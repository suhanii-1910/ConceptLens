import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import VERSION

ROOT = Path(__file__).resolve().parents[2]
REAL = "REAL EVALUATION RESULT"
SIMULATION = "SIMULATED PERSONALIZATION RESULT"
FIXTURE = "TEST FIXTURE — NOT A SUBMISSION RESULT"
PENDING = "PENDING REAL PROVIDER RUN"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def envelope(payload: dict, config: dict, dataset_version: str) -> dict:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    # Timestamp is deliberately outside the deterministic payload.
    return {"metadata": {"evaluation_version": VERSION, "git_commit": commit,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(), "configuration": config,
        "dataset_version": dataset_version, "framework": "ragas", "framework_version": "0.4.3",
        "python_version": sys.version.split()[0],
        "framework_lock_sha256": digest(ROOT / "evaluation/requirements-framework.lock"),
        "production_service_sha256": {p.name: digest(p) for p in sorted((ROOT / "backend/app/services").glob("*.py"))},
        "code_sha256": {str(p.relative_to(ROOT)): digest(p) for p in sorted(
            (ROOT / "evaluation/conceptlens_eval").glob("*.py"))}}, "payload": payload}
