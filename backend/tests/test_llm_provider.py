import json
import pytest
import httpx

from app.services.llm_provider import (
    LLMConfigurationError,
    LLMProviderError,
    InvalidLLMResponseError,
    OpenAILLMProvider,
    get_llm_provider,
)

pytestmark = pytest.mark.asyncio


async def test_provider_success_wire_format():
    """Verify OpenAI-compatible wire format: URL, headers, temperature=0, messages."""
    recorded_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "test-model"
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        assert body["messages"] == [
            {"role": "system", "content": "system prompt test"},
            {"role": "user", "content": "user prompt test"},
        ]
        resp_data = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": '{"blocks": []}'},
                    "finish_reason": "stop",
                }
            ],
        }
        return httpx.Response(200, json=resp_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com/v1/",
            api_key="secret-api-key-123",
            model="test-model",
            client=client,
        )

        content = await provider.generate(
            system_prompt="system prompt test",
            user_prompt="user prompt test",
        )

    assert content == '{"blocks": []}'
    assert len(recorded_requests) == 1
    req = recorded_requests[0]

    # Verify URL ends in /chat/completions and has no trailing slash duplicate
    assert str(req.url) == "https://api.openai.com/v1/chat/completions"
    # Verify API key is NOT in URL query parameters
    assert "secret-api-key" not in str(req.url)
    assert "key" not in req.url.params

    # Verify Authorization header is used safely
    assert req.headers.get("Authorization") == "Bearer secret-api-key-123"
    assert req.headers.get("Content-Type") == "application/json"


async def test_provider_missing_config_raises_configuration_error():
    """Missing base_url, api_key, or model must raise LLMConfigurationError."""
    with pytest.raises(LLMConfigurationError):
        OpenAILLMProvider(base_url="", api_key="key", model="model")

    with pytest.raises(LLMConfigurationError):
        OpenAILLMProvider(base_url="http://example.com", api_key="", model="model")

    with pytest.raises(LLMConfigurationError):
        OpenAILLMProvider(base_url="http://example.com", api_key="key", model="")


async def test_provider_non_2xx_safe_error():
    """Non-2xx response raises LLMProviderError without leaking response body or secret."""
    sensitive_provider_body = "SENSITIVE_PROVIDER_INTERNAL_ERROR_LEAK"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text=sensitive_provider_body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate(
                system_prompt="system",
                user_prompt="user",
            )

        err_msg = str(exc_info.value)
        assert sensitive_provider_body not in err_msg
        assert "secret-key" not in err_msg


async def test_provider_timeout_raises_provider_error():
    """Network timeout raises LLMProviderError without leaking credentials."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            await provider.generate(system_prompt="system", user_prompt="user")
        assert "timed out" in str(exc_info.value).lower()
        assert "secret-key" not in str(exc_info.value)


async def test_provider_network_error_raises_provider_error():
    """Network connection failure raises LLMProviderError."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(LLMProviderError):
            await provider.generate(system_prompt="system", user_prompt="user")


async def test_provider_malformed_response_json():
    """Malformed non-JSON provider response raises InvalidLLMResponseError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="NOT_VALID_JSON")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="system", user_prompt="user")


async def test_provider_missing_choices_or_content():
    """Missing choices, missing message, or non-string content raises InvalidLLMResponseError."""
    # 1. missing choices
    def handler_no_choices(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    transport = httpx.MockTransport(handler_no_choices)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

    # 2. non-string content
    def handler_invalid_content(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": 12345}}]})

    transport = httpx.MockTransport(handler_invalid_content)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")


    # 3. choice is null
    def handler_null_choice(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [None]})

    transport = httpx.MockTransport(handler_null_choice)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

    # 4. choice is bad (string)
    def handler_bad_choice(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": ["bad"]})

    transport = httpx.MockTransport(handler_bad_choice)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

    # 5. choice is empty dict
    def handler_empty_choice(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{}]})

    transport = httpx.MockTransport(handler_empty_choice)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

    # 6. missing message content
    def handler_message_null(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": None}]})

    transport = httpx.MockTransport(handler_message_null)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

    # 7. message is bad (string)
    def handler_message_bad(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": "bad"}]})

    transport = httpx.MockTransport(handler_message_bad)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

    # 8. message is empty dict
    def handler_empty_message(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {}}]})

    transport = httpx.MockTransport(handler_empty_message)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAILLMProvider(
            base_url="https://api.openai.com",
            api_key="secret-key",
            model="test-model",
            client=client,
        )
        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(system_prompt="s", user_prompt="u")

def test_get_llm_provider_factory(monkeypatch):
    """get_llm_provider reads settings/env or raises LLMConfigurationError."""
    monkeypatch.setenv("CONCEPTLENS_LLM_BASE_URL", "")
    monkeypatch.setenv("CONCEPTLENS_LLM_API_KEY", "")
    monkeypatch.setenv("CONCEPTLENS_LLM_MODEL", "")

    # Clean settings as well
    from app.core.config import settings
    monkeypatch.setattr(settings, "llm_base_url", None)
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "llm_model", None)

    with pytest.raises(LLMConfigurationError):
        get_llm_provider()

    monkeypatch.setattr(settings, "llm_base_url", "https://api.openai.com")
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(settings, "llm_model", "gpt-4o-mini")

    p = get_llm_provider()
    assert isinstance(p, OpenAILLMProvider)
    assert p.base_url == "https://api.openai.com"
    assert p.api_key == "sk-test"
    assert p.model == "gpt-4o-mini"
