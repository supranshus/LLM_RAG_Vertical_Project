from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None


class LLMProvider(ABC):
    """What services need from a chat model. Implementations wrap one vendor SDK.

    Provider failures must surface only as LLMRateLimitError, LLMTimeoutError or
    LLMUnavailableError, including failures while a stream is being read.
    """

    name: str
    default_model: str

    @abstractmethod
    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    @abstractmethod
    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]: ...
