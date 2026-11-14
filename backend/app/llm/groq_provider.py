import logging
import time
from collections.abc import Iterator, Sequence
from typing import Any

import groq
import httpx

from app.core.errors import AppError, LLMRateLimitError, LLMTimeoutError, LLMUnavailableError
from app.llm.base import ChatMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(
        self,
        api_key: str,
        default_model: str,
        temperature: float,
        max_tokens: int,
        timeout: float,
        client: groq.Groq | None = None,
    ):
        self.default_model = default_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = client or groq.Groq(api_key=api_key, timeout=timeout, max_retries=1)

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        params = self._params(messages, model, temperature, max_tokens)
        start = time.perf_counter()
        try:
            completion = self.client.chat.completions.create(**params)
        except groq.APIError as exc:
            self._log(params["model"], None, None, start, ok=False)
            raise _map_error(exc) from exc
        usage = completion.usage
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        self._log(completion.model, prompt_tokens, completion_tokens, start, ok=True)
        return LLMResponse(
            content=completion.choices[0].message.content or "",
            model=completion.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        params = self._params(messages, model, temperature, max_tokens)
        start = time.perf_counter()
        try:
            stream = self.client.chat.completions.create(**params, stream=True)
        except groq.APIError as exc:
            self._log(params["model"], None, None, start, ok=False)
            raise _map_error(exc) from exc
        return self._read_stream(stream, params["model"], start)

    def _read_stream(self, stream: Any, model: str, start: float) -> Iterator[str]:
        usage = None
        try:
            for chunk in stream:
                usage = getattr(chunk, "usage", None) or _x_groq_usage(chunk) or usage
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except groq.APIError as exc:
            self._log(model, None, None, start, ok=False)
            raise _map_error(exc) from exc
        except httpx.HTTPError as exc:
            # The SDK reads the response body directly, so a dropped connection or a
            # stalled read mid-stream arrives as a raw httpx error.
            self._log(model, None, None, start, ok=False)
            if isinstance(exc, httpx.TimeoutException):
                raise LLMTimeoutError(
                    "The AI service took too long to respond. Please try again."
                ) from exc
            raise LLMUnavailableError(
                "The AI service is unavailable right now. Please try again."
            ) from exc
        self._log(
            model,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            start,
            ok=True,
        )

    def _params(self, messages, model, temperature, max_tokens) -> dict[str, Any]:
        return {
            "model": model or self.default_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

    @staticmethod
    def _log(model, prompt_tokens, completion_tokens, start, *, ok: bool) -> None:
        logger.info(
            "llm provider=groq model=%s prompt_tokens=%s completion_tokens=%s latency_ms=%d ok=%s",
            model,
            prompt_tokens,
            completion_tokens,
            (time.perf_counter() - start) * 1000,
            ok,
        )


def _x_groq_usage(chunk: Any) -> Any:
    x_groq = getattr(chunk, "x_groq", None)
    return getattr(x_groq, "usage", None) if x_groq else None


def _map_error(exc: groq.APIError) -> AppError:
    if isinstance(exc, groq.RateLimitError):
        return LLMRateLimitError(
            "The AI service rate limit was reached. Please wait and try again."
        )
    if isinstance(exc, groq.APITimeoutError):
        return LLMTimeoutError("The AI service took too long to respond. Please try again.")
    return LLMUnavailableError("The AI service is unavailable right now. Please try again.")
