import pytest

from app.core.config import settings
from app.services.direct_openai import DirectOpenAIProvider, MODELS
from app.services.llm_provider import (
    OpenAILLMProvider,
    LLMConfigurationError,
    get_llm_provider,
)


@pytest.mark.parametrize("tier", ["light", "standard", "deep"])
def test_direct_model_routing(monkeypatch, tier):
    monkeypatch.setattr(settings, "provider_mode", "direct_openai")
    monkeypatch.setattr(settings, "openai_api_key", "mock-api-key")

    provider = get_llm_provider(tier=tier)

    assert isinstance(provider, DirectOpenAIProvider)
    assert provider.model == MODELS[tier]


def test_direct_mode_missing_key_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "provider_mode", "direct_openai")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMConfigurationError):
        get_llm_provider()


def test_legacy_provider_remains_available(monkeypatch):
    monkeypatch.setattr(settings, "provider_mode", "compatible")
    monkeypatch.setattr(settings, "llm_base_url", "http://localhost:20128/v1")
    monkeypatch.setattr(settings, "llm_api_key", "mock-legacy-key")
    monkeypatch.setattr(settings, "llm_model", "mock-model")

    provider = get_llm_provider()

    assert isinstance(provider, OpenAILLMProvider)


def test_unknown_provider_mode_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "provider_mode", "invalid")

    with pytest.raises(LLMConfigurationError):
        get_llm_provider()


def test_astra_selected_for_direct_verification(monkeypatch):
    from app.services.llm_provider import get_verifier_provider

    monkeypatch.setattr(settings, "provider_mode", "direct_openai")
    monkeypatch.setattr(settings, "openai_api_key", "mock-api-key")

    generator = get_llm_provider(tier="standard")
    verifier = get_verifier_provider(generator, injected=False)

    assert generator.model == MODELS["standard"]
    assert verifier.model == MODELS["deep"]


def test_injected_verifier_is_preserved(monkeypatch):
    from app.services.llm_provider import get_verifier_provider

    monkeypatch.setattr(settings, "provider_mode", "direct_openai")

    sentinel = object()

    assert get_verifier_provider(sentinel, injected=True) is sentinel


def test_compatible_verifier_is_preserved(monkeypatch):
    from app.services.llm_provider import get_verifier_provider

    monkeypatch.setattr(settings, "provider_mode", "compatible")

    sentinel = object()

    assert get_verifier_provider(sentinel, injected=False) is sentinel
