import pytest

from app.schemas.ask import AskMode
from app.services import grounded_ask


@pytest.mark.parametrize(
    "mode,expected",
    [
        (AskMode.just_answer, "light"),
        (AskMode.explain, "standard"),
        (AskMode.guide, "standard"),
    ],
)
def test_ask_model_selection(monkeypatch, mode, expected):
    from app.core.config import settings

    monkeypatch.setattr(settings, "provider_mode", "direct_openai")
    calls = []
    sentinel = object()

    def fake_provider(*, tier="standard"):
        calls.append(tier)
        return sentinel

    monkeypatch.setattr(
        grounded_ask,
        "get_llm_provider",
        fake_provider,
    )

    result = grounded_ask.get_ask_provider(mode)

    assert result is sentinel
    assert calls == [expected]



def test_compatible_mode_preserves_provider_contract(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "provider_mode", "compatible")

    sentinel = object()
    monkeypatch.setattr(
        grounded_ask,
        "get_llm_provider",
        lambda: sentinel,
    )

    for mode in AskMode:
        assert grounded_ask.get_ask_provider(mode) is sentinel
