import uuid
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models.concept import Concept
from app.models.assessment import AssessmentAttempt
from app.models.learner_mastery import LearnerConceptMastery, MasteryObservation
from app.schemas.learner_mastery import (
    MasteryUpdateStatus,
    LearnerMasteryUpdatePublic,
)
from app.services.learner_mastery import (
    compute_bkt_step,
    get_mastery_band,
    BKT_INITIAL_MASTERY
)


async def process_mastery_update(
    db: AsyncSession,
    attempt: AssessmentAttempt,
    course_id: uuid.UUID,
    concepts: List[Concept],
) -> Tuple[MasteryUpdateStatus, Optional[LearnerMasteryUpdatePublic]]:
    """Apply mastery within the caller's transaction; never commit independently."""
    if attempt.course_id != course_id or any(c.course_id != course_id for c in concepts):
        raise ValueError("Question concepts and attempt must belong to the same course.")

    if len(concepts) == 0:
        return MasteryUpdateStatus.skipped_unmapped, None

    if len(concepts) > 1:
        return MasteryUpdateStatus.skipped_ambiguous, None

    concept = concepts[0]

    # G. REPEATED QUESTION PROTECTION
    stmt_prior_exposure = select(AssessmentAttempt.id).where(
        AssessmentAttempt.learner_id == attempt.learner_id,
        AssessmentAttempt.course_id == course_id,
        AssessmentAttempt.question_id == attempt.question_id,
        AssessmentAttempt.id != attempt.id,
    ).limit(1)

    prior_exposure = await db.scalar(stmt_prior_exposure)
    if prior_exposure:
        return MasteryUpdateStatus.skipped_repeated_question, None

    # H. POSTGRESQL-SAFE MASTERY CONCURRENCY
    # 1. ensure mastery row exists using PostgreSQL INSERT ... ON CONFLICT DO NOTHING

    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert  # Unit tests only; SQLite does not provide row locks.
    else:
        raise ValueError("Mastery updates require PostgreSQL (or SQLite for unit tests).")
    await db.execute(
        insert(LearnerConceptMastery).values(
            id=uuid.uuid4(), learner_id=attempt.learner_id, course_id=course_id,
            concept_id=concept.id, mastery_probability=BKT_INITIAL_MASTERY,
            observation_count=0, correct_count=0,
        ).on_conflict_do_nothing(
            index_elements=["learner_id", "course_id", "concept_id"]
        )
    )

    # 2. in a separate statement: SELECT mastery row FOR UPDATE
    select_stmt = select(LearnerConceptMastery).where(
        LearnerConceptMastery.learner_id == attempt.learner_id,
        LearnerConceptMastery.course_id == course_id,
        LearnerConceptMastery.concept_id == concept.id,
    ).with_for_update().execution_options(populate_existing=True)

    mastery = await db.scalar(select_stmt)
    if not mastery:
        raise ValueError("Failed to obtain LearnerConceptMastery lock.")

    # Another request may have committed this question while we waited for the
    # same learner/concept row. The first check avoids initializing legacy repeats;
    # this check serializes concurrent first exposures under PostgreSQL READ COMMITTED.
    if await db.scalar(stmt_prior_exposure):
        return MasteryUpdateStatus.skipped_repeated_question, None

    # 3. read current probability/counters only after acquiring the lock
    prior_mastery = mastery.mastery_probability
    observation_count = mastery.observation_count
    correct_count = mastery.correct_count

    # 4. compute BKT
    bkt_result = compute_bkt_step(
        prior=prior_mastery,
        is_correct=attempt.is_correct,
    )

    updated_mastery_prob = bkt_result.updated_mastery
    new_obs_count = observation_count + 1
    new_correct_count = correct_count + (1 if attempt.is_correct else 0)

    # 5. update:
    mastery.mastery_probability = updated_mastery_prob
    mastery.observation_count = new_obs_count
    mastery.correct_count = new_correct_count
    mastery.last_attempt_id = attempt.id

    # 6. observation_index = previous observation_count + 1
    observation_index = new_obs_count

    # 7. append MasteryObservation
    obs = MasteryObservation(
        id=uuid.uuid4(),
        learner_mastery_id=mastery.id,
        learner_id=attempt.learner_id,
        course_id=course_id,
        concept_id=concept.id,
        attempt_id=attempt.id,
        question_id=attempt.question_id,
        is_correct=attempt.is_correct,
        observation_index=observation_index,
        prior_mastery=bkt_result.prior_mastery,
        posterior_mastery=bkt_result.posterior_mastery,
        updated_mastery=bkt_result.updated_mastery,
        learn_probability=bkt_result.learn_probability,
        guess_probability=bkt_result.guess_probability,
        slip_probability=bkt_result.slip_probability,
        model_version=bkt_result.model_version,
    )
    db.add(obs)
    db.add(mastery)

    band = get_mastery_band(new_obs_count, updated_mastery_prob)

    update_public = LearnerMasteryUpdatePublic(
        concept_id=concept.id,
        concept_name=concept.name,
        prior_mastery=prior_mastery,
        posterior_mastery=bkt_result.posterior_mastery,
        updated_mastery=bkt_result.updated_mastery,
        mastery_band=band,
        observation_count=new_obs_count,
        correct_count=new_correct_count,
        model_version=bkt_result.model_version,
    )

    return MasteryUpdateStatus.updated, update_public
