"""Turn task rows from the API into the shape the task templates expect."""
from __future__ import annotations

from typing import Any, Iterable

from components import metrics
from components.documents import initials
from services.workspace import STATUS_LABELS, STATUSES

# Board order, least complete first. Backlog sits outside the sprint flow.
_STATUS_ORDER = {status: i for i, status in enumerate(STATUSES)}
_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def due_label(task: dict[str, Any]) -> str:
    if task.get("status") == metrics.DONE:
        return "Done"
    if not task.get("due_date"):
        return "No date"
    return metrics.relative_day(task["due_date"])


def row(task: dict[str, Any], *, sub: str | None = None) -> dict[str, Any]:
    """One task as the template wants it."""
    name = task.get("assignee_name")
    return {
        "id": task["id"],
        "title": task["title"],
        "sub": sub if sub is not None else task.get("sprint_name") or "Backlog",
        "area": task.get("area"),
        "status": task.get("status", "todo"),
        "status_label": STATUS_LABELS.get(task.get("status", "todo"), task.get("status", "")),
        "priority": task.get("priority", "medium"),
        "assignee_name": name,
        "initials": initials(name) if name else "–",
        "due_label": due_label(task),
        "is_late": metrics.is_overdue(task),
    }


def rows(tasks: Iterable[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    return [row(t, **kwargs) for t in tasks]


def sort_for_attention(tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Blocked and overdue first, then by priority, then by due date."""
    def key(task: dict[str, Any]) -> tuple:
        return (
            0 if task.get("status") == metrics.BLOCKED else 1,
            0 if metrics.is_overdue(task) else 1,
            _PRIORITY_ORDER.get(task.get("priority", "medium"), 9),
            task.get("due_date") or "9999-12-31",
            task["title"],
        )
    return sorted(tasks, key=key)


def sort_for_board(tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(task: dict[str, Any]) -> tuple:
        return (
            _STATUS_ORDER.get(task.get("status", "todo"), 9),
            _PRIORITY_ORDER.get(task.get("priority", "medium"), 9),
            task.get("due_date") or "9999-12-31",
        )
    return sorted(tasks, key=key)


def label(task: dict[str, Any]) -> str:
    """A one-line label for pickers: 'Scorecard dashboard UI · In review'."""
    return f"{task['title']} · {STATUS_LABELS.get(task.get('status', ''), '')}"
