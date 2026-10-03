import math
import uuid
import logging
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from sqlalchemy import select

from app.models.evidence_unit import EvidenceUnit, ExtractionStatus, Modality
from app.models.source_version import SourceVersion, SourceType, ProcessingStatus
from app.schemas.retrieval import Citation, CitationErrorCode, GroundingStatus, RetrievalResultItem

logger = logging.getLogger(__name__)

SAFE_KEYS_PDF = {"page_index", "page_number", "printed_page_label", "bounding_box", "block_index", "element_type"}
SAFE_KEYS_PPTX = {"slide_index", "slide_number", "shape_id", "shape_name", "shape_index", "bounding_box", "coordinate_unit", "slide_width", "slide_height", "element_type", "image_width", "image_height", "image_extension"}
SAFE_KEYS_TRANSCRIPT = {"element_type", "segment_index", "start_seconds", "end_seconds", "start_ms", "end_ms", "source_duration_seconds", "provider_end_seconds", "provider_end_ms", "timestamp_adjustment", "language", "timestamp_source"}
SAFE_KEYS_FRAME = {"element_type", "frame_index", "source_frame_index", "timestamp_seconds", "timestamp_ms", "timestamp_source", "image_width", "image_height", "key_frame", "selection_method", "source_duration_seconds"}

def sanitize_metadata(meta: dict, safe_keys: set) -> dict:
    if not isinstance(meta, dict):
        return {}
    return {k: v for k, v in meta.items() if k in safe_keys}

class CitationValidationResult(BaseModel):
    status: GroundingStatus
    citation: Optional[Citation] = None
    errors: List[CitationErrorCode]

def validate_bounding_box(bbox: Any) -> List[CitationErrorCode]:
    errors = []
    if bbox is not None:
        if not isinstance(bbox, list):
             errors.append(CitationErrorCode.invalid_bounding_box)
        elif len(bbox) != 4:
            errors.append(CitationErrorCode.invalid_bounding_box)
        else:
            try:
                for v in bbox:
                    if type(v) not in (int, float) or isinstance(v, bool):
                        raise ValueError
                x0, y0, x1, y1 = [float(v) for v in bbox]
                if not (math.isfinite(x0) and math.isfinite(y0) and math.isfinite(x1) and math.isfinite(y1)):
                    errors.append(CitationErrorCode.invalid_bounding_box)
                elif x1 < x0 or y1 < y0:
                    errors.append(CitationErrorCode.invalid_bounding_box)
            except (ValueError, TypeError):
                errors.append(CitationErrorCode.invalid_bounding_box)
    return errors

def validate_pdf_citation(meta: dict, filename: str) -> tuple[Optional[Dict[str, Any]], str, List[CitationErrorCode], set]:
    errors = []
    locator = {}

    page_index = meta.get("page_index")
    page_number = meta.get("page_number")

    if page_index is None or page_number is None:
        errors.append(CitationErrorCode.missing_locator)
        return None, "", errors, set()

    has_valid_index = False
    if type(page_index) is not int or isinstance(page_index, bool) or page_index < 0:
        errors.append(CitationErrorCode.invalid_page)
    else:
        has_valid_index = True

    has_valid_number = False
    if type(page_number) is not int or isinstance(page_number, bool) or page_number <= 0:
        errors.append(CitationErrorCode.invalid_page)
    else:
        has_valid_number = True

    if has_valid_index and has_valid_number:
        if page_number != page_index + 1:
            errors.append(CitationErrorCode.inconsistent_locator)
        else:
            locator["page_index"] = page_index
            locator["page_number"] = page_number

    printed_label = meta.get("printed_page_label")
    if printed_label is not None:
        locator["printed_page_label"] = printed_label

    bbox = meta.get("bounding_box")
    if bbox is not None:
        bbox_errors = validate_bounding_box(bbox)
        if bbox_errors:
            errors.extend(bbox_errors)
        else:
            locator["bounding_box"] = bbox

    if errors:
        return None, "", errors, set()

    label_page = printed_label if (printed_label is not None and str(printed_label).strip()) else str(page_number)
    label = f"{filename} · p. {label_page}"
    return locator, label, [], SAFE_KEYS_PDF

def validate_pptx_citation(meta: dict, filename: str) -> tuple[Optional[Dict[str, Any]], str, List[CitationErrorCode], set]:
    errors = []
    locator = {}

    slide_index = meta.get("slide_index")
    slide_number = meta.get("slide_number")

    if slide_index is None or slide_number is None:
        errors.append(CitationErrorCode.missing_locator)
        return None, "", errors, set()

    has_valid_index = False
    if type(slide_index) is not int or isinstance(slide_index, bool) or slide_index < 0:
        errors.append(CitationErrorCode.invalid_slide)
    else:
        has_valid_index = True

    has_valid_number = False
    if type(slide_number) is not int or isinstance(slide_number, bool) or slide_number <= 0:
        errors.append(CitationErrorCode.invalid_slide)
    else:
        has_valid_number = True

    if has_valid_index and has_valid_number:
        if slide_number != slide_index + 1:
            errors.append(CitationErrorCode.inconsistent_locator)
        else:
            locator["slide_index"] = slide_index
            locator["slide_number"] = slide_number

    shape_index = meta.get("shape_index")
    if shape_index is not None:
        if type(shape_index) is not int or isinstance(shape_index, bool) or shape_index < 0:
            errors.append(CitationErrorCode.invalid_slide)
        else:
            locator["shape_index"] = shape_index

    bbox = meta.get("bounding_box")
    if bbox is not None:
        bbox_errors = validate_bounding_box(bbox)
        if bbox_errors:
            errors.extend(bbox_errors)
        else:
            locator["bounding_box"] = bbox

    if errors:
        return None, "", errors, set()

    label = f"{filename} · slide {slide_number}"
    return locator, label, [], SAFE_KEYS_PPTX

def format_timestamp(seconds: float) -> str:
    s = int(round(seconds))
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def validate_video_transcript_citation(meta: dict, filename: str) -> tuple[Optional[Dict[str, Any]], str, List[CitationErrorCode], set]:
    errors = []
    locator = {}
    
    start = meta.get("start_seconds")
    end = meta.get("end_seconds")
    duration = meta.get("source_duration_seconds")
    
    if start is None or end is None:
        errors.append(CitationErrorCode.missing_locator)
        return None, "", errors, set()
        
    try:
        if type(start) not in (int, float) or isinstance(start, bool):
            raise TypeError
        if type(end) not in (int, float) or isinstance(end, bool):
            raise TypeError
        
        start_f = float(start)
        end_f = float(end)
        
        if not math.isfinite(start_f) or not math.isfinite(end_f):
            errors.append(CitationErrorCode.invalid_timestamp)
        elif start_f < 0:
            errors.append(CitationErrorCode.invalid_timestamp)
        elif end_f < start_f:
            errors.append(CitationErrorCode.invalid_timestamp)
        else:
            locator["start_seconds"] = start_f
            locator["end_seconds"] = end_f
            
        if duration is not None:
            if type(duration) not in (int, float) or isinstance(duration, bool):
                raise TypeError
            dur_f = float(duration)
            if not math.isfinite(dur_f) or dur_f <= 0:
                raise TypeError
            else:
                if end_f > dur_f + 1e-6:
                    errors.append(CitationErrorCode.timestamp_out_of_bounds)
                locator["source_duration_seconds"] = dur_f

    except (ValueError, TypeError):
        errors.append(CitationErrorCode.invalid_timestamp)

    if errors:
        return None, "", errors, set()

    ts_source = meta.get("timestamp_source")
    if ts_source is not None:
        locator["timestamp_source"] = ts_source

    label = f"{filename} · {format_timestamp(start_f)}–{format_timestamp(end_f)}"
    return locator, label, [], SAFE_KEYS_TRANSCRIPT

def validate_video_frame_citation(meta: dict, filename: str) -> tuple[Optional[Dict[str, Any]], str, List[CitationErrorCode], set]:
    errors = []
    locator = {}
    
    ts = meta.get("timestamp_seconds")
    if ts is None:
        errors.append(CitationErrorCode.missing_locator)
        return None, "", errors, set()

    try:
        if type(ts) not in (int, float) or isinstance(ts, bool):
            raise TypeError
        ts_f = float(ts)
        if not math.isfinite(ts_f) or ts_f < 0:
            errors.append(CitationErrorCode.invalid_timestamp)
        else:
            locator["timestamp_seconds"] = ts_f
            
        dur = meta.get("source_duration_seconds")
        if dur is not None:
            if type(dur) not in (int, float) or isinstance(dur, bool):
                raise TypeError
            dur_f = float(dur)
            if not math.isfinite(dur_f) or dur_f <= 0:
                raise TypeError
            
            if ts_f > dur_f + 1e-6:
                errors.append(CitationErrorCode.timestamp_out_of_bounds)
            locator["source_duration_seconds"] = dur_f

    except (ValueError, TypeError):
        errors.append(CitationErrorCode.invalid_timestamp)
        
    source_frame_index = meta.get("source_frame_index")
    if source_frame_index is None:
        errors.append(CitationErrorCode.missing_locator)
    else:
        if type(source_frame_index) is not int or isinstance(source_frame_index, bool) or source_frame_index < 0:
            errors.append(CitationErrorCode.invalid_frame)
        else:
            locator["source_frame_index"] = source_frame_index
            
    if errors:
        return None, "", errors, set()

    for key in ["timestamp_source", "selection_method", "image_width", "image_height"]:
        if (val := meta.get(key)) is not None:
            locator[key] = val

    label = f"{filename} · {format_timestamp(ts_f)}"
    return locator, label, [], SAFE_KEYS_FRAME

def validate_and_build_citation(
    evidence_unit: EvidenceUnit,
    source_version: SourceVersion,
    expected_course_id: uuid.UUID
) -> CitationValidationResult:
    errors = []

    if not evidence_unit or not source_version:
        return CitationValidationResult(status=GroundingStatus.invalid, errors=[CitationErrorCode.entity_missing])

    if evidence_unit.course_id != expected_course_id:
        errors.append(CitationErrorCode.wrong_course)
    if source_version.course_id != expected_course_id:
        errors.append(CitationErrorCode.wrong_course)
    if evidence_unit.source_version_id != source_version.id:
        errors.append(CitationErrorCode.source_mismatch)

    if source_version.processing_status != ProcessingStatus.ready:
        errors.append(CitationErrorCode.source_not_ready)
    
    if evidence_unit.extraction_status != ExtractionStatus.extracted:
        errors.append(CitationErrorCode.evidence_not_extracted)
        
    meta = evidence_unit.location_metadata
    if not isinstance(meta, dict):
        errors.append(CitationErrorCode.missing_location_metadata)

    filename = source_version.original_filename
    if not filename or not filename.strip():
        errors.append(CitationErrorCode.entity_missing)

    if errors:
        return CitationValidationResult(status=GroundingStatus.invalid, errors=errors)
        
    stype = source_version.source_type
    
    locator = None
    label = ""
    loc_errors = []
    safe_keys = set()
    
    if stype == SourceType.pdf:
        locator, label, loc_errors, safe_keys = validate_pdf_citation(meta, filename)
    elif stype == SourceType.pptx:
        locator, label, loc_errors, safe_keys = validate_pptx_citation(meta, filename)
    elif stype == SourceType.video:
        el_type = meta.get("element_type")
        if el_type == "transcript_segment" and evidence_unit.modality == Modality.video:
            locator, label, loc_errors, safe_keys = validate_video_transcript_citation(meta, filename)
        elif el_type == "video_frame" and evidence_unit.modality == Modality.image:
            locator, label, loc_errors, safe_keys = validate_video_frame_citation(meta, filename)
        else:
            loc_errors.append(CitationErrorCode.inconsistent_locator)
    else:
        errors.append(CitationErrorCode.unsupported_source_type)

    if loc_errors:
        errors.extend(loc_errors)
        
    if errors or not locator:
        return CitationValidationResult(status=GroundingStatus.invalid, errors=errors)
        
    sanitized_meta = sanitize_metadata(meta, safe_keys)
        
    citation = Citation(
        evidence_unit_id=evidence_unit.id,
        course_id=evidence_unit.course_id,
        source_version_id=evidence_unit.source_version_id,
        source_filename=filename,
        source_type=stype,
        modality=evidence_unit.modality,
        locator=locator,
        location_metadata=sanitized_meta,
        locator_label=label
    )
    
    return CitationValidationResult(status=GroundingStatus.valid, citation=citation, errors=[])

async def ground_retrieval_results(db_session, course_id, results: list[Any]) -> list[RetrievalResultItem]:
    if not results:
        return []
    
    items: list[RetrievalResultItem] = []
    for r in results:
        if isinstance(r, dict):
            items.append(RetrievalResultItem.model_validate(r))
        else:
            items.append(RetrievalResultItem.model_validate(r, from_attributes=True))

    source_version_ids = {item.source_version_id for item in items}
    eu_ids = {item.evidence_unit_id for item in items}
    
    q_sv = select(SourceVersion).where(SourceVersion.id.in_(source_version_ids))
    sv_res = await db_session.execute(q_sv)
    sv_map = {sv.id: sv for sv in sv_res.scalars().all()}
    
    q_eu = select(EvidenceUnit).where(EvidenceUnit.id.in_(eu_ids))
    eu_res = await db_session.execute(q_eu)
    eu_map = {eu.id: eu for eu in eu_res.scalars().all()}

    grounded_results = []
    
    for item in items:
        eu = eu_map.get(item.evidence_unit_id)
        sv = sv_map.get(item.source_version_id)
        
        if eu and sv:
            val_res = validate_and_build_citation(eu, sv, course_id)
            item.grounding_status = val_res.status
            item.citation = val_res.citation
            item.grounding_errors = val_res.errors
            if val_res.citation:
                item.location_metadata = val_res.citation.location_metadata
            else:
                item.location_metadata = None # strip unsafe if invalid
        else:
            item.grounding_status = GroundingStatus.invalid
            item.grounding_errors = [CitationErrorCode.entity_missing]
            item.location_metadata = None
            
        grounded_results.append(item)
        
    return grounded_results


def only_grounded(results: List[RetrievalResultItem]) -> List[RetrievalResultItem]:
    return [r for r in results if r.grounding_status == GroundingStatus.valid and r.citation is not None]
