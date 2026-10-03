import uuid
from typing import List, Dict, Any, Protocol, Optional
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import joinedload
import sqlalchemy as sa

from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import SourceVersion, ProcessingStatus
from app.services.embedding_provider import get_embedding_provider
from app.services.searchable_text import get_postgresql_fts_expression


def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
    k: int = 60,
    dense_weight: float = 1.0,
    lexical_weight: float = 1.0
) -> List[Dict[str, Any]]:
    """
    Combines two ranked lists using Reciprocal Rank Fusion (RRF).
    vector_results: items should have 'item', 'distance'
    keyword_results: items should have 'item', 'score'
    """
    items_map: Dict[uuid.UUID, Dict[str, Any]] = {}

    # Process vector results
    for rank, res in enumerate(vector_results, 1):
        uid = res['item'].id
        items_map[uid] = {
            "item": res['item'],
            "fused_score": dense_weight / (k + rank),
            "dense_rank": rank,
            "lexical_rank": None,
            "dense_distance": res.get("distance"),
            "lexical_score": None
        }

    # Process keyword results (FTS)
    for rank, res in enumerate(keyword_results, 1):
        uid = res['item'].id
        if uid not in items_map:
            items_map[uid] = {
                "item": res['item'],
                "fused_score": lexical_weight / (k + rank),
                "dense_rank": None,
                "lexical_rank": rank,
                "dense_distance": None,
                "lexical_score": res.get("score")
            }
        else:
            items_map[uid]["fused_score"] += lexical_weight / (k + rank)
            items_map[uid]["lexical_rank"] = rank
            items_map[uid]["lexical_score"] = res.get("score")

    fused = list(items_map.values())
    # Deterministic tie resolution: fused_score DESC, ID DESC
    fused.sort(key=lambda x: (x["fused_score"], str(x["item"].id)), reverse=True)
    return fused


class RetrievalBackend(Protocol):
    async def dense_candidates(
        self, session: AsyncSession, course_id: uuid.UUID, query_embedding: List[float],
        top_k: int, modalities: Optional[List[Modality]], source_version_ids: Optional[List[uuid.UUID]]
    ) -> List[Dict[str, Any]]:
        ...

    async def lexical_candidates(
        self, session: AsyncSession, course_id: uuid.UUID, query: str,
        top_k: int, modalities: Optional[List[Modality]], source_version_ids: Optional[List[uuid.UUID]]
    ) -> List[Dict[str, Any]]:
        ...


class PostgresRetrievalBackend(RetrievalBackend):
    def _build_filters(self, course_id, modalities, source_version_ids):
        filters = [
            EvidenceUnit.course_id == course_id,
            EvidenceUnit.extraction_status == ExtractionStatus.extracted,
            EvidenceUnit.source_version.has(SourceVersion.processing_status == ProcessingStatus.ready)
        ]
        if modalities:
            filters.append(EvidenceUnit.modality.in_(modalities))
        if source_version_ids:
            filters.append(EvidenceUnit.source_version_id.in_(source_version_ids))
        return filters

    async def dense_candidates(
        self, session: AsyncSession, course_id: uuid.UUID, query_embedding: List[float],
        top_k: int, modalities: Optional[List[Modality]], source_version_ids: Optional[List[uuid.UUID]]
    ) -> List[Dict[str, Any]]:
        filters = self._build_filters(course_id, modalities, source_version_ids)
        filters.append(EvidenceUnit.embedding.is_not(None))

        stmt = (
            select(EvidenceUnit, EvidenceUnit.embedding.cosine_distance(query_embedding).label("distance"))
            .options(joinedload(EvidenceUnit.source_version))
            .where(and_(*filters))
            .order_by(sa.asc("distance"))
            .limit(top_k * 2)
        )
        rows = (await session.execute(stmt)).all()
        return [{"item": row[0], "distance": float(row[1])} for row in rows]

    async def lexical_candidates(
        self, session: AsyncSession, course_id: uuid.UUID, query: str,
        top_k: int, modalities: Optional[List[Modality]], source_version_ids: Optional[List[uuid.UUID]]
    ) -> List[Dict[str, Any]]:
        filters = self._build_filters(course_id, modalities, source_version_ids)

        tsquery = func.websearch_to_tsquery('english', query)
        canonical_text_expr = get_postgresql_fts_expression(EvidenceUnit)
        searchable_vector = func.to_tsvector('english', canonical_text_expr)
        rank_func = func.ts_rank(searchable_vector, tsquery)

        stmt = (
            select(EvidenceUnit, rank_func.label("rank"))
            .options(joinedload(EvidenceUnit.source_version))
            .where(and_(*filters, searchable_vector.op('@@')(tsquery)))
            .order_by(sa.desc("rank"))
            .limit(top_k * 2)
        )
        rows = (await session.execute(stmt)).all()
        return [{"item": row[0], "score": float(row[1])} for row in rows]


class FakeRetrievalBackend(RetrievalBackend):
    def _build_filters(self, course_id, modalities, source_version_ids):
        filters = [
            EvidenceUnit.course_id == course_id,
            EvidenceUnit.extraction_status == ExtractionStatus.extracted,
            EvidenceUnit.source_version.has(SourceVersion.processing_status == ProcessingStatus.ready)
        ]
        if modalities:
            filters.append(EvidenceUnit.modality.in_(modalities))
        if source_version_ids:
            filters.append(EvidenceUnit.source_version_id.in_(source_version_ids))
        return filters

    async def dense_candidates(
        self, session: AsyncSession, course_id: uuid.UUID, query_embedding: List[float],
        top_k: int, modalities: Optional[List[Modality]], source_version_ids: Optional[List[uuid.UUID]]
    ) -> List[Dict[str, Any]]:
        filters = self._build_filters(course_id, modalities, source_version_ids)
        filters.append(EvidenceUnit.embedding.is_not(None))

        stmt = select(EvidenceUnit).options(joinedload(EvidenceUnit.source_version)).where(and_(*filters))
        rows = (await session.execute(stmt)).scalars().all()
        # Mock logic: sort by ID to be deterministic in tests
        rows.sort(key=lambda u: str(u.id))
        return [{"item": row, "distance": float(0.1 * i)} for i, row in enumerate(rows[:top_k * 2])]

    async def lexical_candidates(
        self, session: AsyncSession, course_id: uuid.UUID, query: str,
        top_k: int, modalities: Optional[List[Modality]], source_version_ids: Optional[List[uuid.UUID]]
    ) -> List[Dict[str, Any]]:
        filters = self._build_filters(course_id, modalities, source_version_ids)
        stmt = (
            select(EvidenceUnit)
            .options(joinedload(EvidenceUnit.source_version))
            .where(and_(
                *filters,
                or_(
                    EvidenceUnit.original_text.ilike(f"%{query}%"),
                    EvidenceUnit.extracted_description.ilike(f"%{query}%"),
                    EvidenceUnit.topic.ilike(f"%{query}%"),
                    EvidenceUnit.subtopic.ilike(f"%{query}%")
                )
            ))
        )
        rows = (await session.execute(stmt)).scalars().all()
        rows.sort(key=lambda u: str(u.id))
        return [{"item": row, "score": float(1.0 - (0.1 * i))} for i, row in enumerate(rows[:top_k * 2])]


def get_retrieval_backend(force_fake: bool = False) -> RetrievalBackend:
    if force_fake or os.getenv("TESTING") == "1":
        return FakeRetrievalBackend()
    return PostgresRetrievalBackend()


async def hybrid_search(
    session: AsyncSession,
    course_id: uuid.UUID,
    query: str,
    top_k: int = 10,
    modalities: Optional[List[Modality]] = None,
    source_version_ids: Optional[List[uuid.UUID]] = None
) -> List[Dict[str, Any]]:

    provider = get_embedding_provider()
    query_embedding = provider.embed_text(query)

    backend = get_retrieval_backend()

    vector_results = await backend.dense_candidates(
        session, course_id, query_embedding, top_k, modalities, source_version_ids
    )
    keyword_results = await backend.lexical_candidates(
        session, course_id, query, top_k, modalities, source_version_ids
    )

    fused_results = reciprocal_rank_fusion(vector_results, keyword_results)

    final_results = []
    for res in fused_results[:top_k]:
        item: EvidenceUnit = res["item"]
        final_results.append({
            "evidence_unit_id": item.id,
            "course_id": item.course_id,
            "source_version_id": item.source_version_id,
            "source_filename": item.source_version.original_filename if item.source_version else "",
            "modality": item.modality,
            "original_text": item.original_text,
            "extracted_description": item.extracted_description,
            "topic": item.topic,
            "subtopic": item.subtopic,
            "location_metadata": item.location_metadata,
            "fused_score": res["fused_score"],
            "dense_rank": res["dense_rank"],
            "lexical_rank": res["lexical_rank"],
            "dense_distance": res["dense_distance"],
            "lexical_score": res["lexical_score"]
        })

    return final_results
