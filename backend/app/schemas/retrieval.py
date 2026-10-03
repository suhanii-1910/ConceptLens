import uuid
import enum
from typing import List, Dict, Any, Optional
import os

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.evidence_unit import Modality
from app.models.source_version import SourceType

class GroundingStatus(str, enum.Enum):
    valid = "valid"
    invalid = "invalid"

class CitationErrorCode(str, enum.Enum):
    wrong_course = "wrong_course"
    source_mismatch = "source_mismatch"
    source_not_ready = "source_not_ready"
    evidence_not_extracted = "evidence_not_extracted"
    missing_location_metadata = "missing_location_metadata"
    unsupported_source_type = "unsupported_source_type"
    missing_locator = "missing_locator"
    invalid_locator = "invalid_locator"
    inconsistent_locator = "inconsistent_locator"
    invalid_bounding_box = "invalid_bounding_box"
    invalid_timestamp = "invalid_timestamp"
    timestamp_out_of_bounds = "timestamp_out_of_bounds"
    invalid_page = "invalid_page"
    invalid_slide = "invalid_slide"
    invalid_frame = "invalid_frame"
    entity_missing = "entity_missing"

class Citation(BaseModel):
    evidence_unit_id: uuid.UUID
    course_id: uuid.UUID
    source_version_id: uuid.UUID
    source_filename: str
    source_type: SourceType
    modality: Modality
    locator: Dict[str, Any]
    location_metadata: Dict[str, Any]
    locator_label: str

    model_config = ConfigDict(from_attributes=True)

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=1, le=50)
    modalities: Optional[List[Modality]] = None
    source_version_ids: Optional[List[uuid.UUID]] = None

    @field_validator("query")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("Query string cannot be whitespace-only.")
        return v

class RetrievalResultItem(BaseModel):
    evidence_unit_id: uuid.UUID
    course_id: uuid.UUID
    source_version_id: uuid.UUID
    source_filename: str
    modality: Modality

    original_text: Optional[str] = None
    extracted_description: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    location_metadata: Optional[Dict[str, Any]] = None

    fused_score: float = 0.0
    dense_rank: Optional[int] = None
    lexical_rank: Optional[int] = None
    dense_distance: Optional[float] = None
    lexical_score: Optional[float] = None

    grounding_status: GroundingStatus = GroundingStatus.invalid
    citation: Optional[Citation] = None
    grounding_errors: List[CitationErrorCode] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    results: List[RetrievalResultItem]

class IndexingResponse(BaseModel):
    total_evidence: int
    searchable_evidence: int
    embedded_count: int
    skipped_unchanged_count: int
    skipped_no_text_count: int
