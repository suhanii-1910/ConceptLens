"""Server-owned learning actions and bounded, non-executable teaching content."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.assessment import AssessmentAttemptResponse, AssessmentQuestionPublic
from app.schemas.reasoning_diagnosis import ProbeDraft, EvidenceIDs
from app.schemas.retrieval import Citation
from app.schemas.learner_mastery import MasteryUpdateStatus
from app.schemas.reasoning_diagnosis import Status as DiagnosisStatus, Resolution

Strategy = Literal['source_explanation', 'visual_explanation', 'prerequisite_probe',
    'prerequisite_recap', 'prerequisite_practice', 'worked_example', 'transfer_check']
Feedback = Literal['understood', 'still_confused']
Choice = Literal['sixty_second_recap', 'practice_prerequisite', 'continue_anyway']
SessionStatus = Literal['active', 'complete', 'diagnosis_not_confirmed', 'needs_reassessment']
Action = Literal['source_explanation', 'visual_explanation', 'prerequisite_probe',
    'prerequisite_recap', 'prerequisite_practice', 'worked_example', 'transfer_check',
    'prerequisite_choice', 'reconsider_diagnosis', 'complete', 'collect_more_reasoning',
    'general_practice', 'diagnostic_probe']
PlainText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SessionCreate(StrictModel):
    diagnosis_id: uuid.UUID


class FeedbackCreate(StrictModel):
    intervention_id: uuid.UUID
    feedback: Feedback


class PrerequisiteChoice(StrictModel):
    intervention_id: uuid.UUID
    choice: Choice


class LearningAttemptCreate(StrictModel):
    selected_option_index: int = Field(strict=True, ge=0, le=3)


class VisualStep(StrictModel):
    label: PlainText
    annotation: PlainText


class VisualPayload(StrictModel):
    title: PlainText
    steps: list[VisualStep] = Field(min_length=1, max_length=12)


class TeachingPayload(StrictModel):
    title: PlainText
    body: PlainText
    steps: list[PlainText] = Field(default_factory=list, max_length=12)
    visual: VisualPayload | None = None


class TeachingDraft(StrictModel):
    strategy: Strategy
    payload: TeachingPayload | None = None
    question: ProbeDraft | None = None
    evidence_unit_ids: EvidenceIDs = Field(min_length=1)

    @model_validator(mode='after')
    def validate_content(self):
        graded = self.strategy in {'prerequisite_probe', 'prerequisite_practice', 'transfer_check'}
        if graded != (self.question is not None) or graded == (self.payload is not None):
            raise ValueError('Return either teaching payload or a graded question for the requested strategy.')
        if self.strategy == 'visual_explanation' and self.payload.visual is None:
            raise ValueError('Visual explanation requires structured visual steps.')
        # These strings are display data, never HTML, SVG, scripts or URLs to execute.
        def check(value):
            if isinstance(value, str) and re.search(r'<\s*(?:/?[a-zA-Z!]|\?)|javascript\s*:|data\s*:\s*text/html', value, re.I):
                raise ValueError('Executable markup is not teaching content.')
            if isinstance(value, dict):
                for item in value.values(): check(item)
            if isinstance(value, list):
                for item in value: check(item)
        check(self.model_dump(mode='json'))
        return self


class TeachingVerification(StrictModel):
    verdict: Literal['verified', 'rejected']
    strategy_matches: bool = Field(strict=True)
    addresses_gap: bool = Field(strict=True)
    source_supported: bool = Field(strict=True)
    materially_different: bool = Field(strict=True)
    answer_supported: bool = Field(strict=True)
    no_answer_leak: bool = Field(strict=True)
    no_permanent_label: bool = Field(strict=True)
    same_target_rule: bool = Field(strict=True)
    fresh_structure: bool = Field(strict=True)
    evidence_unit_ids: EvidenceIDs = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence_for_verified(self):
        if self.verdict == "verified" and not self.evidence_unit_ids:
            raise ValueError(
                "Verified teaching content requires supporting evidence."
            )
        return self


class InterventionPublic(StrictModel):
    id: uuid.UUID
    sequence_index: int
    strategy: Strategy
    target_concept_id: uuid.UUID
    prerequisite_concept_id: uuid.UUID | None
    prerequisite_edge_id: uuid.UUID | None
    payload: TeachingPayload | None
    question: AssessmentQuestionPublic | None
    citations: list[Citation]
    verified: bool
    feedback: Feedback | None
    learner_choice: Choice | None
    completed: bool
    response_attempt_id: uuid.UUID | None
    created_at: datetime


class SessionPublic(StrictModel):
    id: uuid.UUID
    course_id: uuid.UUID
    learner_id: uuid.UUID
    diagnosis_id: uuid.UUID
    target_concept_id: uuid.UUID | None
    status: SessionStatus
    current_action: Action
    reason: str
    current_intervention: InterventionPublic | None
    prerequisite_choices: list[Choice]
    created_at: datetime
    updated_at: datetime


class LearningAttemptPublic(StrictModel):
    session: SessionPublic
    attempt: AssessmentAttemptResponse


class ProofFlags(StrictModel):
    source_location_verified: bool
    diagnostic_question_verified: bool
    citation_valid: bool
    teaching_content_verified: bool
    transfer_check_verified: bool
    learner_update_based_on_verified_evidence: bool


class ObservedReasoning(StrictModel):
    diagnosis_id: uuid.UUID
    assessment_attempt_id: uuid.UUID
    question_id: uuid.UUID
    reasoning_text: str | None
    reasoning_steps: list[str]
    observed_reasoning: str | None
    first_break_step_index: int | None
    first_break_excerpt: str | None


class DiagnosticEvidence(StrictModel):
    attempt_id: uuid.UUID
    probe_id: uuid.UUID
    selected_option_index: int
    is_correct: bool | None
    applied_outcome: Resolution | None
    created_at: datetime


class TransferResult(StrictModel):
    transfer_check_id: uuid.UUID
    question_id: uuid.UUID
    status: Literal['pending', 'passed', 'failed']
    resolved_attempt_id: uuid.UUID | None
    is_correct: bool | None
    mastery_update_status: MasteryUpdateStatus | None


class LearnerUpdateEvidence(StrictModel):
    observation_id: uuid.UUID
    attempt_id: uuid.UUID
    concept_id: uuid.UUID
    observation_index: int
    prior_mastery: float
    updated_mastery: float
    model_version: str
    created_at: datetime


class LearningTrace(StrictModel):
    session: SessionPublic
    observed: ObservedReasoning
    hypothesis: str | None
    diagnostic_evidence: list[DiagnosticEvidence]
    interpretation: DiagnosisStatus
    teaching_actions: list[InterventionPublic]
    transfer_result: TransferResult | None
    learner_updates: list[LearnerUpdateEvidence]
    proof: ProofFlags
