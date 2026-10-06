"""Subprocess boundary keeps RAGAS dependencies out of the backend interpreter."""
import json
import os
import subprocess
from pathlib import Path
from .common import ROOT, FIXTURE, PENDING

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def provider_environment() -> dict:
    from app.core.config import settings
    values = {"BASE_URL": settings.llm_base_url, "API_KEY": settings.llm_api_key, "MODEL": settings.llm_model,
              "EMBEDDING_MODEL": None}
    return {"CONCEPTLENS_EVAL_" + k: os.getenv("CONCEPTLENS_EVAL_" + k) or v or "" for k, v in values.items()}


def pending() -> dict:
    return {"label": PENDING, "status": "pending", "reason": "REAL FRAMEWORK RESULTS: PENDING PROVIDER CONFIGURATION",
            "scores": {k: None for k in METRICS}, "raw": {}}


def score(sample: dict, *, fixture: bool = False, fixture_verdict: int = 1, environment: dict | None = None) -> dict:
    env = provider_environment() if environment is None else environment
    if not fixture and not all(env.get("CONCEPTLENS_EVAL_" + k) for k in ("BASE_URL", "API_KEY", "MODEL", "EMBEDDING_MODEL")):
        return pending()
    executable = ROOT / "evaluation/.venv-framework/bin/python"
    if not executable.is_file():
        return {"label": FIXTURE if fixture else "REAL EVALUATION RESULT", "status": "error",
                "error": "framework environment missing; see evaluation/README.md", "scores": {}, "raw": {}}
    request = {"sample": sample, "fixture": fixture, "fixture_verdict": fixture_verdict}
    try:
        result = subprocess.run([str(executable), str(Path(__file__).with_name("framework_worker.py"))],
            input=json.dumps(request), text=True, capture_output=True, timeout=300,
            env={**os.environ, **env, "RAGAS_DO_NOT_TRACK": "true"})
        if result.returncode:
            # Provider/SDK exception text can contain credentials or URLs. Do not persist it.
            return {"label": FIXTURE if fixture else "REAL EVALUATION RESULT", "status": "error",
                    "error": "framework worker failed (provider details redacted)", "scores": {}, "raw": {}}
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"label": FIXTURE if fixture else "REAL EVALUATION RESULT", "status": "error",
                "error": "framework timeout or invalid worker response", "scores": {}, "raw": {}}
