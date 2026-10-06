"""Actual ingestion -> hybrid retrieval -> evidence boundary -> grounded Ask.

No synthetic provider is accepted here. Fixture scoring lives only in tests.
"""
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .common import REAL, PENDING
from .database import disposable_database, validate_disposable
from .dataset import Manifest, resolve_source
from . import framework
from .metrics import aggregate, case_metrics, failures


def normalize_locator(kind: str, raw: dict) -> dict:
    if kind == "pdf" and "page_number" in raw: return {"kind":"page","number":raw["page_number"]}
    if kind == "pptx" and "slide_number" in raw: return {"kind":"slide","number":raw["slide_number"]}
    if kind == "video":
        if "start_seconds" in raw and "end_seconds" in raw:
            return {"kind":"time","start":float(raw["start_seconds"]),"end":float(raw["end_seconds"])}
        if "timestamp_seconds" in raw:
            return {"kind":"time","start":float(raw["timestamp_seconds"]),"end":float(raw["timestamp_seconds"])}
    return {}  # Never invent a missing location.


def summarize(manifest: Manifest, split: str, rows: list[dict], label: str) -> dict:
    cases = [c for c in manifest.cases if c.split == split]
    by_id = {c.case_id:c for c in cases}
    for row in rows:
        case = by_id[row["case_id"]]
        row["custom"] = case_metrics(case,row)
        row.update(case_type=case.case_type, modality=case.modality, split=case.split,
                   expected_supported=case.supported, expected=[e.model_dump() for e in case.expected],
                   reference_answer=case.reference_answer)
    def group_summary(group):
        selected = [r for r in rows if r["case_id"] in {c.case_id for c in group}]
        return {**aggregate(group,selected), "framework_metrics":framework_summary(selected)}
    return {"label":label,"dataset_version":manifest.version,"split":split,"cases":rows,
        "framework_metrics":framework_summary(rows),"custom_metrics":aggregate(cases,rows),
        "by_modality":{mod:group_summary([c for c in cases if c.modality==mod]) for mod in sorted({c.modality for c in cases})},
        "by_case_type":{kind:group_summary([c for c in cases if c.case_type==kind]) for kind in sorted({c.case_type for c in cases})},
        "failures":[f for row in rows for f in failures(by_id[row["case_id"]],row)]}


def framework_summary(rows):
    scores = {}
    for metric in framework.METRICS:
        values = [r["framework"]["scores"].get(metric) for r in rows if r.get("framework",{}).get("label")==REAL]
        values = [v for v in values if v is not None]
        scores[metric] = {"mean":sum(values)/len(values) if values else None,"n":len(values)}
    return scores


async def run(manifest: Manifest, manifest_path: Path, split: str, admin_url: str | None) -> dict:
    from app.core.config import settings
    cases = [c for c in manifest.cases if c.split==split]
    configured = bool(settings.llm_base_url and settings.llm_model and settings.llm_api_key)
    if not configured:
        rows = [{"case_id":c.case_id,"query":c.question,"status":"pending","answer":None,"citations":[],"retrieved":[],
                 "latency_seconds":None,"framework":framework.pending(),"error":"Generator provider unconfigured; no pipeline run"} for c in cases]
        result = summarize(manifest,split,rows,PENDING)
        result.update(generator_configured=False,real_pipeline_run=False,normal_development_db_touched=False,database_events=[])
        return result
    if not admin_url:
        raise ValueError("configured grounding requires CONCEPTLENS_EVAL_ADMIN_URL pointing to local /postgres; no app DB fallback")
    events, rows = [], []
    with tempfile.TemporaryDirectory(prefix="conceptlens-eval-") as storage:
        async with disposable_database(admin_url,events) as url:
            validate_disposable(url)
            with patch.object(settings,"database_url",url), patch.object(settings,"upload_dir",str(Path(storage)/"uploads")):
                engine = create_async_engine(url)
                try:
                    async with async_sessionmaker(engine,expire_on_commit=False)() as db:
                        source_map, ingestion = await seed(db,manifest,manifest_path)
                        course_id = uuid.uuid5(uuid.NAMESPACE_URL,"conceptlens-eval/grounding-course")
                        for case in cases:
                            rows.append(await ask_case(db,course_id,case,source_map))
                        # Ask has no learner writes; verify that invariant in this disposable DB.
                        from app.models.assessment import AssessmentAttempt
                        from app.models.learner_mastery import LearnerConceptMastery
                        for model in (AssessmentAttempt,LearnerConceptMastery):
                            if await db.scalar(select(func.count()).select_from(model)):
                                raise AssertionError("grounding created learner history")
                finally:
                    await engine.dispose()
    result = summarize(manifest,split,rows,REAL)
    result.update(generator_configured=True,real_pipeline_run=True,normal_development_db_touched=False,
                  database_events=events,ingestion=ingestion,evaluator_model=framework.provider_environment()["CONCEPTLENS_EVAL_MODEL"],
                  evaluator_embedding_model=framework.provider_environment()["CONCEPTLENS_EVAL_EMBEDDING_MODEL"])
    return result


async def seed(db, manifest: Manifest, manifest_path: Path):
    from app.models.course import Course
    from app.models.source_version import SourceVersion, SourceType, ProcessingStatus
    from app.services.source_processing import process_source
    from app.services.indexing import index_evidence_units
    course_id = uuid.uuid5(uuid.NAMESPACE_URL,"conceptlens-eval/grounding-course")
    db.add(Course(id=course_id,name="Phase 9 Aster benchmark"))
    await db.flush()
    records, ingestion = [], []
    for source in manifest.sources:
        row = SourceVersion(id=uuid.uuid5(course_id,source.source_id),course_id=course_id,original_filename=source.filename,
            file_hash=source.sha256,mime_type={"pdf":"application/pdf","pptx":"application/vnd.openxmlformats-officedocument.presentationml.presentation","video":"video/mp4"}[source.kind],
            source_type=SourceType(source.kind),storage_path=str((manifest_path.parent/source.path).resolve()),processing_status=ProcessingStatus.uploaded)
        db.add(row)
        await db.flush()
        result = await process_source(db,row)
        if row.processing_status != ProcessingStatus.ready:
            raise RuntimeError("source ingestion failed: " + source.source_id)
        ingestion.append({"source_id":source.source_id,"status":"ready"})
        records.append({"id":str(row.id),"filename":row.original_filename,"sha256":row.file_hash,"kind":source.kind})
    await db.commit()
    ingestion.append({"indexing":await index_evidence_units(db,course_id)})
    mapping = {resolve_source(s,records)["id"]:{**resolve_source(s,records),"source_id":s.source_id} for s in manifest.sources}
    return mapping, ingestion


async def ask_case(db, course_id, case, source_map):
    from app.schemas.ask import AskRequest
    from app.services import grounded_ask
    from app.services.evidence_boundary import only_supported_evidence
    captured = []
    original = grounded_ask.ground_retrieval_results
    async def capture(*args,**kwargs):
        result = await original(*args,**kwargs)
        captured.extend(result)
        return result
    def citation_record(citation):
        raw = citation.model_dump(mode="json")
        source = source_map.get(str(citation.source_version_id))
        return {"source_id":source["source_id"] if source else None,
            "source_sha256":source["sha256"] if source else None,
            "locator":normalize_locator(raw["source_type"],raw["locator"]),"raw":raw}
    row = {"case_id":case.case_id,"query":case.question,"status":"error","answer":None,"citations":[],"retrieved":[]}
    start = time.perf_counter()
    try:
        with patch.object(grounded_ask,"ground_retrieval_results",capture):
            response = await grounded_ask.execute_grounded_ask(db,course_id,AskRequest(question=case.question,top_k=10))
        row.update(status=response.status.value,answer=response.answer,decline_message=response.decline_message,
                   evidence_boundary=response.evidence_boundary.model_dump(mode="json"),
                   citations=[citation_record(c) for block in response.blocks for c in block.citations])
    except Exception as exc:
        row["error"] = type(exc).__name__  # no provider exception text / secrets
    row["latency_seconds"] = time.perf_counter()-start
    for item in captured:
        source = source_map.get(str(item.source_version_id))
        raw = item.model_dump(mode="json")
        row["retrieved"].append({"source_id":source["source_id"] if source else None,
            "source_sha256":source["sha256"] if source else None,"evidence_unit_id":str(item.evidence_unit_id),
            "locator":normalize_locator(source["kind"],item.citation.locator if item.citation else item.location_metadata or {}) if source else {},
            "text":item.original_text or item.extracted_description or "","raw":raw})
    contexts = only_supported_evidence(captured)[:grounded_ask.MAX_ANSWER_EVIDENCE]
    row["answer_contexts"] = [i.original_text or i.extracted_description or "" for i in contexts]
    if case.supported and row["status"]=="answered" and row["answer_contexts"]:
        row["framework"] = framework.score({"user_input":case.question,"response":row["answer"],
            "reference":case.reference_answer,"retrieved_contexts":row["answer_contexts"]})
    else:
        row["framework"] = {"label":REAL,"status":"not_applicable","scores":{},"raw":{},
                            "reason":"framework scoring requires a supported answered case with context; refusal measured separately"}
    return row
