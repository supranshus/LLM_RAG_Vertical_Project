import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import groq
import httpx
import pytest

from app.core.errors import LLMRateLimitError, LLMTimeoutError, LLMUnavailableError
from app.llm.base import ChatMessage, LLMResponse
from app.llm.groq_provider import GroqProvider

REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
MSGS = [ChatMessage("user", "x")]


def _provider(client):
    return GroqProvider(
        api_key="k",
        default_model="m-default",
        temperature=0.5,
        max_tokens=99,
        timeout=5,
        client=client,
    )


def _completion(content="hi", model="m", prompt=3, completion=4):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        model=model,
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def _chunk(text, usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))],
        usage=usage,
        x_groq=None,
    )


def test_chat_returns_content_and_usage():
    client = MagicMock()
    client.chat.completions.create.return_value = _completion()
    assert _provider(client).chat(MSGS) == LLMResponse("hi", "m", 3, 4)


def test_chat_uses_defaults_and_overrides():
    client = MagicMock()
    client.chat.completions.create.return_value = _completion()
    provider = _provider(client)
    provider.chat(MSGS)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert (kwargs["model"], kwargs["temperature"], kwargs["max_tokens"]) == ("m-default", 0.5, 99)
    assert kwargs["messages"] == [{"role": "user", "content": "x"}]
    provider.chat(MSGS, model="other", temperature=0.1, max_tokens=5)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert (kwargs["model"], kwargs["temperature"], kwargs["max_tokens"]) == ("other", 0.1, 5)


def test_rate_limit_mapped():
    client = MagicMock()
    client.chat.completions.create.side_effect = groq.RateLimitError(
        "rl", response=httpx.Response(429, request=REQUEST), body=None
    )
    with pytest.raises(LLMRateLimitError):
        _provider(client).chat(MSGS)


def test_timeout_mapped():
    client = MagicMock()
    client.chat.completions.create.side_effect = groq.APITimeoutError(request=REQUEST)
    with pytest.raises(LLMTimeoutError):
        _provider(client).chat(MSGS)


def test_connection_error_mapped():
    client = MagicMock()
    client.chat.completions.create.side_effect = groq.APIConnectionError(request=REQUEST)
    with pytest.raises(LLMUnavailableError):
        _provider(client).chat(MSGS)


def test_auth_error_mapped():
    client = MagicMock()
    client.chat.completions.create.side_effect = groq.AuthenticationError(
        "bad key", response=httpx.Response(401, request=REQUEST), body=None
    )
    with pytest.raises(LLMUnavailableError):
        _provider(client).chat(MSGS)


def test_stream_yields_text_and_skips_empty_deltas():
    client = MagicMock()
    client.chat.completions.create.return_value = iter([_chunk("He"), _chunk(None), _chunk("llo")])
    assert list(_provider(client).stream_chat(MSGS)) == ["He", "llo"]
    assert client.chat.completions.create.call_args.kwargs["stream"] is True


def test_error_during_stream_iteration_mapped():
    def broken():
        yield _chunk("He")
        raise groq.APIConnectionError(request=REQUEST)

    client = MagicMock()
    client.chat.completions.create.return_value = broken()
    stream = _provider(client).stream_chat(MSGS)
    assert next(stream) == "He"
    with pytest.raises(LLMUnavailableError):
        next(stream)


def test_stream_error_on_create_raised_immediately():
    client = MagicMock()
    client.chat.completions.create.side_effect = groq.RateLimitError(
        "rl", response=httpx.Response(429, request=REQUEST), body=None
    )
    with pytest.raises(LLMRateLimitError):
        _provider(client).stream_chat(MSGS)


def test_log_line_has_no_content(caplog):
    client = MagicMock()
    client.chat.completions.create.return_value = _completion(content="SECRET-REPLY")
    with caplog.at_level(logging.INFO):
        _provider(client).chat([ChatMessage("user", "SECRET-PROMPT")])
    assert "provider=groq" in caplog.text and "prompt_tokens=3" in caplog.text
    assert "SECRET-PROMPT" not in caplog.text and "SECRET-REPLY" not in caplog.text


@pytest.mark.parametrize(
    ("network_error", "expected"),
    [
        (httpx.RemoteProtocolError("peer closed connection"), LLMUnavailableError),
        (httpx.ReadTimeout("read timed out"), LLMTimeoutError),
    ],
)
def test_network_error_during_stream_mapped(network_error, expected):
    # The real Groq Stream reads the httpx body directly, so a dropped connection or a
    # stalled read surfaces as a raw httpx error, not a groq.APIError.
    def broken():
        yield _chunk("He")
        raise network_error

    client = MagicMock()
    client.chat.completions.create.return_value = broken()
    stream = _provider(client).stream_chat(MSGS)
    assert next(stream) == "He"
    with pytest.raises(expected):
        next(stream)
