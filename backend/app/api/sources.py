"""Source upload/listing/processing API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.source_version import SourceVersion
from app.schemas.source_version import ProcessingResultRead, SourceVersionRead
from app.services import course_service
from app.services.file_storage import UnsupportedFileTypeError, store_source, list_sources
from app.services.pdf_ingestion import (
    AlreadyProcessedError,
    NotAPDFError,
    PDFProcessingError,
    process_pdf,
)

router = APIRouter(prefix="/courses/{course_id}/sources", tags=["sources"])


@router.post("", response_model=SourceVersionRead)
async def upload_source(
    course_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    # Verify the course exists
    course = await course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    try:
        sv, is_new = await store_source(db, course_id=course_id, upload=file)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        )

    from fastapi.responses import JSONResponse

    response_data = SourceVersionRead.model_validate(sv).model_dump(mode="json")
    status_code = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
    return JSONResponse(content=response_data, status_code=status_code)


@router.get("", response_model=list[SourceVersionRead])
async def list_course_sources(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[SourceVersionRead]:
    # Verify the course exists
    course = await course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    sources = await list_sources(db, course_id)
    return [SourceVersionRead.model_validate(s) for s in sources]


@router.post(
    "/{source_version_id}/process",
    response_model=ProcessingResultRead,
)
async def process_source(
    course_id: uuid.UUID,
    source_version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger PDF processing for a source version.

    Extracts text blocks, tables, and images, creating EvidenceUnit
    records with page-level provenance.

    Returns 200 if already processed, 201 on fresh processing.
    """
    # Verify the course exists
    course = await course_service.get_course(db, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {course_id} not found",
        )

    # Verify the source version exists and belongs to this course
    result = await db.execute(
        select(SourceVersion).where(
            SourceVersion.id == source_version_id,
            SourceVersion.course_id == course_id,
        )
    )
    sv = result.scalar_one_or_none()
    if sv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SourceVersion {source_version_id} not found in course {course_id}",
        )

    try:
        from app.services.source_processing import process_source as dispatch_process_source
        from app.services.source_processing import VideoNotSupportedError
        processing_result = await dispatch_process_source(db, source_version=sv)
    except NotAPDFError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except VideoNotSupportedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except AlreadyProcessedError as exc:
        # Return existing result with 200
        from fastapi.responses import JSONResponse

        data = ProcessingResultRead(**exc.result.__dict__).model_dump(mode="json")
        return JSONResponse(content=data, status_code=status.HTTP_200_OK)
    except PDFProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PDF processing failed: {exc}",
        )
    except Exception as exc:
        # We need to catch PPTXProcessingError without importing it directly at the top since it might cause circular imports if placed incorrectly, or we can just import it. Let's import it here.
        from app.services.pptx_ingestion import PPTXProcessingError, AlreadyProcessedError as PPTXAlreadyProcessedError, NotAPPTXError
        if isinstance(exc, PPTXProcessingError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"PPTX processing failed: {exc}",
            )
        if isinstance(exc, NotAPPTXError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        if isinstance(exc, PPTXAlreadyProcessedError):
            from fastapi.responses import JSONResponse
            data = ProcessingResultRead(**exc.result.__dict__).model_dump(mode="json")
            return JSONResponse(content=data, status_code=status.HTTP_200_OK)

        from app.services.video_ingestion import VideoProcessingError, AlreadyProcessedError as VideoAlreadyProcessedError, NotAVideoError
        if isinstance(exc, VideoProcessingError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Video processing failed: {exc}",
            )
        if isinstance(exc, NotAVideoError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        if isinstance(exc, VideoAlreadyProcessedError):
            from fastapi.responses import JSONResponse
            data = ProcessingResultRead(**exc.result.__dict__).model_dump(mode="json")
            return JSONResponse(content=data, status_code=status.HTTP_200_OK)

        raise exc

    from fastapi.responses import JSONResponse

    data = ProcessingResultRead(**processing_result.__dict__).model_dump(mode="json")
    return JSONResponse(content=data, status_code=status.HTTP_201_CREATED)
