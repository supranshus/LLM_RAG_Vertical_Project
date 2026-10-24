"""Project setup and document generation.

API contract (see services/endpoints.py for paths):
  POST  /projects                         create project      -> {"id": ..., ...}
  PATCH /projects/{project_id}            update project (later "Save as draft" clicks)
  POST /projects/{project_id}/brd         upload BRD (multipart field "file")
  POST /projects/{project_id}/generate    run generation      -> generated documents
  GET  /projects/{project_id}/documents   generated documents (shape: mock_data/generated_documents.json)
"""
from __future__ import annotations

from typing import Any

from . import data
from .base import UploadFile


def list_employees() -> list[dict[str, Any]]:
    return data.list("employees")


def upload_brd(project_id: str, brd: UploadFile) -> Any:
    return data.action("project_brd", path_params={"project_id": project_id}, files={"file": brd})


def create_project(payload: dict[str, Any], brd: UploadFile | None = None) -> dict[str, Any]:
    project = data.create("projects", payload)
    if brd:
        upload_brd(project["id"], brd)
    return project


def update_project(
    project_id: str, payload: dict[str, Any], brd: UploadFile | None = None
) -> dict[str, Any]:
    project = data.update("projects", project_id, payload)
    if brd:
        upload_brd(project_id, brd)
    return project


def get_project(project_id: str) -> dict[str, Any]:
    return data.get("projects", project_id)


def generate_documents(project_id: str) -> dict[str, Any]:
    return data.action("project_generate", path_params={"project_id": project_id})


def get_documents(project_id: str) -> dict[str, Any]:
    return data.fetch("project_documents", path_params={"project_id": project_id})
