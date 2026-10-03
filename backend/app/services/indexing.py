import uuid
import hashlib
from typing import List, Optional, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.evidence_unit import EvidenceUnit, ExtractionStatus
from app.services.embedding_provider import get_embedding_provider
from app.services.searchable_text import build_canonical_searchable_text, get_searchable_text_hash
from app.core.config import settings

async def index_evidence_units(session: AsyncSession, course_id: uuid.UUID) -> Dict[str, int]:
    """
    Indexes unindexed or changed evidence units for a course.
    Returns statistics about the indexing process.
    """
    provider = get_embedding_provider()
    batch_size = settings.embedding_batch_size

    # 1. Fetch ALL extracted evidence units for the course
    stmt = select(EvidenceUnit).where(
        and_(
            EvidenceUnit.course_id == course_id,
            EvidenceUnit.extraction_status == ExtractionStatus.extracted
        )
    )
    result = await session.execute(stmt)
    units = result.scalars().all()

    total_evidence = len(units)
    searchable_evidence = 0
    embedded_count = 0
    skipped_unchanged_count = 0
    skipped_no_text_count = 0

    if not units:
        return {
            "total_evidence": 0,
            "searchable_evidence": 0,
            "embedded_count": 0,
            "skipped_unchanged_count": 0,
            "skipped_no_text_count": 0
        }

    to_embed_units = []
    to_embed_texts = []

    for unit in units:
        # Build canonical searchable text
        canonical_text = build_canonical_searchable_text(
            original_text=unit.original_text,
            extracted_description=unit.extracted_description,
            topic=unit.topic,
            subtopic=unit.subtopic
        )

        if not canonical_text:
            skipped_no_text_count += 1
            if unit.embedding or unit.embedding_content_hash or unit.embedding_model:
                unit.embedding = None
                unit.embedding_content_hash = None
                unit.embedding_model = None
            continue

        searchable_evidence += 1
        content_hash = get_searchable_text_hash(canonical_text)

        # Check if already embedded with same content and model
        if (unit.embedding is not None
            and unit.embedding_content_hash == content_hash
            and unit.embedding_model == provider.model_name):
            skipped_unchanged_count += 1
            continue

        # Needs embedding
        unit.embedding_content_hash = content_hash
        unit.embedding_model = provider.model_name
        to_embed_units.append(unit)
        to_embed_texts.append(canonical_text)

    # Batch process embedding calls
    for i in range(0, len(to_embed_texts), batch_size):
        batch_texts = to_embed_texts[i : i + batch_size]
        batch_units = to_embed_units[i : i + batch_size]

        batch_embeddings = provider.embed_texts(batch_texts)

        for unit, embedding in zip(batch_units, batch_embeddings):
            unit.embedding = embedding
            embedded_count += 1

    await session.commit()

    return {
        "total_evidence": total_evidence,
        "searchable_evidence": searchable_evidence,
        "embedded_count": embedded_count,
        "skipped_unchanged_count": skipped_unchanged_count,
        "skipped_no_text_count": skipped_no_text_count
    }