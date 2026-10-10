"""Central configuration, read from environment variables / .env / st.secrets."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _get(key: str, default: str = "") -> str:
    """Env var first, then Streamlit secrets, then default."""
    if key in os.environ:
        return os.environ[key]
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


@dataclass(frozen=True)
class Settings:
    data_source: str
    api_base_url: str
    api_token: str
    api_timeout: float
    mock_latency_ms: int
    cache_ttl: int
    mock_data_dir: Path = ROOT_DIR / "mock_data"
    templates_dir: Path = ROOT_DIR / "templates"
    assets_dir: Path = ROOT_DIR / "assets"

    @property
    def use_mock(self) -> bool:
        return self.data_source.lower() != "api"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        data_source=_get("DATA_SOURCE", "mock"),
        api_base_url=_get("API_BASE_URL", "http://localhost:8000/api").rstrip("/"),
        api_token=_get("API_TOKEN", ""),
        api_timeout=float(_get("API_TIMEOUT", "15")),
        mock_latency_ms=int(_get("MOCK_LATENCY_MS", "0")),
        cache_ttl=int(_get("CACHE_TTL", "60")),
    )
