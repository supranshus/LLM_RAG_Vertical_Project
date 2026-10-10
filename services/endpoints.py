"""Maps logical resource names to API paths and mock files.

When the backend is ready, adjust ``path`` here; pages don't change.
Paths may contain ``{placeholders}`` filled from ``path_params``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Endpoint:
    path: str                     # API path relative to API_BASE_URL
    mock_file: str | None = None  # JSON file in mock_data/ (None: mock echoes the request)
    id_field: str = "id"          # primary key field name for collections
    data_key: str | None = None   # key wrapping the payload in API responses, e.g. "data"

    def format_path(self, path_params: dict[str, Any] | None = None) -> str:
        try:
            return self.path.format(**(path_params or {}))
        except KeyError as exc:
            raise ValueError(f"Missing path param {exc} for '{self.path}'") from exc


ENDPOINTS: dict[str, Endpoint] = {
    # Collection: list/get/create/update/delete projects.
    "projects": Endpoint(path="/projects", mock_file="projects.json"),
    # POST multipart with the BRD file.
    "project_brd": Endpoint(path="/projects/{project_id}/brd"),
    # POST: kick off sprint/task/test case generation. Returns the documents.
    "project_generate": Endpoint(
        path="/projects/{project_id}/generate", mock_file="generated_documents.json"
    ),
    # GET: generated documents for a project.
    "project_documents": Endpoint(
        path="/projects/{project_id}/documents", mock_file="generated_documents.json"
    ),
}


def get_endpoint(resource: str) -> Endpoint:
    try:
        return ENDPOINTS[resource]
    except KeyError as exc:
        raise KeyError(
            f"Unknown resource '{resource}'. Register it in services/endpoints.py"
        ) from exc
