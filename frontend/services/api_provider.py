"""Talks to the real backend over HTTP. Activated with DATA_SOURCE=api."""
from __future__ import annotations

from typing import Any

import requests

from .base import DataProviderError, NotFoundError, UploadFile
from .endpoints import get_endpoint


class ApiProvider:
    def __init__(self, base_url: str, token: str = "", timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def _request(
        self,
        method: str,
        resource: str,
        suffix: str = "",
        path_params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        endpoint = get_endpoint(resource)
        url = f"{self.base_url}{endpoint.format_path(path_params)}{suffix}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise DataProviderError(f"Network error calling {url}: {exc}") from exc

        if resp.status_code == 404:
            raise NotFoundError(f"{url} not found")
        if not resp.ok:
            raise DataProviderError(
                f"{method} {url} failed ({resp.status_code}): {resp.text[:300]}",
                resp.status_code,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        body = resp.json()
        if endpoint.data_key and isinstance(body, dict):
            return body.get(endpoint.data_key, body)
        return body

    def list(self, resource: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        clean = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        return self._request("GET", resource, params=clean) or []

    def get(self, resource: str, item_id: Any) -> dict[str, Any]:
        return self._request("GET", resource, f"/{item_id}")

    def create(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", resource, json=payload)

    def update(self, resource: str, item_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", resource, f"/{item_id}", json=payload)

    def delete(self, resource: str, item_id: Any) -> None:
        self._request("DELETE", resource, f"/{item_id}")

    def fetch(
        self,
        resource: str,
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
    ) -> Any:
        return self._request("GET", resource, path_params=path_params, params=params)

    def action(
        self,
        resource: str,
        payload: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        files: dict[str, UploadFile] | None = None,
    ) -> Any:
        if files:
            # Multipart: non-file fields go as form data.
            return self._request(
                "POST", resource, path_params=path_params, data=payload or {}, files=files
            )
        return self._request("POST", resource, path_params=path_params, json=payload or {})
