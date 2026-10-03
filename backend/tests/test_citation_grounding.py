import pytest
import uuid
from typing import Any

from app.models.evidence_unit import EvidenceUnit, Modality, ExtractionStatus
from app.models.source_version import SourceVersion, SourceType, ProcessingStatus
from app.schemas.retrieval import GroundingStatus, CitationErrorCode, RetrievalResultItem
from app.services.citation_grounding import validate_and_build_citation, validate_bounding_box, only_grounded, ground_retrieval_results

@pytest.fixture
def base_ids():
    return {
        "course": uuid.uuid4(),
        "sv": uuid.uuid4(),
        "eu": uuid.uuid4(),
    }

@pytest.fixture
def fake_sv(base_ids):
    return SourceVersion(
        id=base_ids["sv"],
        course_id=base_ids["course"],
        original_filename="lect.pdf",
        source_type=SourceType.pdf,
        processing_status=ProcessingStatus.ready
    )

@pytest.fixture
def fake_eu(base_ids):
    return EvidenceUnit(
        id=base_ids["eu"],
        course_id=base_ids["course"],
        source_version_id=base_ids["sv"],
        modality=Modality.text,
        extraction_status=ExtractionStatus.extracted,
        location_metadata={"page_index": 0, "page_number": 1}
    )

def test_pdf_valid(fake_eu, fake_sv, base_ids):
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.valid
    assert res.errors == []
    assert res.citation is not None
    assert res.citation.locator["page_number"] == 1
    assert res.citation.locator["page_index"] == 0
    assert res.citation.locator_label == "lect.pdf · p. 1"

def test_pdf_missing_page(fake_eu, fake_sv, base_ids):
    fake_eu.location_metadata = {"bounding_box": [0,0,1,1]}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.missing_locator in res.errors

def test_pdf_negative_page(fake_eu, fake_sv, base_ids):
    fake_eu.location_metadata = {"page_index": -1, "page_number": 1}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.invalid_page in res.errors

def test_pdf_zero_page(fake_eu, fake_sv, base_ids):
    fake_eu.location_metadata = {"page_index": 0, "page_number": 0}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.invalid_page in res.errors

def test_pdf_mismatch_page(fake_eu, fake_sv, base_ids):
    fake_eu.location_metadata = {"page_index": 0, "page_number": 2}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.inconsistent_locator in res.errors

def test_pdf_valid_bbox(fake_eu, fake_sv, base_ids):
    fake_eu.location_metadata = {"page_index": 0, "page_number": 1, "bounding_box": [10.5, 20.1, 100.0, 200.0]}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.valid
    assert "bounding_box" in res.citation.locator

def test_pdf_invalid_bbox(fake_eu, fake_sv, base_ids):
    fake_eu.location_metadata = {"page_index": 0, "page_number": 1, "bounding_box": [100.0, 200.0, 10.5, 20.1]} # inverted
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.invalid_bounding_box in res.errors

def test_pptx_valid(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.pptx
    fake_sv.original_filename = "slides.pptx"
    fake_eu.location_metadata = {"slide_index": 5, "slide_number": 6, "shape_index": 2}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.valid
    assert res.citation.locator_label == "slides.pptx · slide 6"
    assert res.citation.locator["shape_index"] == 2

def test_pptx_missing_slide(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.pptx
    fake_eu.location_metadata = {"shape_index": 2}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.missing_locator in res.errors


def test_transcript_valid(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_sv.original_filename = "vid.mp4"
    fake_eu.modality = Modality.video
    fake_eu.location_metadata = {"element_type": "transcript_segment", "start_seconds": 0.0, "end_seconds": 2.5, "source_duration_seconds": 10.0, "timestamp_source": "x"}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.valid
    assert res.citation.locator_label == "vid.mp4 · 00:00–00:02"
    assert res.citation.locator["timestamp_source"] == "x"

def test_transcript_negative_start(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_eu.modality = Modality.video
    fake_eu.location_metadata = {"element_type": "transcript_segment", "start_seconds": -1.0, "end_seconds": 2.5}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.invalid_timestamp in res.errors

def test_transcript_nan(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_eu.modality = Modality.video
    fake_eu.location_metadata = {"element_type": "transcript_segment", "start_seconds": float("nan"), "end_seconds": 2.5}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid

def test_transcript_end_before_start(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_eu.modality = Modality.video
    fake_eu.location_metadata = {"element_type": "transcript_segment", "start_seconds": 5.0, "end_seconds": 2.5}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid

def test_transcript_out_of_bounds(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_eu.modality = Modality.video
    fake_eu.location_metadata = {"element_type": "transcript_segment", "start_seconds": 0.0, "end_seconds": 12.0, "source_duration_seconds": 10.0}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.timestamp_out_of_bounds in res.errors

def test_frame_valid(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_sv.original_filename = "vid.mp4"
    fake_eu.modality = Modality.image
    fake_eu.location_metadata = {"element_type": "video_frame", "timestamp_seconds": 3662.0, "source_frame_index": 1500}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.valid
    assert res.citation.locator_label == "vid.mp4 · 01:01:02"
    assert res.citation.locator["source_frame_index"] == 1500

def test_frame_missing_ts(fake_eu, fake_sv, base_ids):
    fake_sv.source_type = SourceType.video
    fake_eu.modality = Modality.image
    fake_eu.location_metadata = {"element_type": "video_frame", "source_frame_index": 1500}
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid

def test_wrong_course(fake_eu, fake_sv, base_ids):
    res = validate_and_build_citation(fake_eu, fake_sv, uuid.uuid4())
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.wrong_course in res.errors

def test_source_mismatch(fake_eu, fake_sv, base_ids):
    fake_eu.source_version_id = uuid.uuid4()
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.source_mismatch in res.errors

def test_source_not_ready(fake_eu, fake_sv, base_ids):
    fake_sv.processing_status = ProcessingStatus.processing
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.source_not_ready in res.errors

def test_evidence_not_extracted(fake_eu, fake_sv, base_ids):
    fake_eu.extraction_status = ExtractionStatus.pending
    res = validate_and_build_citation(fake_eu, fake_sv, base_ids["course"])
    assert res.status == GroundingStatus.invalid
    assert CitationErrorCode.evidence_not_extracted in res.errors

def test_only_grounded(base_ids):
    valid_item = RetrievalResultItem(
        evidence_unit_id=base_ids["eu"],
        course_id=base_ids["course"],
        source_version_id=base_ids["sv"],
        source_filename="x",
        modality=Modality.text,
        fused_score=1.0,
        grounding_status=GroundingStatus.valid,
        citation={"evidence_unit_id": base_ids["eu"], "course_id": base_ids["course"], "source_version_id": base_ids["sv"], "source_filename": "x", "source_type": SourceType.pdf, "modality": Modality.text, "locator": {}, "location_metadata": {}, "locator_label": ""}
    )
    invalid_item = RetrievalResultItem(
        evidence_unit_id=base_ids["eu"],
        course_id=base_ids["course"],
        source_version_id=base_ids["sv"],
        source_filename="y",
        modality=Modality.text,
        fused_score=0.9,
        grounding_status=GroundingStatus.invalid,
        grounding_errors=[CitationErrorCode.missing_locator]
    )
    
    filtered = only_grounded([valid_item, invalid_item])
    assert len(filtered) == 1
    assert filtered[0].source_filename == "x"

def test_only_grounded_preserves_order(base_ids):
    items = []
    for i in range(10):
        item = RetrievalResultItem(
            evidence_unit_id=base_ids["eu"],
            course_id=base_ids["course"],
            source_version_id=base_ids["sv"],
            source_filename=f"x{i}",
            modality=Modality.text,
            fused_score=1.0 - i * 0.1,
            grounding_status=GroundingStatus.valid if i % 2 == 0 else GroundingStatus.invalid,
            citation={"evidence_unit_id": base_ids["eu"], "course_id": base_ids["course"], "source_version_id": base_ids["sv"], "source_filename": "x", "source_type": SourceType.pdf, "modality": Modality.text, "locator": {}, "location_metadata": {}, "locator_label": ""} if i % 2 == 0 else None
        )
        items.append(item)

    res = only_grounded(items)
    score_list = [r.fused_score for r in res]
    assert score_list == sorted(score_list, reverse=True)


def test_video_frame_derived_path_excluded_from_citation(base_ids):
    raw_meta = {
        "element_type": "video_frame",
        "frame_index": 0,
        "source_frame_index": 12,
        "timestamp_seconds": 2.0,
        "timestamp_ms": 2000,
        "source_duration_seconds": 10.0,
        "derived_path": "/Users/example/private/frame.jpg",
    }
    sv = SourceVersion(
        id=base_ids["sv"],
        course_id=base_ids["course"],
        original_filename="vid.mp4",
        source_type=SourceType.video,
        processing_status=ProcessingStatus.ready,
    )
    eu = EvidenceUnit(
        id=base_ids["eu"],
        course_id=base_ids["course"],
        source_version_id=base_ids["sv"],
        modality=Modality.image,
        extraction_status=ExtractionStatus.extracted,
        location_metadata=raw_meta,
    )

    res = validate_and_build_citation(eu, sv, base_ids["course"])

    assert res.status == GroundingStatus.valid, f"Expected valid citation, got errors: {res.errors}"
    assert res.citation is not None

    # derived_path must NOT appear in citation.location_metadata
    assert "derived_path" not in res.citation.location_metadata

    # The public RetrievalResultItem.location_metadata also must not contain derived_path
    public_item_meta = res.citation.location_metadata
    assert "derived_path" not in public_item_meta

    # Original dict must remain unmodified (no mutation)
    assert raw_meta["derived_path"] == "/Users/example/private/frame.jpg"
    assert "derived_path" in raw_meta
