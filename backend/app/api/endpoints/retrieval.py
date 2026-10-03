import uuid
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.schemas.retrieval import SearchRequest, SearchResponse, IndexingResponse
from app.services.retriever import hybrid_search
from app.services.indexing import index_evidence_units
from app.models.course import Course
from app.models.evidence_unit import EvidenceUnit, ExtractionStatus

router = APIRouter(prefix="/courses/{course_id}/retrieval", tags=["retrieval"])

async def _verify_course(db: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await db.scalar(select(Course).where(Course.id == course_id))
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found"
        )
    return course

@router.post("/index", response_model=IndexingResponse)
async def index_course_evidence(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Index all evidence units for a specific course.
    """
    await _verify_course(db, course_id)
    
    try:
        result = await index_evidence_units(db, course_id)
        
        if isinstance(result, int):
            # Fallback if index_evidence_units returns an int (old signature)
            return IndexingResponse(
                total_evidence=0,
                searchable_evidence=0,
                embedded_count=result,
                skipped_unchanged_count=0,
                skipped_no_text_count=0
            )
        
        return IndexingResponse(
            total_evidence=result.get("total_evidence", 0),
            searchable_evidence=result.get("searchable_evidence", 0),
            embedded_count=result.get("embedded_count", 0),
            skipped_unchanged_count=result.get("skipped_unchanged_count", 0),
            skipped_no_text_count=result.get("skipped_no_text_count", 0)
        )
        
    except Exception:
        logger.exception("Indexing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Indexing failed due to an internal error.",
        )

@router.post("/search", response_model=SearchResponse)
async def search_evidence(
    course_id: uuid.UUID,
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Search evidence units using a hybrid dense/lexical ranking algorithm for a specific course.
    """
    await _verify_course(db, course_id)
    
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )
        
    if request.top_k < 1 or request.top_k > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="top_k must be between 1 and 50"
        )
    
    try:
        results = await hybrid_search(
            session=db,
            course_id=course_id,
            query=request.query,
            top_k=request.top_k,
            modalities=request.modalities,
            source_version_ids=request.source_version_ids
        )
        from app.services.citation_grounding import ground_retrieval_results
        from app.services.evidence_boundary import evaluate_evidence_boundary
        grounded = await ground_retrieval_results(db, course_id, results)
        boundary = evaluate_evidence_boundary(grounded)
        return {
            "results": grounded,
            "evidence_boundary": {
                "status": boundary.status.value,
                "reason": boundary.reason.value,
                "should_decline": boundary.should_decline,
                "message": boundary.message,
                "candidate_count": boundary.candidate_count,
                "relevant_candidate_count": boundary.relevant_candidate_count,
                "usable_candidate_count": boundary.usable_candidate_count,
                "usable_evidence_unit_ids": [str(uid) for uid in boundary.usable_evidence_unit_ids],
            },
        }
    except Exception:
        logger.exception("Search failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed due to an internal error.",
        )
