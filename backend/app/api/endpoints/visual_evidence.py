import uuid
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.evidence_unit import EvidenceUnit
from app.services import visual_evidence as service
from app.services.llm_provider import LLMConfigurationError,LLMProviderError,InvalidLLMResponseError
from app.api.endpoints.source_preview import HEADERS

router=APIRouter(prefix='/courses/{course_id}',tags=['visual evidence'])

@router.get('/sources/{source_id}/evidence')
async def source_evidence(course_id:uuid.UUID,source_id:uuid.UUID,db:AsyncSession=Depends(get_db)):
    from app.services.source_preview import resolve_source
    await resolve_source(db,course_id,source_id)
    rows=(await db.scalars(select(EvidenceUnit).where(EvidenceUnit.course_id==course_id,EvidenceUnit.source_version_id==source_id).order_by(EvidenceUnit.id).limit(500))).all()
    result=[]
    for unit in rows:
        try:
            _,_,citation=await service.evidence(db,course_id,unit.id)
            result.append(service.public_visual(unit,citation))
        except HTTPException:continue
    return result

@router.get('/evidence/{evidence_id}')
async def get_evidence(course_id:uuid.UUID,evidence_id:uuid.UUID,db:AsyncSession=Depends(get_db)):
    unit,_,citation=await service.evidence(db,course_id,evidence_id)
    return service.public_visual(unit,citation)

@router.get('/evidence/{evidence_id}/asset')
async def asset(course_id:uuid.UUID,evidence_id:uuid.UUID,db:AsyncSession=Depends(get_db)):
    unit,_,_=await service.evidence(db,course_id,evidence_id)
    return Response(service.visual_asset(unit),media_type='image/png',headers=HEADERS)

@router.post('/evidence/{evidence_id}/interpret')
async def interpret(course_id:uuid.UUID,evidence_id:uuid.UUID,db:AsyncSession=Depends(get_db)):
    try:
        async with db.begin():result=await service.interpret(db,course_id,evidence_id)
        return result
    except (LLMConfigurationError,LLMProviderError):raise HTTPException(503,'Visual asset is available; semantic interpretation is unavailable') from None
    except InvalidLLMResponseError:raise HTTPException(502,'Visual interpretation could not be verified') from None
