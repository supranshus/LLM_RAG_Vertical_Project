import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED = ("ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "LLM_API_KEY", "PINECONE_API_KEY")


def test_settings_require_secrets(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key in REQUIRED:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key in REQUIRED:
        monkeypatch.setenv(key, "x")
    for key in ("RAG_TOP_K", "RAG_MIN_SCORE", "LLM_PROVIDER", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    s = Settings()
    assert (s.llm_provider, s.vector_store_provider, s.embedding_model) == (
        "groq",
        "pinecone",
        "multilingual-e5-large",
    )
    assert (s.rag_top_k, s.rag_min_score, s.rag_chunk_size, s.rag_chunk_overlap) == (
        5,
        0.78,
        1000,
        150,
    )
    assert (s.max_upload_mb, s.chat_history_limit, s.log_retention_days) == (10, 20, 14)
    assert s.database_url == "sqlite:///./data/app.db"


@pytest.mark.parametrize("key", REQUIRED)
def test_blank_required_value_is_rejected(monkeypatch, tmp_path, key):
    monkeypatch.chdir(tmp_path)
    for name in REQUIRED:
        monkeypatch.setenv(name, "x")
    monkeypatch.setenv(key, "  ")
    with pytest.raises(ValidationError, match=key.lower()):
        Settings()
