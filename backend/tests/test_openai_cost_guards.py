import json

import httpx
import pytest

from app.services.direct_openai import (
    DirectOpenAIProvider,
    MAX_OUTPUT_TOKENS,
    MAX_TEXT_CHARS,
    MAX_IMAGE_BYTES,
    MODELS,
)
from app.services.llm_provider import LLMProviderError


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["light", "standard", "deep"])
async def test_model_output_token_cap(tier):
    def handler(request):
        body = json.loads(request.content)

        assert body["model"] == MODELS[tier]
        assert body["max_output_tokens"] == MAX_OUTPUT_TOKENS[MODELS[tier]]
        assert body["store"] is False

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
            api_key="test-key",
            model=MODELS[tier],
            client=client,
        )

        result = await provider.generate(
            system_prompt="system",
            user_prompt="question",
        )

        assert json.loads(result) == {"ok": True}


@pytest.mark.asyncio
async def test_oversized_text_rejected():
    provider = DirectOpenAIProvider(
        api_key="test-key",
        model=MODELS["standard"],
    )

    with pytest.raises(LLMProviderError):
        await provider.generate(
            system_prompt="system",
            user_prompt="x" * (MAX_TEXT_CHARS + 1),
        )


@pytest.mark.asyncio
async def test_oversized_image_rejected():
    provider = DirectOpenAIProvider(
        api_key="test-key",
        model=MODELS["standard"],
    )

    with pytest.raises(LLMProviderError):
        await provider.inspect(
            b"x" * (MAX_IMAGE_BYTES + 1),
            "Describe the image",
        )
