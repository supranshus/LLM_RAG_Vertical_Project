"""Generic data access. Pages normally use the domain modules
(e.g. ``services.projects``) which are built on top of ``data``.

Reads are cached (CACHE_TTL); writes clear the cache.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from config.settings import get_settings

from .api_provider import ApiProvider
from .base import DataProvider, DataProviderError, NotFoundError, UploadFile
from .mock_provider import MockProvider

__all__ = ["data", "get_provider", "DataProviderError", "NotFoundError"]


@st.cache_resource
def get_provider() -> DataProvider:
    s = get_settings()
    if s.use_mock:
        return MockProvider(s.mock_data_dir, s.mock_latency_ms)
    return ApiProvider(s.api_base_url, s.api_token, s.api_timeout)


_TTL = get_settings().cache_ttl or None


def _freeze(params: dict[str, Any] | None) -> tuple:
    return tuple(sorted((params or {}).items()))


@st.cache_data(ttl=_TTL, show_spinner=False)
def _cached_list(resource: str, frozen: tuple) -> list[dict[str, Any]]:
    return get_provider().list(resource, dict(frozen))


@st.cache_data(ttl=_TTL, show_spinner=False)
def _cached_get(resource: str, item_id: Any) -> dict[str, Any]:
    return get_provider().get(resource, item_id)


@st.cache_data(ttl=_TTL, show_spinner=False)
def _cached_fetch(resource: str, frozen: tuple, frozen_path: tuple) -> Any:
    return get_provider().fetch(resource, dict(frozen), dict(frozen_path))


class _DataService:
    def list(self, resource: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return _cached_list(resource, _freeze(params))

    def get(self, resource: str, item_id: Any) -> dict[str, Any]:
        return _cached_get(resource, item_id)

    def fetch(
        self,
        resource: str,
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
    ) -> Any:
        return _cached_fetch(resource, _freeze(params), _freeze(path_params))

    def action(
        self,
        resource: str,
        payload: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        files: dict[str, UploadFile] | None = None,
    ) -> Any:
        result = get_provider().action(resource, payload, path_params, files)
        st.cache_data.clear()
        return result

    def create(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = get_provider().create(resource, payload)
        st.cache_data.clear()
        return result

    def update(self, resource: str, item_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
        result = get_provider().update(resource, item_id, payload)
        st.cache_data.clear()
        return result

    def delete(self, resource: str, item_id: Any) -> None:
        get_provider().delete(resource, item_id)
        st.cache_data.clear()


data = _DataService()
