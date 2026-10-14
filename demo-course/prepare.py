"""Disposable demo only. Run from the repository root; see docs/phase11/demo-guide.md."""
import argparse
import asyncio
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import uuid

import fitz
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "evaluation")]
from conceptlens_eval.database import disposable_database, validate_admin, validate_disposable


def build_source(destination: Path) -> None:
    """Generate real text pages plus an embedded raster diagram using existing PyMuPDF."""
    with fitz.open() as document:
        for section in (ROOT / "demo-course/cpu-scheduling.md").read_text().split("# ")[1:]:
            page = document.new_page()
            assert page.insert_textbox(fitz.Rect(48, 48, 547, 790), section.strip(), fontsize=14) >= 0
        with fitz.open() as drawing:
            page = drawing.new_page(width=700, height=400)
            for y, text in [(40, "SRTF decision at an arrival"), (110, "Running: burst minus executed CPU time"),
                            (180, "Newcomer: burst (no execution yet)"), (250, "Choose the smallest remaining time"),
                            (320, "Tie: arrival, then input order")]:
                page.draw_rect(fitz.Rect(30, y-20, 670, y+25), color=(.2, .4, .6))
                page.insert_text((45, y+5), text, fontsize=20)
            image = page.get_pixmap().tobytes("png")
        page = document.new_page()
        page.insert_image(fitz.Rect(35, 100, 560, 400), stream=image)
        document.set_metadata({"title": "CPU Scheduling: General Rules", "author": "ConceptLens demo material"})
        document.save(destination, no_new_id=True)


def server_environment(url: str, storage: Path, with_provider: bool) -> dict[str, str]:
    validate_disposable(url)
    env = dict(os.environ)
    for name in ("TESTING", "USE_FAKE_EMBEDDING"):
        env.pop(name, None)
    # Empty process values override any normal application .env configuration.
    for suffix in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "VISION_MODEL"):
        key = "CONCEPTLENS_" + suffix
        env[key] = os.environ.get(key, "") if with_provider else ""
    if with_provider and not all(env["CONCEPTLENS_" + key].strip() for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")):
        raise ValueError("Export the three LLM provider settings before --with-provider")
    env.update(CONCEPTLENS_DATABASE_URL=url, CONCEPTLENS_UPLOAD_DIR=str(storage / "uploads"),
               CONCEPTLENS_DEBUG="false")
    return env


@contextmanager
def managed_process(command: list[str], *, cwd: Path, env: dict[str, str], stdout=None):
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout,
                               stderr=subprocess.STDOUT, start_new_session=True)
    try:
        yield process
    finally:
        # Only this process's newly created group, including its Vite children.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=10)


async def curate_concepts(url: str, course: uuid.UUID, source: uuid.UUID) -> None:
    """Only metadata lacks a public authoring API; never create attempts or grades."""
    validate_disposable(url)
    from app.models import Concept, EvidenceUnit, PrerequisiteEdge
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine)() as db, db.begin():
            units = list(await db.scalars(select(EvidenceUnit).where(
                EvidenceUnit.course_id == course, EvidenceUnit.source_version_id == source)))
            concepts = []
            for page, name in enumerate(("Remaining time", "Shortest remaining time first", "Scheduling metrics"), 1):
                evidence = [unit for unit in units if (unit.location_metadata or {}).get("page_number") == page and unit.original_text]
                if not evidence:
                    raise RuntimeError("Expected authored source page was not extracted")
                concept = Concept(course_id=course, name=name, evidence_units=evidence)
                db.add(concept)
                concepts.append(concept)
            await db.flush()
            db.add(PrerequisiteEdge(course_id=course, prerequisite_concept_id=concepts[0].id,
                target_concept_id=concepts[1].id, relation_type="prerequisite", source_backed=True))
    finally:
        await engine.dispose()


async def prepare(client: httpx.AsyncClient, url: str, source_file: Path) -> dict:
    async def call(method: str, path: str, **kwargs):
        response = await client.request(method, path, **kwargs)
        if not response.is_success:
            raise RuntimeError(f"Demo API {method} {path} returned {response.status_code}; no provider response logged")
        return response.json()

    course = await call("POST", "/courses", json={"name": "CPU Scheduling — disposable demo"})
    prefix = f"/courses/{course['id']}"
    source = await call("POST", prefix + "/sources", files={"file": (source_file.name, source_file.read_bytes(), "application/pdf")})
    await call("POST", prefix + f"/sources/{source['id']}/process")
    await curate_concepts(url, uuid.UUID(course['id']), uuid.UUID(source['id']))
    indexed = await call("POST", prefix + "/retrieval/index")
    if not indexed["embedded_count"]:
        raise RuntimeError("Demo evidence was not indexed")
    found = await call("POST", prefix + "/retrieval/search", json={"query": "SRTF remaining time", "top_k": 5})
    assert found["evidence_boundary"]["status"] == "supported"
    preview = await client.get(prefix + f"/sources/{source['id']}/preview?kind=page&number=2")
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/png"
    graph = await call("GET", prefix + "/concept-evidence")
    assert len(graph["concepts"]) == 3 and all(c["citations"] for c in graph["concepts"])
    assert len(graph["prerequisites"]) == 1 and graph["prerequisites"][0]["source_backed"]
    report = await call("GET", prefix + f"/learners/{uuid.uuid4()}/assessment-report")
    assert report["attempt_count"] == 0 and len(report["untested"]) == 3
    evidence = await call("GET", prefix + f"/sources/{source['id']}/evidence")
    visual = next(e for e in evidence if e["asset_extracted"])
    assert visual["semantic_state"] == "not_interpreted" and visual["semantic_description"] is None
    asset = await client.get(visual["asset_url"])
    assert asset.status_code == 200 and asset.headers["content-type"] == "image/png"
    return {"course_id": course["id"], "source_id": source["id"], "index": indexed,
            "retrieval": "supported", "exact_page_preview": "passed", "curated_concepts": 3,
            "source_backed_prerequisites": 1, "untested_concepts": 3, "learner_attempts": 0,
            "visual_asset": "extracted, not interpreted", "visual_evidence_id": visual["evidence_unit_id"]}


async def run(args) -> dict:
    # No application DB fallback, and no arbitrary existing API/database target.
    admin = os.environ.get("CONCEPTLENS_EVAL_ADMIN_URL", "")
    validate_admin(admin)
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", args.port))
    events: list[dict] = []
    result = {"label": "DISPOSABLE DEMO ACCEPTANCE — NOT MODEL QUALITY", "events": events}
    try:
        async with disposable_database(admin, events) as url:
            with tempfile.TemporaryDirectory(prefix="conceptlens_phase11_") as directory:
                temp = Path(directory)
                source = temp / "cpu-scheduling.pdf"
                build_source(source)
                env = server_environment(url, temp, args.with_provider)
                with (temp / "backend.log").open("w") as log, managed_process(
                    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
                    cwd=ROOT / "backend", env=env, stdout=log,
                ) as backend:
                    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{args.port}", timeout=180, trust_env=False) as client:
                        for _ in range(100):
                            if backend.poll() is not None:
                                raise RuntimeError("Disposable backend failed to start")
                            try:
                                if (await client.get("/health")).status_code == 200:
                                    break
                            except httpx.ConnectError:
                                pass
                            await asyncio.sleep(.1)
                        else:
                            raise RuntimeError("Disposable backend startup timed out")
                        result.update(await prepare(client, url, source))
                        if not args.with_provider:
                            prefix = f"/courses/{result['course_id']}"
                            for route, payload in [("ask", {"question": "Explain SRTF remaining time"}),
                                                   ("assessments/generate", {"focus": "SRTF remaining time", "count": 1})]:
                                response = await client.post(prefix + "/" + route, json=payload)
                                assert response.status_code == 503, f"Expected unconfigured {route} boundary"
                            response = await client.post(prefix + f"/evidence/{result['visual_evidence_id']}/interpret")
                            assert response.status_code == 503
                            result["unconfigured_provider_boundary"] = "Ask, assessment and visual interpretation returned 503"
                    print(json.dumps(result), flush=True)
                    if args.browser_smoke:
                        browser_env = {**env, "CI": "1", "CONCEPTLENS_LIVE_SMOKE": "1",
                            "CONCEPTLENS_EXPECT_UNCONFIGURED": "0" if args.with_provider else "1",
                            "CONCEPTLENS_API_PROXY_TARGET": f"http://127.0.0.1:{args.port}"}
                        with managed_process(["npm", "run", "test:e2e", "--", "--grep", "live backend:",
                            "--output", str(temp / "playwright")], cwd=ROOT / "frontend", env=browser_env) as browser:
                            code = await asyncio.to_thread(browser.wait, timeout=240)
                            if code:
                                raise RuntimeError("Live browser smoke failed")
                        result["live_browser"] = "passed"
                    if args.serve:
                        print(f"Disposable backend ready on 127.0.0.1:{args.port}. Start Vite with CONCEPTLENS_API_PROXY_TARGET set to this URL. Ctrl-C cleans up.", flush=True)
                        await asyncio.Event().wait()
    finally:
        print(json.dumps({"cleanup_events": events}), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--serve", action="store_true")
    mode.add_argument("--browser-smoke", action="store_true")
    parser.add_argument("--with-provider", action="store_true", help="Use explicitly exported real provider settings")
    parser.add_argument("--port", type=int, default=8100, choices=range(1024, 65536), metavar="PORT")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        # Do not expose SQL/driver/provider exceptions, which may contain secrets.
        print(f"Demo setup failed ({type(exc).__name__}); check configuration, local model cache and available ports. No credentials logged.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
