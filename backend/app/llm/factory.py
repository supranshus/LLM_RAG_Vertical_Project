from collections.abc import Callable

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.groq_provider import GroqProvider


def _build_groq(settings: Settings) -> LLMProvider:
    return GroqProvider(
        api_key=settings.llm_api_key.get_secret_value(),
        default_model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )


# To add a provider: write a class implementing LLMProvider, add a builder here,
# and set LLM_PROVIDER to its key.
_PROVIDERS: dict[str, Callable[[Settings], LLMProvider]] = {
    "groq": _build_groq,
}


def get_llm_provider(settings: Settings) -> LLMProvider:
    name = settings.llm_provider.lower()
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER: {name!r}")
    return _PROVIDERS[name](settings)
