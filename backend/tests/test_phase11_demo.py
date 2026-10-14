"""Demo tooling stays outside production, preserves source rules and refuses unsafe DBs."""
import importlib.util
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("phase11_demo", ROOT / "demo-course/prepare.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


@pytest.mark.parametrize("url", [
    "postgresql+asyncpg://localhost/conceptlens",
    "postgresql+asyncpg://localhost/postgres",
    "postgresql+asyncpg://localhost/conceptlens_eval_not_owned",
])
def test_demo_rejects_existing_databases(url, tmp_path):
    with pytest.raises(ValueError):
        demo.server_environment(url, tmp_path, False)


def test_demo_disables_inherited_providers_and_test_embeddings(monkeypatch, tmp_path):
    monkeypatch.setenv("CONCEPTLENS_LLM_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("USE_FAKE_EMBEDDING", "1")
    url = "postgresql+asyncpg://127.0.0.1/conceptlens_eval_" + "a" * 32
    env = demo.server_environment(url, tmp_path, False)
    assert env["CONCEPTLENS_DATABASE_URL"] == url
    assert env["CONCEPTLENS_LLM_API_KEY"] == ""
    assert "TESTING" not in env and "USE_FAKE_EMBEDDING" not in env
    assert Path(env["CONCEPTLENS_UPLOAD_DIR"]).is_relative_to(tmp_path)
    monkeypatch.delenv("CONCEPTLENS_LLM_MODEL", raising=False)
    with pytest.raises(ValueError):
        demo.server_environment(url, tmp_path, True)


def test_source_teaches_general_rule_and_contains_actual_visual(tmp_path):
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    demo.build_source(first)
    demo.build_source(second)
    assert first.read_bytes() == second.read_bytes()
    with fitz.open(first) as document:
        assert len(document) == 4
        text = " ".join(" ".join(page.get_text() for page in document).split())
        assert "Remaining time = original burst time - executed CPU time" in text
        assert "original burst ignores work already completed" in text
        assert "P1" not in text and "P2" not in text
        assert document[3].get_images()
        assert document[3].get_text() == ""
