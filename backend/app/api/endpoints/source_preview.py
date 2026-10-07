import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Response, Request, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.source_preview import SourceLocation
from app.services import source_preview as service
from app.services.file_storage import _safe_filename

router=APIRouter(prefix='/courses/{course_id}/sources/{source_id}',tags=['source preview'])
HEADERS={'X-Content-Type-Options':'nosniff','Cache-Control':'private, no-store','Content-Security-Policy':"default-src 'none'; sandbox"}

@router.get('/file')
async def source_file(course_id:uuid.UUID,source_id:uuid.UUID,request:Request,db:AsyncSession=Depends(get_db)):
    if request.query_params:
        raise HTTPException(422, "File endpoint accepts source identity only")
    source,path=await service.resolve_source(db,course_id,source_id)
    return FileResponse(path,media_type=service.MIME[source.source_type.value],filename=_safe_filename(source.original_filename),
        content_disposition_type='inline' if source.source_type.value in {'pdf','video'} else 'attachment',headers=HEADERS)

@router.get('/location')
async def source_location(course_id:uuid.UUID,source_id:uuid.UUID,location:Annotated[SourceLocation,Query()],db:AsyncSession=Depends(get_db)):
    source,path=await service.resolve_source(db,course_id,source_id)
    info=service.validate_location(path,source.source_type.value,location)
    base=f'/courses/{course_id}/sources/{source_id}'
    params='&'.join(f'{k}={v}' for k,v in location.model_dump(exclude_none=True).items())
    return dict(source_id=source.id,source_type=source.source_type,filename=source.original_filename,
        locator=location.model_dump(exclude_none=True),file_url=base+'/file',
        preview_url=base+'/preview?'+params if source.source_type.value!='video' else None,
        preview_note='Slide preview uses original text, images, tables and basic shapes. Grouped graphics, charts, styling and Office effects may be omitted or simplified. Download the original for full fidelity.' if source.source_type.value=='pptx' else None,**info)

@router.get('/preview')
async def preview(course_id:uuid.UUID,source_id:uuid.UUID,location:Annotated[SourceLocation,Query()],db:AsyncSession=Depends(get_db)):
    from fastapi import HTTPException
    source,path=await service.resolve_source(db,course_id,source_id)
    service.validate_location(path,source.source_type.value,location)
    if location.kind=='time': raise HTTPException(422,'Use the video file endpoint with playback seeking')
    data=service.pdf_page(path,location.number) if location.kind=='page' else service.slide_preview(path,location.number)[0]
    return Response(data,media_type='image/png',headers=HEADERS)
