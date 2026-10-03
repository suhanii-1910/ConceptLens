import math
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from app.schemas.retrieval import GroundingStatus, RetrievalResultItem


UNSUPPORTED_MESSAGE = (
    "I couldn't find enough relevant support for this in the uploaded course materials."
)
INSUFFICIENT_MESSAGE = (
    "I found related material, but not enough grounded evidence to answer reliably "
    "from the uploaded course materials."
)


class EvidenceSupportStatus(str, Enum):
    supported = "supported"
    insufficient_evidence = "insufficient_evidence"
    unsupported = "unsupported"


class EvidenceBoundaryReason(str, Enum):
    grounded_relevant_evidence = "grounded_relevant_evidence"
    no_candidates = "no_candidates"
    no_relevant_evidence = "no_relevant_evidence"
    relevant_evidence_not_grounded = "relevant_evidence_not_grounded"


@dataclass(frozen=True)
class EvidenceBoundaryPolicy:
    dense_distance_threshold: float = 0.55


DEFAULT_POLICY = EvidenceBoundaryPolicy()


@dataclass(frozen=True)
class EvidenceBoundaryDecision:
    status: EvidenceSupportStatus
    reason: EvidenceBoundaryReason
    should_decline: bool
    message: str | None
    candidate_count: int
    relevant_candidate_count: int
    usable_candidate_count: int
    usable_evidence_unit_ids: list[uuid.UUID]


def _is_safe_finite_number(value: object) -> bool:
    """Return True only for a non-bool real finite number."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def is_relevance_qualified(
    item: RetrievalResultItem,
    policy: EvidenceBoundaryPolicy = DEFAULT_POLICY,
) -> bool:
    """Return True if the item passes at least one relevance signal."""
    # Lexical branch: lexical_score is a positive finite number
    lex = item.lexical_score
    if _is_safe_finite_number(lex) and float(lex) > 0:  # type: ignore[arg-type]
        return True

    # Dense branch: dense_distance finite, non-negative, within threshold (inclusive)
    dist = item.dense_distance
    if _is_safe_finite_number(dist):
        d = float(dist)  # type: ignore[arg-type]
        if 0 <= d <= policy.dense_distance_threshold:
            return True

    return False


def _is_usable(item: RetrievalResultItem) -> bool:
    return (
        item.grounding_status == GroundingStatus.valid
        and item.citation is not None
    )


def evaluate_evidence_boundary(
    results: Sequence[RetrievalResultItem],
    policy: EvidenceBoundaryPolicy = DEFAULT_POLICY,
) -> EvidenceBoundaryDecision:
    candidate_count = len(results)

    if candidate_count == 0:
        return EvidenceBoundaryDecision(
            status=EvidenceSupportStatus.unsupported,
            reason=EvidenceBoundaryReason.no_candidates,
            should_decline=True,
            message=UNSUPPORTED_MESSAGE,
            candidate_count=0,
            relevant_candidate_count=0,
            usable_candidate_count=0,
            usable_evidence_unit_ids=[],
        )

    relevant_items = [r for r in results if is_relevance_qualified(r, policy)]
    relevant_count = len(relevant_items)

    if relevant_count == 0:
        return EvidenceBoundaryDecision(
            status=EvidenceSupportStatus.unsupported,
            reason=EvidenceBoundaryReason.no_relevant_evidence,
            should_decline=True,
            message=UNSUPPORTED_MESSAGE,
            candidate_count=candidate_count,
            relevant_candidate_count=0,
            usable_candidate_count=0,
            usable_evidence_unit_ids=[],
        )

    usable_items = [r for r in relevant_items if _is_usable(r)]
    usable_count = len(usable_items)

    # De-duplicate by first occurrence while preserving order
    seen: set[uuid.UUID] = set()
    usable_ids: list[uuid.UUID] = []
    for item in usable_items:
        if item.evidence_unit_id not in seen:
            seen.add(item.evidence_unit_id)
            usable_ids.append(item.evidence_unit_id)

    if usable_count == 0:
        return EvidenceBoundaryDecision(
            status=EvidenceSupportStatus.insufficient_evidence,
            reason=EvidenceBoundaryReason.relevant_evidence_not_grounded,
            should_decline=True,
            message=INSUFFICIENT_MESSAGE,
            candidate_count=candidate_count,
            relevant_candidate_count=relevant_count,
            usable_candidate_count=0,
            usable_evidence_unit_ids=[],
        )

    return EvidenceBoundaryDecision(
        status=EvidenceSupportStatus.supported,
        reason=EvidenceBoundaryReason.grounded_relevant_evidence,
        should_decline=False,
        message=None,
        candidate_count=candidate_count,
        relevant_candidate_count=relevant_count,
        usable_candidate_count=usable_count,
        usable_evidence_unit_ids=usable_ids,
    )


def only_supported_evidence(
    results: Sequence[RetrievalResultItem],
    policy: EvidenceBoundaryPolicy = DEFAULT_POLICY,
) -> list[RetrievalResultItem]:
    """Return only results that are relevance-qualified AND validly grounded AND have a citation.

    Preserves original retrieval order. Does not rescore, rerank, or mutate.
    """
    return [r for r in results if is_relevance_qualified(r, policy) and _is_usable(r)]
