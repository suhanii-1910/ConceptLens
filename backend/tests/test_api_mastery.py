"""Phase 5 attempt transactions and read-only mastery API contracts."""

import uuid
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import event, func, insert, select

from app.models.assessment import AssessmentAttempt
from app.models.concept import Concept
from app.models.learner_mastery import (
    LearnerConceptMastery, MasteryObservation, assessment_question_concept_link,
)
from tests.conftest import TEST_ENGINE
from tests.test_api_assessment import _create_course, _seed_verified_question

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def no_providers(monkeypatch):
    factory = Mock(side_effect=AssertionError("Mastery must never create a provider"))
    generate = AsyncMock(side_effect=AssertionError("Mastery must never call a provider"))
    monkeypatch.setattr("app.services.llm_provider.get_llm_provider", factory)
    monkeypatch.setattr("app.services.assessment_generation.get_llm_provider", factory)
    monkeypatch.setattr("app.services.llm_provider.OpenAILLMProvider.generate", generate)
    yield
    factory.assert_not_called()
    generate.assert_not_called()


async def mapped_question(db, course, concepts):
    question = await _seed_verified_question(db, course.id)
    if concepts:
        await db.execute(insert(assessment_question_concept_link), [
            {"question_id": question.id, "concept_id": c.id} for c in concepts
        ])
        await db.commit()
    return question


async def seed(db, count=1):
    course = await _create_course(db)
    concepts = [Concept(id=uuid.uuid4(), course_id=course.id, name=f"Concept {i}") for i in range(count)]
    db.add_all(concepts)
    await db.commit()
    return course, concepts, await mapped_question(db, course, concepts)


async def submit(client, course, question, learner, selected=2):
    return await client.post(
        f"/courses/{course.id}/assessments/questions/{question.id}/attempts",
        json={"learner_id": str(learner), "selected_option_index": selected},
    )


async def counts(db):
    return tuple([await db.scalar(select(func.count()).select_from(model)) for model in (
        AssessmentAttempt, LearnerConceptMastery, MasteryObservation,
    )])


@pytest.mark.parametrize("n,status", [(0, "skipped_unmapped"), (1, "updated"), (2, "skipped_ambiguous")])
async def test_mapping_policy(client, db_session, n, status):
    course, concepts, q = await seed(db_session, n)
    r = await submit(client, course, q, uuid.uuid4())
    assert r.status_code == 200
    data = r.json()
    assert data["mastery_update_status"] == status
    assert data["is_correct"] is True
    assert data["correct_option_index"] == 2
    assert data["citations"] == q.citation_snapshots
    assert data["explanation"] == q.explanation
    assert await counts(db_session) == (1, int(n == 1), int(n == 1))
    attempt = await db_session.get(AssessmentAttempt, uuid.UUID(data["attempt_id"]))
    assert attempt.mastery_update_status.value == status
    if n == 1:
        update = data["mastery_update"]
        assert update["updated_mastery"] == pytest.approx(49 / 85)
        assert update["concept_id"] == str(concepts[0].id)
        assert update["model_version"] == "bkt-v1"
    else:
        assert data["mastery_update"] is None


async def test_repeats_order_counts_and_last_attempt(client, db_session):
    course, concepts, q1 = await seed(db_session)
    q2 = await mapped_question(db_session, course, concepts)
    learner = uuid.uuid4()
    first = (await submit(client, course, q1, learner, 0)).json()
    repeat = (await submit(client, course, q1, learner)).json()
    second = (await submit(client, course, q2, learner)).json()
    assert repeat["mastery_update_status"] == "skipped_repeated_question"
    assert repeat["mastery_update"] is None
    assert len({d["attempt_id"] for d in [first, repeat, second]}) == 3
    assert await counts(db_session) == (3, 1, 2)
    obs = (await db_session.scalars(select(MasteryObservation).order_by(MasteryObservation.observation_index))).all()
    assert [o.observation_index for o in obs] == [1, 2]
    assert [o.is_correct for o in obs] == [False, True]
    assert obs[1].prior_mastery == obs[0].updated_mastery
    assert obs[1].updated_mastery == pytest.approx(.45660377358490567)
    assert all((o.learn_probability, o.guess_probability, o.slip_probability, o.model_version) == (.1, .2, .1, "bkt-v1") for o in obs)
    last_repeat = (await submit(client, course, q1, learner)).json()
    assert last_repeat["mastery_update_status"] == "skipped_repeated_question"
    mastery = (await db_session.scalars(select(LearnerConceptMastery))).one()
    assert (mastery.observation_count, mastery.correct_count) == (2, 1)
    assert str(mastery.last_attempt_id) == second["attempt_id"]
    original = await db_session.get(AssessmentAttempt, uuid.UUID(first["attempt_id"]))
    assert original.selected_option_index == 0 and original.is_correct is False
    assert await counts(db_session) == (4, 1, 2)


async def test_historical_attempt_is_exposure_without_initialization(client, db_session):
    course, _, q = await seed(db_session)
    learner = uuid.uuid4()
    db_session.add(AssessmentAttempt(
        id=uuid.uuid4(), question_id=q.id, course_id=course.id, learner_id=learner,
        selected_option_index=0, is_correct=False, mastery_update_status=None,
    ))
    await db_session.commit()
    r = await submit(client, course, q, learner)
    assert r.status_code == 200
    assert r.json()["mastery_update_status"] == "skipped_repeated_question"
    assert await counts(db_session) == (2, 0, 0)


async def test_distinct_learners_and_courses_are_isolated(client, db_session):
    c1, concepts, q1 = await seed(db_session)
    c2, _, q2 = await seed(db_session)
    a, b = uuid.uuid4(), uuid.uuid4()
    for course, q, learner, option in [(c1, q1, a, 2), (c1, q1, b, 0), (c2, q2, a, 0)]:
        assert (await submit(client, course, q, learner, option)).json()["mastery_update_status"] == "updated"
    assert (await submit(client, c2, q1, a)).status_code == 404
    rows = (await db_session.scalars(select(LearnerConceptMastery))).all()
    assert len(rows) == 3
    assert next(r for r in rows if r.course_id == c1.id and r.learner_id == a).mastery_probability == pytest.approx(49 / 85)
    assert next(r for r in rows if r.course_id == c1.id and r.learner_id == b).mastery_probability == pytest.approx(7 / 55)


async def test_foreign_frozen_mapping_fails_closed(client, db_session):
    c1, _, _ = await seed(db_session, 0)
    _, foreign, _ = await seed(db_session)
    q = await mapped_question(db_session, c1, foreign)
    with pytest.raises(ValueError, match="same course"):
        await submit(client, c1, q, uuid.uuid4())
    assert await counts(db_session) == (0, 0, 0)


async def test_bkt_failure_rolls_back_attempt_and_new_mastery(client, db_session, monkeypatch):
    course, _, q = await seed(db_session)
    monkeypatch.setattr("app.services.mastery_update.compute_bkt_step", Mock(side_effect=ValueError("BKT failure")))
    with pytest.raises(ValueError, match="BKT failure"):
        await submit(client, course, q, uuid.uuid4())
    assert await counts(db_session) == (0, 0, 0)


async def test_observation_failure_rolls_back_existing_mastery(client, db_session):
    course, concepts, q1 = await seed(db_session)
    q2 = await mapped_question(db_session, course, concepts)
    learner = uuid.uuid4()
    first = (await submit(client, course, q1, learner)).json()
    def fail(mapper, connection, target):
        raise RuntimeError("Observation insert failed")
    event.listen(MasteryObservation, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="Observation insert failed"):
            await submit(client, course, q2, learner, 0)
    finally:
        event.remove(MasteryObservation, "before_insert", fail)
    assert await counts(db_session) == (1, 1, 1)
    mastery = (await db_session.scalars(select(LearnerConceptMastery))).one()
    assert mastery.observation_count == mastery.correct_count == 1
    assert mastery.mastery_probability == pytest.approx(49 / 85)
    assert str(mastery.last_attempt_id) == first["attempt_id"]


async def test_bad_snapshot_rolls_back_before_attempt(client, db_session):
    course, _, q = await seed(db_session)
    q.citation_snapshots = [{"invalid": True}]
    await db_session.commit()
    with pytest.raises(ValueError):
        await submit(client, course, q, uuid.uuid4())
    assert await counts(db_session) == (0, 0, 0)


async def test_observation_cannot_be_rewritten(client, db_session):
    course, _, q = await seed(db_session)
    await submit(client, course, q, uuid.uuid4())
    obs = (await db_session.scalars(select(MasteryObservation))).one()
    obs.is_correct = False
    with pytest.raises(ValueError, match="immutable"):
        await db_session.commit()
    await db_session.rollback()
    saved = (await db_session.scalars(select(MasteryObservation))).one()
    assert saved.is_correct is True


async def test_observation_cannot_be_deleted(client, db_session):
    course, _, q = await seed(db_session)
    await submit(client, course, q, uuid.uuid4())
    obs = (await db_session.scalars(select(MasteryObservation))).one()
    await db_session.delete(obs)
    with pytest.raises(ValueError, match="immutable"):
        await db_session.commit()
    await db_session.rollback()
    assert await counts(db_session) == (1, 1, 1)


async def test_read_api_persisted_virtual_order_and_zero_writes(client, db_session):
    course, concepts, q = await seed(db_session)
    learner = uuid.uuid4()
    result = (await submit(client, course, q, learner)).json()
    # Same-name concepts must sort by UUID, independently of insertion order.
    unseen = [Concept(id=uuid.UUID(int=i), course_id=course.id, name="A concept") for i in [12, 11]]
    db_session.add_all(unseen)
    await db_session.commit()
    before = await counts(db_session)
    statements = []
    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())
    event.listen(TEST_ENGINE.sync_engine, "before_cursor_execute", record)
    try:
        base = f"/courses/{course.id}/learners/{learner}/mastery"
        for _ in range(2):
            response = await client.get(base)
            assert response.status_code == 200
            data = response.json()
            assert data["model_version"] == "bkt-v1"
            assert [c["concept_id"] for c in data["concepts"]] == [str(uuid.UUID(int=11)), str(uuid.UUID(int=12)), str(concepts[0].id)]
            virtual = data["concepts"][0]
            assert virtual["mastery_probability"] == .2
            assert virtual["observation_count"] == virtual["correct_count"] == 0
            assert virtual["mastery_band"] == "unseen"
            assert virtual["last_attempt_id"] is virtual["created_at"] is virtual["updated_at"] is None
            assert virtual["model_version"] == "bkt-v1"
            persisted = data["concepts"][2]
            assert persisted["last_attempt_id"] == result["attempt_id"]
            assert persisted["mastery_probability"] == pytest.approx(49 / 85)
            assert persisted["created_at"] and persisted["updated_at"]
            assert (await client.get(base + f"/{concepts[0].id}")).json() == persisted
            assert (await client.get(base + f"/{uuid.UUID(int=11)}")).json() == virtual
        unknown = await client.get(f"/courses/{course.id}/learners/{uuid.uuid4()}/mastery")
        assert all(c["mastery_band"] == "unseen" for c in unknown.json()["concepts"])
    finally:
        event.remove(TEST_ENGINE.sync_engine, "before_cursor_execute", record)
    assert statements
    assert not set(statements) & {"INSERT", "UPDATE", "DELETE", "REPLACE"}
    assert await counts(db_session) == before


async def test_read_empty_missing_and_foreign(client, db_session):
    empty = await _create_course(db_session)
    course, concepts, _ = await seed(db_session)
    learner = uuid.uuid4()
    base = f"/courses/{empty.id}/learners/{learner}/mastery"
    assert (await client.get(base)).json()["concepts"] == []
    assert (await client.get(base + f"/{concepts[0].id}")).status_code == 404
    assert (await client.get(base + f"/{uuid.uuid4()}")).status_code == 404
    assert (await client.get(f"/courses/{uuid.uuid4()}/learners/{learner}/mastery")).status_code == 404
    assert (await client.get(f"/courses/{course.id}/learners/{learner}/mastery/{concepts[0].id}")).json()["mastery_band"] == "unseen"
    assert await counts(db_session) == (0, 0, 0)
