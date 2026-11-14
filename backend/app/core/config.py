from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend settings, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # Microsoft Entra ID
    entra_tenant_id: str
    entra_client_id: str
    # The delegated scope the frontend requests; tokens without it are refused.
    entra_required_scope: str = "access_as_user"

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # LLM
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: SecretStr
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 60.0

    # Chat
    chat_system_prompt: str = "You are a helpful assistant."
    chat_history_limit: int = 20

    # Document Q&A (RAG)
    vector_store_provider: str = "pinecone"
    embedding_provider: str = "pinecone"
    pinecone_api_key: SecretStr
    pinecone_index_name: str = "genai-boilerplate"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    embedding_model: str = "multilingual-e5-large"
    embedding_dimension: int = 1024
    rag_top_k: int = 5
    rag_min_score: float = 0.78
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 150
    max_upload_mb: int = 10
    upload_dir: str = "./data/uploads"

    # Logging
    log_level: str = "INFO"
    log_dir: str = "./logs"
    log_retention_days: int = 14

    @field_validator("entra_tenant_id", "entra_client_id", "llm_api_key", "pinecone_api_key")
    @classmethod
    def _not_blank(cls, value):
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not raw.strip():
            raise ValueError("must be set (it is empty)")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
