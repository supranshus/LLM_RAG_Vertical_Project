"""Dashboard — progress and risk for the current project (FR-009, FR-010, FR-011).

What the page shows depends on the signed-in role. A director opens on the
portfolio; a project manager and a tech lead get the team's work and risks; a
team member gets their own tasks. Every number is computed in
``components.metrics`` from the task rows, so each screen agrees.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from components import metrics, tasks as task_view
from components.documents import initials
from components.html import render_template
from components.shell import empty_state, page_header, render_shell
from services import DataProviderError, workspace

BOARD_PAGE = "views/sprint_board.py"
NOTIFICATIONS_PAGE = "views/notifications.py"

BAR_CLASS = {"on_track": "is-good", "at_risk": "is-warn", "behind": "is-bad"}
DOT_CLASS = {"on_track": "", "at_risk": "is-warn", "behind": "is-late"}
SPRINT_BADGE = {"completed": "done", "active": "in_progress", "planned": "todo",
                "cancelled": "backlog"}
PROJECT_BADGE = {"completed": "done", "active": "in_progress", "draft": "backlog",
                 "on_hold": "blocked", "archived": "backlog"}
SPRINT_STATUS_LABEL = {"completed": "Completed", "active": "Active", "planned": "Planned",
                       "cancelled": "Cancelled"}


def _sprint_lines(project_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lines = []
    for sprint in workspace.list_sprints(project_id):
        progress = metrics.sprint_progress(sprint, rows)
        status = sprint.get("status", "planned")
        late = status == "active" and progress["open_count"] and \
            (sprint.get("end_date") or "") < metrics.today().isoformat()
        lines.append({
            **progress,
            "badge": SPRINT_BADGE.get(status, "todo"),
            "status_label": "Overran" if late else SPRINT_STATUS_LABEL.get(status, status),
            "dates": metrics.date_range(sprint.get("start_date"), sprint.get("end_date")),
            "bar_class": "is-good" if progress["percent"] == 100
                         else ("is-bad" if late else "is-warn" if status == "active" else ""),
        })
    return lines


def _feed(updates: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    return [{
        **u,
        "initials": initials(u.get("author_name") or "?"),
        "when": metrics.relative_day(u.get("created_at")),
        "status_label": workspace.STATUS_LABELS.get(u.get("status_after", ""), ""),
    } for u in updates[:limit]]


# ---- page -------------------------------------------------------------------

shell = render_shell("dashboard", page_css="dashboard.css")

with shell.main:
    if not shell.project:
        page_header("Dashboard")
        empty_state("No project selected yet. Open one from Projects, or set up a new project.")
        st.stop()

    project = shell.project
    try:
        rows = workspace.list_tasks(project["id"])
        members = workspace.list_members(project["id"])
        updates = workspace.list_task_updates(project_id=project["id"])
        load_error = None
    except DataProviderError as exc:
        rows, members, updates, load_error = [], [], [], str(exc)

    health = metrics.health(project, rows)
    percent = metrics.percent_complete(rows)
    overdue = metrics.overdue_tasks(rows)
    blocked = metrics.blocked_tasks(rows)
    flags = metrics.risk_flags(project, rows)
    left = metrics.days_left(project)
    logged, estimated = metrics.hours_progress(rows)
    sprint = workspace.current_sprint(project["id"])

    status_text = metrics.HEALTH_LABELS[health]
    if sprint:
        status_text += f" · {sprint['name']} ({metrics.date_range(sprint['start_date'], sprint['end_date'])})"

    with st.container(key="page_head", horizontal=True):
        page_header(
            project["name"],
            project.get("description", ""),
            status=status_text,
            status_tone=DOT_CLASS[health],
            chips=[f"{len(members)} people", f"{len(metrics.scheduled(rows))} tasks",
                   f"{logged:g}h of {estimated:g}h logged"],
        )
        with st.container(key="head_actions", horizontal=True, wrap=False, width="content"):
            if st.button("Open board", key="to_board"):
                st.switch_page(BOARD_PAGE)
            if st.button("View alerts", key="to_alerts", type="primary"):
                st.switch_page(NOTIFICATIONS_PAGE)

    if load_error:
        st.error(f"Could not load the project: {load_error}")

    render_template(
        "workspace/metric_grid.html",
        metrics=[
            {"label": "Complete", "value": f"{percent}%",
             "note": f"{sum(1 for t in metrics.scheduled(rows) if t['status'] == metrics.DONE)}"
                     f" of {len(metrics.scheduled(rows))} tasks",
             "tone": BAR_CLASS[health]},
            {"label": "Days left", "value": left if left is not None else "–",
             "note": f"to {metrics.short_date(project.get('preferred_end_date'))}",
             "tone": "is-bad" if left is not None and left < 0 else ""},
            {"label": "Overdue", "value": len(overdue), "note": "past the due date",
             "tone": "is-bad" if overdue else "is-good"},
            {"label": "Blocked", "value": len(blocked), "note": "waiting on something",
             "tone": "is-bad" if blocked else "is-good"},
        ],
    )

    # Director and PM: how the rest of the portfolio is doing.
    if shell.role in ("admin", "pm") and len(shell.projects) > 1:
        others = []
        for other in shell.projects:
            other_rows = workspace.list_tasks(other["id"])
            other_health = metrics.health(other, other_rows)
            has_tasks = bool(metrics.scheduled(other_rows))
            risks = len(metrics.risk_flags(other, other_rows))
            percent = metrics.percent_complete(other_rows)
            others.append({
                "name": other["name"],
                "health": other_health,
                "health_label": metrics.HEALTH_LABELS[other_health] if has_tasks
                                else "Not started",
                "dates": metrics.date_range(other.get("start_date"),
                                            other.get("preferred_end_date")),
                "status_badge": PROJECT_BADGE.get(other.get("status", ""), "todo"),
                "status_label": str(other.get("status", "")).replace("_", " ").capitalize(),
                "percent": percent if has_tasks else 0,
                "percent_label": f"{percent}%" if has_tasks else "No tasks",
                "bar_class": BAR_CLASS[other_health],
                "risk_count": risks,
                "risk_label": f"{risks} risk{'' if risks == 1 else 's'}" if risks else "Clear",
            })
        st.html('<div class="section-label">Portfolio <span class="count">'
                f'{len(others)} projects</span></div>')
        render_template("workspace/portfolio_rows.html", projects=others)

    render_template("workspace/sprint_progress.html", sprints=_sprint_lines(project["id"], rows))

    # Needs attention: the deterministic risk flags, newest problem first.
    render_template(
        "workspace/risk_list.html", title="Needs attention", flags=flags[:8],
        note="Flags are rules over the task data: blocked work, anything past its due date, and a "
             "project whose elapsed schedule runs ahead of the work finished. The wording you see "
             "on the Notifications page is drafted from these same flags.",
    )

    attention = task_view.sort_for_attention([t for t in rows if t["status"] not in
                                              (metrics.DONE, metrics.BACKLOG)])
    if shell.role == "member":
        mine = [t for t in attention if t.get("assignee_id") == shell.user_id]
        st.html('<div class="section-label">Your open tasks <span class="count">'
                f'{len(mine)} tasks</span></div>')
        if mine:
            render_template("workspace/task_rows.html", tasks=task_view.rows(mine))
        else:
            empty_state("Nothing open is assigned to you on this project.")
    else:
        st.html('<div class="section-label">Open work <span class="count">'
                f'{len(attention)} tasks</span></div>')
        if attention:
            render_template("workspace/task_rows.html", tasks=task_view.rows(attention[:10]))
        else:
            empty_state("Every scheduled task on this project is done.")

    if shell.role in ("admin", "pm", "tech_lead"):
        render_template("workspace/workload.html",
                        rows=[{**r, "initials": initials(r["name"])}
                              for r in metrics.workload(rows, members)])

    render_template("workspace/activity_feed.html", title="Recent activity",
                    updates=_feed(updates))
