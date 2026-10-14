import json
import uuid
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import visual_evidence
from app.services.direct_openai import MODELS


@pytest.mark.asyncio
async def test_visual_interpretation_routes_sol_then_astra(monkeypatch):
    monkeypatch.setattr(settings, "provider_mode", "direct_openai")
    calls = []

    class FakeProvider:
        def __init__(self, tier):
            self.model = MODELS[tier]

        async def inspect(self, image, prompt):
            calls.append(self.model)
            assert image == b"test-image"

            if self.model == MODELS["standard"]:
                return json.dumps({
                    "evidence_type": "diagram",
                    "description": "P1 arrives before P2.",
                })

            return json.dumps({
                "supported": True,
                "reason": "The diagram supports the description.",
            })

    monkeypatch.setattr(
        visual_evidence,
        "get_direct_provider",
        lambda tier: FakeProvider(tier),
    )

    unit = SimpleNamespace(
        id=uuid.uuid4(),
        course_id=uuid.uuid4(),
        source_version_id=uuid.uuid4(),
        modality=SimpleNamespace(value="image"),
        location_metadata={},
        original_text=None,
        extracted_description=None,
        embedding=None,
        embedding_model=None,
        embedding_content_hash=None,
    )

    source = SimpleNamespace(file_hash="test-sha256")

    async def fake_evidence(db, course_id, evidence_id, *, lock=False):
        assert lock is True
        return unit, source, {"reference": "test"}

    monkeypatch.setattr(visual_evidence, "evidence", fake_evidence)
    monkeypatch.setattr(
        visual_evidence,
        "visual_asset",
        lambda unit: b"test-image",
    )

    class FakeDB:
        async def flush(self):
            pass

    result = await visual_evidence.interpret(
        FakeDB(),
        unit.course_id,
        unit.id,
    )

    assert calls == [MODELS["standard"], MODELS["deep"]]
    assert result["semantic_state"] == "verified"
    assert unit.extracted_description == "P1 arrives before P2."
    assert unit.location_metadata["visual_semantics"]["provider_model"] == MODELS["standard"]
    assert unit.location_metadata["visual_semantics"]["verifier_model"] == MODELS["deep"]
