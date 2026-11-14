import pytest

from app.core.config import Settings
from app.llm.factory import get_llm_provider
from app.llm.groq_provider import GroqProvider


def test_factory_builds_groq_from_settings():
    provider = get_llm_provider(Settings(llm_model="some-model"))
    assert isinstance(provider, GroqProvider)
    assert (provider.name, provider.default_model) == ("groq", "some-model")


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER: 'nope'"):
        get_llm_provider(Settings(llm_provider="nope"))
