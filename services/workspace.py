"""People, sprints, tasks, progress updates and notifications.

These back the dashboard, sprint board, my-tasks, assistant and notifications pages.

API contract (see services/endpoints.py for paths):
  GET   /users                              people, with role and designation
  GET   /project-members?project_id=...     who is on a project, and their allocation
  GET   /sprints?project_id=...             sprints in sprint_number order
  GET   /tasks?project_id=...               tasks (see mock_data/tasks.json for the shape)
  PATCH /tasks/{task_id}                    change status / progress on a task
  GET   /task-updates?project_id=...        progress notes written against tasks
  POST  /task-updates                       record a progress note
  GET   /notifications?recipient_user_id=.. alerts for one person
  PATCH /notifications/{id}                 acknowledge / resolve / dismiss

Role filtering happens here rather than in the pages, so the same rule applies
when these calls move to the real backend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from . import data

# Roles from the users table. Ordered widest access first.
ROLES = ["admin", "pm", "tech_lead", "member"]
ROLE_LABELS = {
    "admin": "Director",
    "pm": "Project manager",
    "tech_lead": "Tech lead",
    "member": "Team member",
}
# Task statuses from the tasks table, in board order.
STATUSES = ["backlog", "todo", "in_progress", "in_review", "blocked", "done"]
STATUS_LABELS = {
    "backlog": "Backlog",
    "todo": "To do",
    "in_progress": "In progress",
    "in_review": "In review",
    "blocked": "Blocked",
    "done": "Done",
}
PRIORITIES = ["critical", "high", "medium", "low"]
OPEN_STATUSES = [s for s in STATUSES if s != "done"]


# ---- people -----------------------------------------------------------------

def list_users() -> list[dict[str, Any]]:
    return data.list("users")


def user_map() -> dict[str, dict[str, Any]]:
    return {u["id"]: u for u in list_users()}


def get_user(user_id: str) -> dict[str, Any] | None:
    return user_map().get(user_id)


def list_members(project_id: str) -> list[dict[str, Any]]:
    """Project members with the person's name, role and designation joined in."""
    users = user_map()
    members = []
    for m in data.list("project_members", {"project_id": project_id}):
        user = users.get(m["user_id"], {})
        members.append({**m, "name": user.get("name", "Unknown"),
                        "designation": user.get("designation"),
                        "account_role": user.get("role")})
    return sorted(members, key=lambda m: m["name"])


def list_user_skills(user_id: str) -> list[str]:
    names = {s["id"]: s["name"] for s in data.list("skills")}
    return [names.get(us["skill_id"], "") for us in data.list("user_skills", {"user_id": user_id})]


# ---- projects ---------------------------------------------------------------

def list_projects() -> list[dict[str, Any]]:
    return data.list("projects")


def visible_projects(user_id: str, role: str) -> list[dict[str, Any]]:
    """Which projects this person may see (FR-011).

    admin and pm see every project; everyone else sees the projects they are on.
    """
    projects = list_projects()
    if role in ("admin", "pm"):
        return projects
    mine = {m["project_id"] for m in data.list("project_members", {"user_id": user_id})}
    return [p for p in projects if p["id"] in mine]


# ---- sprints and tasks ------------------------------------------------------

def list_sprints(project_id: str) -> list[dict[str, Any]]:
    sprints = data.list("sprints", {"project_id": project_id})
    return sorted(sprints, key=lambda s: s.get("sprint_number", 0))


def current_sprint(project_id: str) -> dict[str, Any] | None:
    """The sprint in flight: the active one, else the next planned, else the last."""
    sprints = list_sprints(project_id)
    if not sprints:
        return None
    for sprint in sprints:
        if sprint.get("status") == "active":
            return sprint
    for sprint in sprints:
        if sprint.get("status") == "planned":
            return sprint
    return sprints[-1]


def list_tasks(project_id: str, *, sprint_id: str | None = None,
               assignee_id: str | None = None) -> list[dict[str, Any]]:
    """Tasks with the assignee's name and their sprint name joined in."""
    tasks = data.list("tasks", {"project_id": project_id})
    if sprint_id is not None:
        tasks = [t for t in tasks if t.get("sprint_id") == sprint_id]
    if assignee_id is not None:
        tasks = [t for t in tasks if t.get("assignee_id") == assignee_id]
    users = user_map()
    sprint_names = {s["id"]: s["name"] for s in list_sprints(project_id)}
    sprint_numbers = {s["id"]: s.get("sprint_number") for s in list_sprints(project_id)}
    for task in tasks:
        task["assignee_name"] = users.get(task.get("assignee_id"), {}).get("name")
        task["sprint_name"] = sprint_names.get(task.get("sprint_id"))
        task["sprint_number"] = sprint_numbers.get(task.get("sprint_id"))
    return tasks


def get_task(task_id: str) -> dict[str, Any]:
    return data.get("tasks", task_id)


def update_task(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    payload = {**payload, "updated_at": datetime.now().isoformat(timespec="seconds")}
    return data.update("tasks", task_id, payload)


def my_tasks(user_id: str, project_id: str | None = None) -> list[dict[str, Any]]:
    """Every task assigned to someone, across the projects they can see."""
    project_ids = [project_id] if project_id else [p["id"] for p in list_projects()]
    tasks: list[dict[str, Any]] = []
    for pid in project_ids:
        tasks.extend(list_tasks(pid, assignee_id=user_id))
    return tasks


# ---- progress updates -------------------------------------------------------

def list_task_updates(*, project_id: str | None = None,
                      task_id: str | None = None) -> list[dict[str, Any]]:
    """Progress notes, newest first, with the author's name joined in."""
    params = {}
    if project_id:
        params["project_id"] = project_id
    if task_id:
        params["task_id"] = task_id
    updates = data.list("task_updates", params)
    users = user_map()
    titles = {}
    for update in updates:
        update["author_name"] = users.get(update.get("author_id"), {}).get("name", "Unknown")
        if update["task_id"] not in titles:
            try:
                titles[update["task_id"]] = get_task(update["task_id"]).get("title", "")
            except Exception:  # noqa: BLE001 - a deleted task must not break the feed
                titles[update["task_id"]] = ""
        update["task_title"] = titles[update["task_id"]]
    return sorted(updates, key=lambda u: u.get("created_at", ""), reverse=True)


def post_task_update(task_id: str, author_id: str, note: str, *,
                     status_after: str | None = None,
                     progress_percentage: int | None = None,
                     hours_logged: float = 0.0,
                     source: str = "form") -> dict[str, Any]:
    """Record a progress note and move the task to match it (FR-008)."""
    task = get_task(task_id)
    update = data.create("task_updates", {
        "task_id": task_id,
        "project_id": task["project_id"],
        "author_id": author_id,
        "note": note.strip(),
        "status_after": status_after or task["status"],
        "progress_percentage": progress_percentage,
        "hours_logged": hours_logged,
        "source": source,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    changes: dict[str, Any] = {}
    if status_after and status_after != task["status"]:
        changes["status"] = status_after
    if hours_logged:
        changes["actual_hours"] = round(float(task.get("actual_hours") or 0) + hours_logged, 2)
    if changes:
        update_task(task_id, changes)
    return update


# ---- notifications ----------------------------------------------------------

def list_notifications(recipient_user_id: str, *, project_id: str | None = None,
                       include_closed: bool = True) -> list[dict[str, Any]]:
    """Alerts for one person, newest first (FR-010, FR-012)."""
    params: dict[str, Any] = {"recipient_user_id": recipient_user_id}
    if project_id:
        params["project_id"] = project_id
    items = data.list("notifications", params)
    if not include_closed:
        items = [n for n in items if n.get("lifecycle_status") == "active"]
    names = {p["id"]: p["name"] for p in list_projects()}
    users = user_map()
    for item in items:
        item["project_name"] = names.get(item.get("project_id"), "")
        item["actor_name"] = users.get(item.get("actor_user_id"), {}).get("name")
    return sorted(items, key=lambda n: n.get("created_at", ""), reverse=True)


def unread_count(recipient_user_id: str) -> int:
    return sum(1 for n in data.list("notifications", {"recipient_user_id": recipient_user_id})
               if n.get("lifecycle_status") == "active")


def set_notification_lifecycle(notification_id: str, lifecycle_status: str) -> dict[str, Any]:
    """Acknowledge, resolve or dismiss an alert."""
    now = datetime.now().isoformat(timespec="seconds")
    payload: dict[str, Any] = {"lifecycle_status": lifecycle_status, "updated_at": now,
                               "read_at": now}
    stamp = {"acknowledged": "acknowledged_at", "resolved": "resolved_at",
             "dismissed": "dismissed_at"}.get(lifecycle_status)
    if stamp:
        payload[stamp] = now
    return data.update("notifications", notification_id, payload)
