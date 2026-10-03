import uuid
from typing import List, Dict, Any, Optional
import os

from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.evidence_unit import Modality

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

    fused_score: float
    dense_rank: Optional[int] = None
    lexical_rank: Optional[int] = None
    dense_distance: Optional[float] = None
    lexical_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    results: List[RetrievalResultItem]

class IndexingResponse(BaseModel):
    total_evidence: int
    searchable_evidence: int
    embedded_count: int
    skipped_unchanged_count: int
    skipped_no_text_count: int
