"""Source upload/listing API routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.source_version import SourceVersionRead
from app.services import course_service
from app.services.file_storage import UnsupportedFileTypeError, store_source, list_sources

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
