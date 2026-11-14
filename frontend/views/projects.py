"""Projects — the portfolio a person can see, with health computed from their tasks.

Which projects appear depends on the signed-in role (FR-011): directors and
project managers see everything, everyone else sees the projects they are on.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from components import metrics
from components.documents import initials
from components.html import render_template
from components.shell import empty_state, page_header, render_shell, select_project
from components.ui import icon_rule, inject_css
from services import DataProviderError, workspace

DASHBOARD_PAGE = "views/dashboard.py"
CREATE_PROJECT_PAGE = "views/create_project.py"

TYPE_LABELS = {"web_app": "Web app", "mobile_app": "Mobile app", "api": "API / backend",
               "backend": "Backend", "platform": "Platform", "internal_tool": "Internal tool"}
STATUS_FILTERS = ["All", "Active", "Draft", "On hold", "Completed", "Archived"]
BAR_CLASS = {"on_track": "is-good", "at_risk": "is-warn", "behind": "is-bad"}


def _open(project_id: str) -> None:
    select_project(project_id)
    st.session_state["app_open_dashboard"] = True


def _summary(project: dict[str, Any]) -> dict[str, Any]:
    """Everything the card shows, computed from the project's own tasks."""
    tasks = workspace.list_tasks(project["id"])
    members = workspace.list_members(project["id"])
    scheduled = metrics.scheduled(tasks)
    health = metrics.health(project, tasks)
    done = sum(1 for t in scheduled if t["status"] == metrics.DONE)
    percent = metrics.percent_complete(tasks)
    return {
        "project": project,
        "type_label": TYPE_LABELS.get(project.get("type", ""), project.get("type", "Project")),
        "health": health,
        # A project with no tasks has not started, so health would read as "on track".
        "health_label": metrics.HEALTH_LABELS[health] if scheduled else "Not started",
        "bar_class": BAR_CLASS[health],
        "percent": percent if scheduled else 0,
        "percent_label": f"{percent}%" if scheduled else "—",
        "count_label": f"{done} of {len(scheduled)} tasks done" if scheduled
                       else "No tasks generated yet",
        "members": [{"name": m["name"], "initials": initials(m["name"])} for m in members],
        "dates": metrics.date_range(project.get("start_date"), project.get("preferred_end_date")),
        "risk_count": len(metrics.risk_flags(project, tasks)),
    }


# ---- page -------------------------------------------------------------------

shell = render_shell("projects", page_css="projects.css")

if st.session_state.pop("app_open_dashboard", False):
    st.switch_page(DASHBOARD_PAGE)

inject_css(icon_rule(".st-key-new_project button", "plus", size=15, stroke_width=2,
                     color="var(--route)"))

with shell.main:
    try:
        summaries = [_summary(p) for p in shell.projects]
        load_error = None
    except DataProviderError as exc:
        summaries, load_error = [], str(exc)

    counts = {
        "total": len(summaries),
        "active": sum(1 for s in summaries if s["project"].get("status") == "active"),
        "attention": sum(1 for s in summaries if s["health"] != "on_track"),
        "risks": sum(s["risk_count"] for s in summaries),
    }

    with st.container(key="page_head", horizontal=True):
        page_header(
            "Projects",
            "Every project you can see, with progress and risk worked out from its own tasks."
            if shell.role in ("admin", "pm")
            else "The projects you are assigned to.",
        )
        with st.container(key="head_actions", horizontal=True, wrap=False, width="content"):
            if st.button("New project", key="new_project", type="primary"):
                st.switch_page(CREATE_PROJECT_PAGE)

    if load_error:
        st.error(f"Could not load projects: {load_error}")

    render_template(
        "workspace/metric_grid.html",
        metrics=[
            {"label": "Projects", "value": counts["total"], "note": "visible to you"},
            {"label": "Active", "value": counts["active"], "note": "in flight now",
             "tone": "is-good" if counts["active"] else ""},
            {"label": "Need attention", "value": counts["attention"],
             "note": "at risk or behind", "tone": "is-warn" if counts["attention"] else ""},
            {"label": "Open risks", "value": counts["risks"], "note": "across all projects",
             "tone": "is-bad" if counts["risks"] else ""},
        ],
    )

    with st.container(key="proj_filters", horizontal=True):
        status_filter = st.selectbox("Status", STATUS_FILTERS, key="proj_status")
        sort_by = st.selectbox("Sort by", ["Needs attention", "Name", "Progress"], key="proj_sort")

    shown = summaries
    if status_filter != "All":
        wanted = status_filter.lower().replace(" ", "_")
        shown = [s for s in shown if s["project"].get("status") == wanted]
    order = {"behind": 0, "at_risk": 1, "on_track": 2}
    if sort_by == "Needs attention":
        shown = sorted(shown, key=lambda s: (order[s["health"]], s["project"]["name"]))
    elif sort_by == "Name":
        shown = sorted(shown, key=lambda s: s["project"]["name"])
    else:
        shown = sorted(shown, key=lambda s: -s["percent"])

    if not shown and not load_error:
        empty_state("No projects match this filter. Clear the filter, or set up a new project.")

    for summary in shown:
        project_id = summary["project"]["id"]
        is_current = project_id == shell.project_id
        with st.container(key=f"proj_card_{project_id}"):
            render_template("workspace/project_card.html", **summary)
            st.button("Open project", key=f"open_proj_{project_id}", on_click=_open,
                      args=(project_id,), width="content")
        if is_current:
            inject_css(f".stApp .st-key-proj_card_{project_id} {{ border-color: var(--accent);"
                       " box-shadow: 0 0 0 3px var(--accent-soft); }")
