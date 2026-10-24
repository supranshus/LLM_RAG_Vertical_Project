"""Progress and risk computed from task rows.

Every number on the dashboard, the board and the assistant comes from here, so
each screen reports the same figure. Nothing in this module calls a model: the
design rule is that code computes the facts and the model only writes prose.

These are frontend calculations over the mock rows. When the backend exposes a
metrics endpoint, each function here is replaced by a field in its response.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Iterable

DONE = "done"
BLOCKED = "blocked"
BACKLOG = "backlog"
# A project counts as behind once its elapsed share of the schedule runs this
# far ahead of the share of work finished.
BURN_RATE_TOLERANCE = 0.15


def today() -> date:
    return date.today()


def _as_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


# ---- progress ---------------------------------------------------------------

def scheduled(tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tasks that count towards progress: everything except the backlog."""
    return [t for t in tasks if t.get("status") != BACKLOG]


def percent_complete(tasks: Iterable[dict[str, Any]]) -> int:
    """Share of scheduled tasks that are done, 0-100."""
    items = scheduled(tasks)
    if not items:
        return 0
    done = sum(1 for t in items if t.get("status") == DONE)
    return round(100 * done / len(items))


def hours_progress(tasks: Iterable[dict[str, Any]]) -> tuple[float, float]:
    """(hours logged, hours estimated) over the scheduled tasks."""
    items = scheduled(tasks)
    logged = sum(float(t.get("actual_hours") or 0) for t in items)
    estimated = sum(float(t.get("estimated_hours") or 0) for t in items)
    return round(logged, 1), round(estimated, 1)


def status_counts(tasks: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "todo")
        counts[status] = counts.get(status, 0) + 1
    return counts


# ---- risk -------------------------------------------------------------------

def is_overdue(task: dict[str, Any], on: date | None = None) -> bool:
    """Past its due date and not finished."""
    if task.get("status") == DONE:
        return False
    due = _as_date(task.get("due_date"))
    return bool(due and due < (on or today()))


def overdue_tasks(tasks: Iterable[dict[str, Any]], on: date | None = None) -> list[dict[str, Any]]:
    return [t for t in tasks if is_overdue(t, on)]


def blocked_tasks(tasks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tasks if t.get("status") == BLOCKED]


def days_left(project: dict[str, Any], on: date | None = None) -> int | None:
    end = _as_date(project.get("preferred_end_date"))
    return (end - (on or today())).days if end else None


def elapsed_fraction(project: dict[str, Any], on: date | None = None) -> float | None:
    """How much of the planned schedule has gone by, 0.0-1.0."""
    start, end = _as_date(project.get("start_date")), _as_date(project.get("preferred_end_date"))
    if not start or not end or end <= start:
        return None
    gone = ((on or today()) - start).days
    return max(0.0, min(1.0, gone / (end - start).days))


def health(project: dict[str, Any], tasks: Iterable[dict[str, Any]],
           on: date | None = None) -> str:
    """``on_track``, ``at_risk`` or ``behind``, from the burn rate and open risks.

    Behind: the schedule has run materially ahead of the work finished.
    At risk: on pace overall, but something is blocked or overdue.
    """
    tasks = list(tasks)
    if project.get("status") == "completed":
        return "on_track"
    elapsed = elapsed_fraction(project, on)
    complete = percent_complete(tasks) / 100
    if elapsed is not None and elapsed - complete > BURN_RATE_TOLERANCE:
        return "behind"
    if blocked_tasks(tasks) or overdue_tasks(tasks, on):
        return "at_risk"
    return "on_track"


HEALTH_LABELS = {"on_track": "On track", "at_risk": "At risk", "behind": "Behind schedule"}


def risk_flags(project: dict[str, Any], tasks: Iterable[dict[str, Any]],
               on: date | None = None) -> list[dict[str, Any]]:
    """Deterministic risk detection (FR-010).

    Returns one flag per problem. Detection is rules only; the wording a user
    sees on the notifications page is drafted separately.
    """
    tasks = list(tasks)
    flags: list[dict[str, Any]] = []
    state = health(project, tasks, on)
    if state == "behind":
        elapsed = elapsed_fraction(project, on) or 0
        flags.append({
            "type": "behind_schedule", "severity": "critical", "entity_type": "project",
            "entity_id": project["id"], "title": f"{project['name']} is behind schedule",
            "reason": f"{round(elapsed * 100)}% of the schedule has gone by with "
                      f"{percent_complete(tasks)}% of the work finished.",
        })
    for task in blocked_tasks(tasks):
        flags.append({
            "type": "blocked", "severity": "high", "entity_type": "task", "entity_id": task["id"],
            "title": f"{task['title']} is blocked",
            "reason": f"Assigned to {task.get('assignee_name') or 'nobody'}"
                      f"{', due ' + task['due_date'] if task.get('due_date') else ''}.",
        })
    for task in overdue_tasks(tasks, on):
        if task.get("status") == BLOCKED:
            continue  # already flagged above
        due = _as_date(task["due_date"])
        late = ((on or today()) - due).days
        flags.append({
            "type": "overdue", "severity": "high" if late > 3 else "medium",
            "entity_type": "task", "entity_id": task["id"],
            "title": f"{task['title']} is {late} day{'' if late == 1 else 's'} overdue",
            "reason": f"Due {task['due_date']}, still in "
                      f"{task.get('status', 'todo').replace('_', ' ')}.",
        })
    return flags


# ---- sprints and people -----------------------------------------------------

def sprint_progress(sprint: dict[str, Any], tasks: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """One sprint with its task counts and completion."""
    items = [t for t in tasks if t.get("sprint_id") == sprint["id"]]
    logged, estimated = hours_progress(items)
    return {
        **sprint,
        "task_count": len(items),
        "done_count": sum(1 for t in items if t.get("status") == DONE),
        "open_count": sum(1 for t in items if t.get("status") not in (DONE, BACKLOG)),
        "percent": percent_complete(items),
        "hours_logged": logged,
        "hours_estimated": estimated,
    }


def workload(tasks: Iterable[dict[str, Any]], members: Iterable[dict[str, Any]]
             ) -> list[dict[str, Any]]:
    """Open work per person, busiest first. Used for the team view."""
    rows = []
    tasks = list(tasks)
    for member in members:
        mine = [t for t in tasks if t.get("assignee_id") == member["user_id"]]
        open_tasks = [t for t in mine if t.get("status") not in (DONE, BACKLOG)]
        rows.append({
            **member,
            "open_tasks": len(open_tasks),
            "open_hours": round(sum(float(t.get("estimated_hours") or 0) for t in open_tasks), 1),
            "done_tasks": sum(1 for t in mine if t.get("status") == DONE),
            "blocked": sum(1 for t in open_tasks if t.get("status") == BLOCKED),
            "overdue": len(overdue_tasks(open_tasks)),
        })
    return sorted(rows, key=lambda r: (-r["open_hours"], r["name"]))


# ---- formatting -------------------------------------------------------------

def short_date(value: str | None) -> str:
    d = _as_date(value)
    return f"{d:%d %b}" if d else "No date"


def date_range(start: str | None, end: str | None) -> str:
    return f"{short_date(start)} – {short_date(end)}"


def relative_day(value: str | None, on: date | None = None) -> str:
    """'Today', 'Tomorrow', '3 days ago' — for due dates and feeds."""
    d = _as_date((value or "")[:10])
    if not d:
        return ""
    delta = (d - (on or today())).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Tomorrow"
    if delta == -1:
        return "Yesterday"
    if delta < 0:
        return f"{-delta} days ago"
    return f"in {delta} days"
