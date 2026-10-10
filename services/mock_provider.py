"""Serves data from JSON files in mock_data/. Writes are kept in memory only."""
from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

from .base import DataProviderError, NotFoundError, UploadFile
from .endpoints import get_endpoint


class MockProvider:
    def __init__(self, data_dir: Path, latency_ms: int = 0):
        self.data_dir = data_dir
        self.latency_ms = latency_ms
        self._store: dict[str, Any] = {}

    # -- internals -----------------------------------------------------------
    def _load(self, resource: str) -> Any:
        if resource not in self._store:
            mock_file = get_endpoint(resource).mock_file
            if not mock_file:
                raise DataProviderError(f"No mock file registered for '{resource}'", 500)
            file = self.data_dir / mock_file
            if not file.exists():
                raise DataProviderError(f"Mock file not found: {file.name}", 500)
            self._store[resource] = json.loads(file.read_text(encoding="utf-8"))
        return self._store[resource]

    def _sleep(self) -> None:
        if self.latency_ms:
            time.sleep(self.latency_ms / 1000)

    def _collection(self, resource: str) -> list[dict[str, Any]]:
        data = self._load(resource)
        if not isinstance(data, list):
            raise DataProviderError(f"Resource '{resource}' is not a collection", 500)
        return data

    def _find(self, resource: str, item_id: Any) -> dict[str, Any]:
        id_field = get_endpoint(resource).id_field
        for item in self._collection(resource):
            if str(item.get(id_field)) == str(item_id):
                return item
        raise NotFoundError(f"{resource}/{item_id} not found")

    # -- DataProvider --------------------------------------------------------
    def list(self, resource: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._sleep()
        items = self._collection(resource)
        # Simple equality filtering so mock behaves like ?field=value query params.
        for key, value in (params or {}).items():
            if value in (None, ""):
                continue
            items = [i for i in items if str(i.get(key)) == str(value)]
        return copy.deepcopy(items)

    def get(self, resource: str, item_id: Any) -> dict[str, Any]:
        self._sleep()
        return copy.deepcopy(self._find(resource, item_id))

    def create(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._sleep()
        id_field = get_endpoint(resource).id_field
        item = {id_field: payload.get(id_field) or uuid.uuid4().hex[:8], **payload}
        self._collection(resource).append(item)
        return copy.deepcopy(item)

    def update(self, resource: str, item_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
        self._sleep()
        item = self._find(resource, item_id)
        item.update(payload)
        return copy.deepcopy(item)

    def delete(self, resource: str, item_id: Any) -> None:
        self._sleep()
        item = self._find(resource, item_id)
        self._collection(resource).remove(item)

    def fetch(
        self,
        resource: str,
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
    ) -> Any:
        # Mock files are shared across path params (every project gets the same sample).
        self._sleep()
        return copy.deepcopy(self._load(resource))

    def action(
        self,
        resource: str,
        payload: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        files: dict[str, UploadFile] | None = None,
    ) -> Any:
        self._sleep()
        if get_endpoint(resource).mock_file:
            return copy.deepcopy(self._load(resource))
        # No fixture: echo the request, like a typical "accepted" response.
        return {
            **(path_params or {}),
            **(payload or {}),
            **{field: name for field, (name, _, _) in (files or {}).items()},
        }
