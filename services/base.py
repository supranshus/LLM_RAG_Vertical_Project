"""Contract every data provider (mock or real API) must satisfy.

Pages never talk to a provider directly; they go through the service
functions in ``services/``. Swapping mock -> API is a config change.
"""
from __future__ import annotations

from typing import Any, Protocol

# (filename, content bytes, mime type)
UploadFile = tuple[str, bytes, str]


class DataProviderError(Exception):
    """Raised for any provider failure so pages can handle one error type."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(DataProviderError):
    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class DataProvider(Protocol):
    def list(self, resource: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...

    def get(self, resource: str, item_id: Any) -> dict[str, Any]: ...

    def create(self, resource: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def update(self, resource: str, item_id: Any, payload: dict[str, Any]) -> dict[str, Any]: ...

    def delete(self, resource: str, item_id: Any) -> None: ...

    def fetch(
        self,
        resource: str,
        params: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
    ) -> Any:
        """GET a non-collection resource (e.g. a project's generated documents)."""
        ...

    def action(
        self,
        resource: str,
        payload: dict[str, Any] | None = None,
        path_params: dict[str, Any] | None = None,
        files: dict[str, UploadFile] | None = None,
    ) -> Any:
        """POST to an action endpoint (e.g. generate, upload). ``files`` -> multipart."""
        ...
