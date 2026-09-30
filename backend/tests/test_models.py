"""Tests for database model relationships and constraints."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Concept,
    Course,
    EvidenceUnit,
    ExtractionStatus,
    Modality,
    PrerequisiteEdge,
    ProcessingStatus,
    SourceType,
    SourceVersion,
)


# ---- helpers ----

async def _create_course(db: AsyncSession, name: str = "Test Course") -> Course:
    course = Course(name=name)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course


async def _create_source_version(db: AsyncSession, course: Course) -> SourceVersion:
    sv = SourceVersion(
        course_id=course.id,
        original_filename="test.pdf",
        file_hash="a" * 64,
        mime_type="application/pdf",
        source_type=SourceType.pdf,
        storage_path="/fake/path/test.pdf",
        processing_status=ProcessingStatus.uploaded,
    )
    db.add(sv)
    await db.commit()
    await db.refresh(sv)
    return sv


# ---- SourceVersion relationships ----


@pytest.mark.asyncio
async def test_source_version_belongs_to_course(db_session: AsyncSession):
    course = await _create_course(db_session)
    sv = await _create_source_version(db_session, course)

    assert sv.course_id == course.id

    # Refresh to load relationship
    await db_session.refresh(course, ["source_versions"])
    assert len(course.source_versions) == 1
    assert course.source_versions[0].id == sv.id


# ---- EvidenceUnit / Concept many-to-many ----


@pytest.mark.asyncio
async def test_evidence_unit_concept_many_to_many(db_session: AsyncSession):
    course = await _create_course(db_session)
    sv = await _create_source_version(db_session, course)

    # Create two concepts
    c1 = Concept(course_id=course.id, name="Linear Algebra")
    c2 = Concept(course_id=course.id, name="Calculus")
    db_session.add_all([c1, c2])
    await db_session.commit()
    await db_session.refresh(c1)
    await db_session.refresh(c2)

    # Create an evidence unit linked to both concepts
    eu = EvidenceUnit(
        course_id=course.id,
        source_version_id=sv.id,
        modality=Modality.text,
        original_text="Eigenvalues require both linear algebra and calculus.",
        extraction_status=ExtractionStatus.pending,
        location_metadata={"page_index": 5},
    )
    eu.concepts.append(c1)
    eu.concepts.append(c2)
    db_session.add(eu)
    await db_session.commit()
    await db_session.refresh(eu, ["concepts"])

    assert len(eu.concepts) == 2
    concept_names = {c.name for c in eu.concepts}
    assert concept_names == {"Linear Algebra", "Calculus"}

    # Verify reverse direction
    await db_session.refresh(c1, ["evidence_units"])
    assert len(c1.evidence_units) == 1
    assert c1.evidence_units[0].id == eu.id


# ---- PrerequisiteEdge ----


@pytest.mark.asyncio
async def test_prerequisite_edge(db_session: AsyncSession):
    course = await _create_course(db_session)

    c1 = Concept(course_id=course.id, name="Algebra")
    c2 = Concept(course_id=course.id, name="Calculus")
    db_session.add_all([c1, c2])
    await db_session.commit()
    await db_session.refresh(c1)
    await db_session.refresh(c2)

    edge = PrerequisiteEdge(
        course_id=course.id,
        prerequisite_concept_id=c1.id,
        target_concept_id=c2.id,
        relation_type="requires",
        confidence=0.95,
        source_backed=True,
    )
    db_session.add(edge)
    await db_session.commit()
    await db_session.refresh(edge)

    assert edge.prerequisite_concept_id == c1.id
    assert edge.target_concept_id == c2.id
    assert edge.relation_type == "requires"
    assert edge.source_backed is True


@pytest.mark.asyncio
async def test_self_prerequisite_rejected(db_session: AsyncSession):
    """A concept must not be its own prerequisite (CHECK constraint).

    SQLite enforces CHECK constraints, so this test works in-memory.
    """
    course = await _create_course(db_session)
    concept = Concept(course_id=course.id, name="Loop")
    db_session.add(concept)
    await db_session.commit()
    await db_session.refresh(concept)

    edge = PrerequisiteEdge(
        course_id=course.id,
        prerequisite_concept_id=concept.id,
        target_concept_id=concept.id,
        relation_type="requires",
        source_backed=False,
    )
    db_session.add(edge)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
