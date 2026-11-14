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
    # Collection: list employees available for project teams.
    "employees": Endpoint(path="/employees", mock_file="employees.json"),
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

    # ---- workspace: execution data behind the dashboard, board, tasks and alerts ----
    # Collection: people, their skills and their project membership.
    "users": Endpoint(path="/users", mock_file="users.json"),
    "skills": Endpoint(path="/skills", mock_file="skills.json"),
    "user_skills": Endpoint(path="/user-skills", mock_file="user_skills.json", id_field="user_id"),
    "project_members": Endpoint(path="/project-members", mock_file="project_members.json"),
    "project_sprint_settings": Endpoint(
        path="/project-sprint-settings", mock_file="project_sprint_settings.json"
    ),
    # Collection: deliverables (candidate epics), sprints and tasks.
    "deliverables": Endpoint(path="/deliverables", mock_file="project_deliverables.json"),
    "sprints": Endpoint(path="/sprints", mock_file="sprints.json"),
    "tasks": Endpoint(path="/tasks", mock_file="tasks.json"),
    # Collection: progress notes written against a task (see README "Schema gaps").
    "task_updates": Endpoint(path="/task-updates", mock_file="task_updates.json"),
    # Collection: risk alerts and notifications.
    "notifications": Endpoint(path="/notifications", mock_file="notifications.json"),
}


def get_endpoint(resource: str) -> Endpoint:
    try:
        return ENDPOINTS[resource]
    except KeyError as exc:
        raise KeyError(
            f"Unknown resource '{resource}'. Register it in services/endpoints.py"
        ) from exc
