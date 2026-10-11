import os
from typing import Optional, Protocol, runtime_checkable

import httpx


class LLMConfigurationError(Exception):
    """Raised when LLM provider configuration is missing or invalid."""


class LLMProviderError(Exception):
    """Raised when LLM provider communication fails (network, timeout, non-2xx)."""

class InvalidLLMResponseError(Exception):
    """Raised when LLM response is malformed, invalid JSON, or violates schema."""


class UnsafeCitationReferenceError(Exception):
    """Raised when LLM references an evidence ID that is unknown or not supported."""


@runtime_checkable
class LLMProvider(Protocol):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate response text from LLM given system and user prompts."""
        ...


class OpenAILLMProvider:
    """OpenAI-compatible LLM provider adapter using runtime httpx."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 45.0,
        client: Optional[httpx.AsyncClient] = None,
    ):
        if not base_url or not base_url.strip():
            raise LLMConfigurationError("LLM base URL is not configured.")
        if not api_key or not api_key.strip():
            raise LLMConfigurationError("LLM API key is not configured.")
        if not model or not model.strip():
            raise LLMConfigurationError("LLM model is not configured.")

        self.base_url = base_url.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.timeout_seconds = timeout_seconds if timeout_seconds > 0 else 45.0
        self._client = client

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        try:
            if self._client is not None:
                response = await self._client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )
        except httpx.TimeoutException:
            raise LLMProviderError("LLM provider request timed out.") from None
        except httpx.NetworkError:
            raise LLMProviderError("LLM provider network error.") from None
        except Exception:
            raise LLMProviderError("LLM provider connection failed.") from None

        if response.status_code < 200 or response.status_code >= 300:
            raise LLMProviderError(
                f"LLM provider returned error status {response.status_code}."
            )

        try:
            data = response.json()
        except Exception:
            raise InvalidLLMResponseError("LLM provider returned malformed JSON response.") from None

        if not isinstance(data, dict):
            raise InvalidLLMResponseError("LLM provider response must be a JSON object.")

        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) == 0:
            raise InvalidLLMResponseError("LLM provider response missing choices.")

        choice = choices[0]
        if not isinstance(choice, dict):
            raise InvalidLLMResponseError("LLM provider response choice is not a dict.")

        message = choice.get("message")
        if not isinstance(message, dict):
            raise InvalidLLMResponseError("LLM provider response missing message in choice.")

        content = message.get("content")
        if not isinstance(content, str):
            raise InvalidLLMResponseError("LLM provider response content is not a string.")

        return content


def get_llm_provider(*, tier: str = "standard") -> LLMProvider:
    """Resolve and instantiate the configured LLMProvider.

    Raises LLMConfigurationError if required configuration is missing.
    """
    from app.core.config import settings

    if settings.provider_mode == "direct_openai":
        from app.services.direct_openai import get_direct_provider
        return get_direct_provider(tier)

    if settings.provider_mode != "compatible":
        raise LLMConfigurationError("Unknown LLM provider mode.")

    base_url = settings.llm_base_url or os.environ.get("CONCEPTLENS_LLM_BASE_URL")
    api_key = settings.llm_api_key or os.environ.get("CONCEPTLENS_LLM_API_KEY")
    model = settings.llm_model or os.environ.get("CONCEPTLENS_LLM_MODEL")

    raw_timeout = os.environ.get("CONCEPTLENS_LLM_TIMEOUT_SECONDS")
    if raw_timeout:
        try:
            timeout_seconds = float(raw_timeout)
        except ValueError:
            timeout_seconds = settings.llm_timeout_seconds
    else:
        timeout_seconds = settings.llm_timeout_seconds

    if not base_url or not api_key or not model:
        raise LLMConfigurationError("Answer generation is not configured.")

    return OpenAILLMProvider(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
    )


def get_verifier_provider(
    generator_provider: LLMProvider,
    *,
    injected: bool,
) -> LLMProvider:
    from app.core.config import settings

    if injected or settings.provider_mode != "direct_openai":
        return generator_provider

    return get_llm_provider(tier="deep")
