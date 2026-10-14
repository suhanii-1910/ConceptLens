import json

import httpx
import pytest

from app.services.direct_openai import (
    DirectOpenAIProvider,
    MODELS,
    get_direct_provider,
)
from app.services.llm_provider import (
    InvalidLLMResponseError,
    LLMConfigurationError,
)


@pytest.mark.asyncio
async def test_text_request():
    def handler(request):
        body = json.loads(request.content)

        assert request.url.path == "/v1/responses"
        assert body["model"] == MODELS["standard"]
        assert body["store"] is False
        assert body["text"]["format"] == {"type": "json_object"}
        assert "temperature" not in body
        assert body["input"][0]["content"][0]["text"] == "question\nReturn a JSON object."

        return httpx.Response(200, json={
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": '{"ok":true}',
                }],
            }],
        })

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = DirectOpenAIProvider(
            api_key="test",
            model=MODELS["standard"],
            client=client,
        )

        result = await provider.generate(
            system_prompt="system",
            user_prompt="question",
        )

        assert json.loads(result) == {"ok": True}


@pytest.mark.asyncio
async def test_vision_request():
    def handler(request):
        body = json.loads(request.content)
        parts = body["input"][0]["content"]

        assert "json" in parts[0]["text"].lower()
        assert parts[1]["type"] == "input_image"
        assert parts[1]["image_url"].startswith(
            "data:image/png;base64,"
        )

        return httpx.Response(200, json={
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": '{"supported":true}',
                }],
            }],
        })

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = DirectOpenAIProvider(
            api_key="test",
            model=MODELS["standard"],
            client=client,
        )

        result = await provider.inspect(
            b"fake-png",
            "explain",
        )

        assert json.loads(result) == {"supported": True}


@pytest.mark.asyncio
async def test_incomplete_fails_closed():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"status": "incomplete", "output": []},
        )
    )

    async with httpx.AsyncClient(transport=transport) as client:
        provider = DirectOpenAIProvider(
            api_key="test",
            model=MODELS["deep"],
            client=client,
        )

        with pytest.raises(InvalidLLMResponseError):
            await provider.generate(
                system_prompt="system",
                user_prompt="question",
            )


def test_routing_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMConfigurationError):
        get_direct_provider("deep")

    with pytest.raises(LLMConfigurationError):
        get_direct_provider("invalid")
