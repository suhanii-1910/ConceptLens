"""
Phase 2C unit tests: deterministic evidence boundary evaluation.

All tests use explicitly constructed RetrievalResultItem instances with
exact score values — no real embeddings, no DB, no LLM.
"""
import copy
import math
import uuid

import pytest

from app.models.evidence_unit import Modality
from app.models.source_version import SourceType
from app.schemas.retrieval import (
    Citation,
    CitationErrorCode,
    GroundingStatus,
    RetrievalResultItem,
)
from app.services.evidence_boundary import (
    DEFAULT_POLICY,
    INSUFFICIENT_MESSAGE,
    UNSUPPORTED_MESSAGE,
    EvidenceBoundaryPolicy,
    EvidenceBoundaryReason,
    EvidenceSupportStatus,
    evaluate_evidence_boundary,
    is_relevance_qualified,
    only_supported_evidence,
)

THRESHOLD = DEFAULT_POLICY.dense_distance_threshold  # 0.55


# ─── helpers ────────────────────────────────────────────────────────────────

def _cid():
    return uuid.uuid4()


def _citation(eu_id=None, course_id=None, sv_id=None):
    eu = eu_id or uuid.uuid4()
    co = course_id or uuid.uuid4()
    sv = sv_id or uuid.uuid4()
    return Citation(
        evidence_unit_id=eu,
        course_id=co,
        source_version_id=sv,
        source_filename="test.pdf",
        source_type=SourceType.pdf,
        modality=Modality.text,
        locator={"page_index": 0, "page_number": 1},
        location_metadata={"page_index": 0, "page_number": 1},
        locator_label="test.pdf · p. 1",
    )


def _item(
    *,
    dense_distance=None,
    lexical_score=None,
    fused_score=0.01,
    dense_rank=None,
    lexical_rank=None,
    grounding_status=GroundingStatus.invalid,
    citation=None,
    eu_id=None,
):
    eu = eu_id or uuid.uuid4()
    co = uuid.uuid4()
    sv = uuid.uuid4()
    return RetrievalResultItem(
        evidence_unit_id=eu,
        course_id=co,
        source_version_id=sv,
        source_filename="src.pdf",
        modality=Modality.text,
        fused_score=fused_score,
        dense_rank=dense_rank,
        lexical_rank=lexical_rank,
        dense_distance=dense_distance,
        lexical_score=lexical_score,
        grounding_status=grounding_status,
        citation=citation,
    )


def _valid_item(**kwargs):
    eu = kwargs.pop("eu_id", uuid.uuid4())
    cit = _citation(eu_id=eu)
    return _item(
        eu_id=eu,
        grounding_status=GroundingStatus.valid,
        citation=cit,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# A. SUPPORTED — lexical
# ═══════════════════════════════════════════════════════════════════════════

def test_supported_lexical():
    item = _valid_item(lexical_score=0.15, dense_distance=None)
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.supported
    assert dec.reason == EvidenceBoundaryReason.grounded_relevant_evidence
    assert dec.should_decline is False
    assert dec.message is None
    assert dec.usable_candidate_count == 1
    assert dec.relevant_candidate_count == 1
    assert dec.candidate_count == 1
    assert item.evidence_unit_id in dec.usable_evidence_unit_ids


# ═══════════════════════════════════════════════════════════════════════════
# B. SUPPORTED — dense
# ═══════════════════════════════════════════════════════════════════════════

def test_supported_dense():
    item = _valid_item(lexical_score=None, dense_distance=0.30)
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.supported
    assert dec.should_decline is False
    assert dec.message is None
    assert dec.usable_candidate_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# C. DENSE THRESHOLD EQUALITY — exactly at threshold → qualified
# ═══════════════════════════════════════════════════════════════════════════

def test_dense_threshold_equality():
    item = RetrievalResultItem(
        evidence_unit_id=uuid.uuid4(),
        course_id=uuid.uuid4(),
        source_version_id=uuid.uuid4(),
        source_filename="f.pdf",
        modality=Modality.text,
        dense_distance=THRESHOLD,
        lexical_score=None,
    )
    assert is_relevance_qualified(item) is True


# ═══════════════════════════════════════════════════════════════════════════
# D. DENSE JUST ABOVE THRESHOLD — not qualified
# ═══════════════════════════════════════════════════════════════════════════

def test_dense_just_above_threshold():
    item = RetrievalResultItem(
        evidence_unit_id=uuid.uuid4(),
        course_id=uuid.uuid4(),
        source_version_id=uuid.uuid4(),
        source_filename="f.pdf",
        modality=Modality.text,
        dense_distance=THRESHOLD + 0.001,
        lexical_score=None,
    )
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# E. UNSUPPORTED — no results
# ═══════════════════════════════════════════════════════════════════════════

def test_unsupported_no_results():
    dec = evaluate_evidence_boundary([])
    assert dec.status == EvidenceSupportStatus.unsupported
    assert dec.reason == EvidenceBoundaryReason.no_candidates
    assert dec.should_decline is True
    assert dec.message == UNSUPPORTED_MESSAGE
    assert dec.candidate_count == 0
    assert dec.relevant_candidate_count == 0
    assert dec.usable_candidate_count == 0
    assert dec.usable_evidence_unit_ids == []


# ═══════════════════════════════════════════════════════════════════════════
# F. UNSUPPORTED — irrelevant candidates
# ═══════════════════════════════════════════════════════════════════════════

def test_unsupported_irrelevant_candidates():
    item = _item(lexical_score=0.0, dense_distance=THRESHOLD + 0.1)
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.unsupported
    assert dec.reason == EvidenceBoundaryReason.no_relevant_evidence
    assert dec.should_decline is True
    assert dec.candidate_count == 1
    assert dec.relevant_candidate_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# G. INSUFFICIENT — relevant but grounding invalid
# ═══════════════════════════════════════════════════════════════════════════

def test_insufficient_relevant_invalid_grounding():
    item = _item(
        lexical_score=0.20,
        grounding_status=GroundingStatus.invalid,
        citation=None,
    )
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.insufficient_evidence
    assert dec.reason == EvidenceBoundaryReason.relevant_evidence_not_grounded
    assert dec.should_decline is True
    assert dec.relevant_candidate_count == 1
    assert dec.usable_candidate_count == 0
    assert dec.usable_evidence_unit_ids == []


# ═══════════════════════════════════════════════════════════════════════════
# H. INSUFFICIENT — relevant grounding status valid but citation missing
# ═══════════════════════════════════════════════════════════════════════════

def test_insufficient_relevant_citation_missing():
    item = _item(
        lexical_score=0.20,
        grounding_status=GroundingStatus.valid,
        citation=None,  # citation absent even though status says valid
    )
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.insufficient_evidence
    assert dec.reason == EvidenceBoundaryReason.relevant_evidence_not_grounded
    assert dec.should_decline is True


# ═══════════════════════════════════════════════════════════════════════════
# I. MIXTURE — irrelevant + relevant invalid → insufficient_evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_mixture_irrelevant_and_relevant_invalid():
    irrelevant = _item(lexical_score=None, dense_distance=2.0)
    relevant_invalid = _item(
        lexical_score=0.10,
        grounding_status=GroundingStatus.invalid,
    )
    dec = evaluate_evidence_boundary([irrelevant, relevant_invalid])
    assert dec.status == EvidenceSupportStatus.insufficient_evidence
    assert dec.relevant_candidate_count == 1
    assert dec.usable_candidate_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# J. MIXTURE — valid supported + invalid relevant → supported; usable excludes invalid
# ═══════════════════════════════════════════════════════════════════════════

def test_mixture_valid_and_invalid_usable_only_valid():
    eu_valid = uuid.uuid4()
    eu_invalid = uuid.uuid4()
    valid_item = _valid_item(lexical_score=0.20, eu_id=eu_valid)
    invalid_item = _item(
        lexical_score=0.10,
        grounding_status=GroundingStatus.invalid,
        eu_id=eu_invalid,
    )
    dec = evaluate_evidence_boundary([valid_item, invalid_item])
    assert dec.status == EvidenceSupportStatus.supported
    assert eu_valid in dec.usable_evidence_unit_ids
    assert eu_invalid not in dec.usable_evidence_unit_ids
    assert dec.usable_candidate_count == 1
    assert dec.relevant_candidate_count == 2


# ═══════════════════════════════════════════════════════════════════════════
# K. ORDER — only_supported_evidence preserves retrieval order
# ═══════════════════════════════════════════════════════════════════════════

def test_only_supported_evidence_preserves_order():
    items = [_valid_item(lexical_score=0.10, fused_score=1.0 - i * 0.1) for i in range(5)]
    supported = only_supported_evidence(items)
    assert [x.fused_score for x in supported] == [x.fused_score for x in items]


# ═══════════════════════════════════════════════════════════════════════════
# L. RANKING PRESERVATION — scores unchanged after boundary evaluation
# ═══════════════════════════════════════════════════════════════════════════

def test_ranking_scores_preserved():
    item = _valid_item(
        lexical_score=0.25,
        dense_distance=0.30,
        fused_score=0.042,
        dense_rank=2,
        lexical_rank=1,
    )
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.supported
    # Scores on original item must be unchanged
    assert item.fused_score == 0.042
    assert item.dense_rank == 2
    assert item.lexical_rank == 1
    assert item.dense_distance == 0.30
    assert item.lexical_score == 0.25


# ═══════════════════════════════════════════════════════════════════════════
# M. NO MUTATION — input unchanged after all service calls
# ═══════════════════════════════════════════════════════════════════════════

def test_no_mutation():
    items = [
        _valid_item(lexical_score=0.20),
        _item(dense_distance=2.0),
    ]
    # Deep-copy to compare afterward
    originals = copy.deepcopy([i.model_dump() for i in items])

    evaluate_evidence_boundary(items)
    only_supported_evidence(items)

    for orig, after in zip(originals, [i.model_dump() for i in items]):
        assert orig == after, "Input RetrievalResultItem was mutated"


# ═══════════════════════════════════════════════════════════════════════════
# N. NaN DENSE — must NOT qualify
# ═══════════════════════════════════════════════════════════════════════════

def test_nan_dense_not_qualified():
    item = _item(dense_distance=float("nan"), lexical_score=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# O. +inf DENSE — must NOT qualify
# ═══════════════════════════════════════════════════════════════════════════

def test_pos_inf_dense_not_qualified():
    item = _item(dense_distance=float("inf"), lexical_score=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# P. -inf DENSE — must NOT qualify
# ═══════════════════════════════════════════════════════════════════════════

def test_neg_inf_dense_not_qualified():
    item = _item(dense_distance=float("-inf"), lexical_score=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# Q. None DENSE — must NOT crash
# ═══════════════════════════════════════════════════════════════════════════

def test_none_dense_does_not_crash():
    item = _item(dense_distance=None, lexical_score=None)
    result = is_relevance_qualified(item)
    assert result is False


# ═══════════════════════════════════════════════════════════════════════════
# R. bool DENSE — must NOT be interpreted as numeric support
# ═══════════════════════════════════════════════════════════════════════════

def test_bool_dense_not_qualified():
    # True would be 1 if treated as number, which is < 0.55, but bool must not qualify
    item = RetrievalResultItem(
        evidence_unit_id=uuid.uuid4(),
        course_id=uuid.uuid4(),
        source_version_id=uuid.uuid4(),
        source_filename="f.pdf",
        modality=Modality.text,
        dense_distance=None,
        lexical_score=None,
    )
    # Manually patch (bypassing Pydantic coercion which converts bool to float)
    object.__setattr__(item, "dense_distance", True)  # type: ignore[call-overload]
    from app.services.evidence_boundary import _is_safe_finite_number
    assert _is_safe_finite_number(True) is False


# ═══════════════════════════════════════════════════════════════════════════
# S. NaN LEXICAL — must NOT qualify
# ═══════════════════════════════════════════════════════════════════════════

def test_nan_lexical_not_qualified():
    item = _item(lexical_score=float("nan"), dense_distance=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# T. +inf LEXICAL — must NOT qualify
# ═══════════════════════════════════════════════════════════════════════════

def test_pos_inf_lexical_not_qualified():
    item = _item(lexical_score=float("inf"), dense_distance=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# U. bool LEXICAL — must NOT qualify
# ═══════════════════════════════════════════════════════════════════════════

def test_bool_lexical_not_qualified():
    from app.services.evidence_boundary import _is_safe_finite_number
    assert _is_safe_finite_number(True) is False
    assert _is_safe_finite_number(False) is False


# ═══════════════════════════════════════════════════════════════════════════
# V. FUSED SCORE ONLY — very high fused_score alone must NOT produce supported
# ═══════════════════════════════════════════════════════════════════════════

def test_fused_score_only_not_supported():
    item = _item(
        fused_score=999.0,
        dense_distance=THRESHOLD + 1.0,
        lexical_score=None,
    )
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.unsupported


# ═══════════════════════════════════════════════════════════════════════════
# W. RANK #1 ONLY — dense_rank=1 without qualifying score → unsupported
# ═══════════════════════════════════════════════════════════════════════════

def test_rank_one_only_not_supported():
    item = _item(
        dense_rank=1,
        lexical_rank=1,
        dense_distance=THRESHOLD + 0.5,  # above threshold
        lexical_score=None,
    )
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.unsupported


# ═══════════════════════════════════════════════════════════════════════════
# X. INVALID + IRRELEVANT → UNSUPPORTED (not insufficient_evidence)
# ═══════════════════════════════════════════════════════════════════════════

def test_invalid_grounding_plus_irrelevant_scores_is_unsupported():
    """
    Candidate grounding invalid AND relevance fails.
    Expected: unsupported / no_relevant_evidence (not insufficient_evidence).
    insufficient_evidence means related material exists but is unsafe to cite.
    unsupported means no sufficiently related material exists.
    """
    item = _item(
        dense_distance=THRESHOLD + 0.5,  # not relevant
        lexical_score=None,
        grounding_status=GroundingStatus.invalid,
        citation=None,
    )
    dec = evaluate_evidence_boundary([item])
    assert dec.status == EvidenceSupportStatus.unsupported
    assert dec.reason == EvidenceBoundaryReason.no_relevant_evidence


# ═══════════════════════════════════════════════════════════════════════════
# Extra: lexical_score = 0 → NOT qualified (must be strictly > 0)
# ═══════════════════════════════════════════════════════════════════════════

def test_lexical_zero_not_qualified():
    item = _item(lexical_score=0.0, dense_distance=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# Extra: negative dense_distance → not qualified (must be >= 0)
# ═══════════════════════════════════════════════════════════════════════════

def test_negative_dense_distance_not_qualified():
    item = _item(dense_distance=-0.001, lexical_score=None)
    assert is_relevance_qualified(item) is False


# ═══════════════════════════════════════════════════════════════════════════
# Extra: custom policy threshold respected
# ═══════════════════════════════════════════════════════════════════════════

def test_custom_policy_threshold():
    policy = EvidenceBoundaryPolicy(dense_distance_threshold=0.20)
    item_in = _item(dense_distance=0.19, lexical_score=None)
    item_out = _item(dense_distance=0.21, lexical_score=None)
    assert is_relevance_qualified(item_in, policy) is True
    assert is_relevance_qualified(item_out, policy) is False


# ═══════════════════════════════════════════════════════════════════════════
# Extra: de-duplication of usable_evidence_unit_ids
# ═══════════════════════════════════════════════════════════════════════════

def test_usable_ids_deduplicated_preserves_order():
    eu1 = uuid.uuid4()
    eu2 = uuid.uuid4()
    item_a = _valid_item(lexical_score=0.3, eu_id=eu1)
    item_b = _valid_item(lexical_score=0.2, eu_id=eu2)
    # Duplicate of first
    item_c = _valid_item(lexical_score=0.15, eu_id=eu1)
    dec = evaluate_evidence_boundary([item_a, item_b, item_c])
    assert dec.status == EvidenceSupportStatus.supported
    assert dec.usable_evidence_unit_ids == [eu1, eu2]


# ═══════════════════════════════════════════════════════════════════════════
# Extra: only_supported_evidence excludes irrelevant and invalid
# ═══════════════════════════════════════════════════════════════════════════

def test_only_supported_evidence_excludes_irrelevant_and_invalid():
    good = _valid_item(lexical_score=0.1)
    irrelevant = _item(dense_distance=2.0, grounding_status=GroundingStatus.valid)
    invalid_grounding = _item(lexical_score=0.2, grounding_status=GroundingStatus.invalid)
    result = only_supported_evidence([good, irrelevant, invalid_grounding])
    assert len(result) == 1
    assert result[0].evidence_unit_id == good.evidence_unit_id


# ═══════════════════════════════════════════════════════════════════════════
# Extra: message content
# ═══════════════════════════════════════════════════════════════════════════

def test_unsupported_message_refers_to_course_materials():
    dec = evaluate_evidence_boundary([])
    assert "course materials" in (dec.message or "")
    assert "false" not in (dec.message or "").lower()
    assert "does not exist" not in (dec.message or "").lower()


def test_insufficient_message_refers_to_grounded_evidence():
    item = _item(lexical_score=0.1, grounding_status=GroundingStatus.invalid)
    dec = evaluate_evidence_boundary([item])
    assert "grounded" in (dec.message or "").lower() or "course materials" in (dec.message or "").lower()


def test_supported_message_is_none():
    item = _valid_item(lexical_score=0.1)
    dec = evaluate_evidence_boundary([item])
    assert dec.message is None
