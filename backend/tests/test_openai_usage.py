import json
import logging

import httpx
import pytest

from app.services.direct_openai import DirectOpenAIProvider, MODELS
from app.services.llm_provider import InvalidLLMResponseError


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["completed", "incomplete"])
async def test_usage_logged_without_sensitive_content(caplog, status):
    def handler(request):
        return httpx.Response(200, json={
            "status": status,
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({"ok": True}),
                }],
            }] if status == "completed" else [],
            "usage": {
                "input_tokens": 150,
                "output_tokens": 80,
                "input_tokens_details": {"cached_tokens": 20},
                "output_tokens_details": {"reasoning_tokens": 30},
            },
        })

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        provider = DirectOpenAIProvider(
            api_key="SECRET_API_KEY_DO_NOT_LOG",
            model=MODELS["deep"],
            client=client,
        )

        with caplog.at_level(
            logging.INFO,
            logger="app.services.direct_openai",
        ):
            if status == "completed":
                await provider.generate(
                    system_prompt="system",
                    user_prompt="PRIVATE_STUDENT_CONTENT",
                )
            else:
                with pytest.raises(InvalidLLMResponseError):
                    await provider.generate(
                        system_prompt="system",
                        user_prompt="PRIVATE_STUDENT_CONTENT",
                    )

    assert "input=150" in caplog.text
    assert "output=80" in caplog.text
    assert "cached=20" in caplog.text
    assert "reasoning=30" in caplog.text
    assert "SECRET_API_KEY_DO_NOT_LOG" not in caplog.text
    assert "PRIVATE_STUDENT_CONTENT" not in caplog.text
