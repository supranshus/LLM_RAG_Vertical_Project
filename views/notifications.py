"""Notifications and alerts — what needs attention, and why (FR-010, FR-012).

Alerts are shown in-app only; there is no email, push or SMS in this phase.
Detection is deterministic (``components.metrics.risk_flags``); the wording of
each message is what a model drafts from a flag.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from components import metrics
from components.html import render_template
from components.shell import empty_state, page_header, render_shell
from services import DataProviderError, workspace

CATEGORY_LABELS = {"risk_alert": "Risk alert", "ai_generation": "Generation",
                   "task_update": "Task update", "sprint_event": "Sprint"}
CATEGORY_TAGS = {"risk_alert": "critical", "ai_generation": "frontend",
                 "task_update": "backend", "sprint_event": "pm"}
ENTITY_LABELS = {"project": "Project", "task": "Task", "sprint": "Sprint",
                 "generation_job": "Generation job", "document": "Document"}
LIFECYCLE_LABELS = {"active": "Needs attention", "acknowledged": "Acknowledged",
                    "resolved": "Resolved", "dismissed": "Dismissed"}
LIFECYCLE_BADGES = {"active": "blocked", "acknowledged": "in_progress",
                    "resolved": "done", "dismissed": "backlog"}
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _set(notification_id: str, lifecycle: str) -> None:
    try:
        workspace.set_notification_lifecycle(notification_id, lifecycle)
        st.toast(f"Alert {lifecycle}")
    except DataProviderError as exc:
        st.session_state["ntf_error"] = str(exc)


shell = render_shell("notifications", page_css="notifications.css")

with shell.main:
    with st.container(key="page_head", horizontal=True):
        page_header(
            "Notifications & alerts",
            f"Raised for {shell.user['name']} as "
            f"{workspace.ROLE_LABELS.get(shell.role, shell.role).lower()}. "
            "Shown in the app only — nothing is emailed or pushed in this phase.",
        )

    error = st.session_state.pop("ntf_error", None)
    if error:
        st.error(f"Could not update the alert: {error}")

    try:
        items = workspace.list_notifications(shell.user_id)
        load_error = None
    except DataProviderError as exc:
        items, load_error = [], str(exc)
    if load_error:
        st.error(f"Could not load alerts: {load_error}")

    active = [n for n in items if n["lifecycle_status"] == "active"]
    render_template(
        "workspace/metric_grid.html",
        metrics=[
            {"label": "Needs attention", "value": len(active), "note": "still open",
             "tone": "is-bad" if active else "is-good"},
            {"label": "Critical & high", "value": sum(1 for n in active
                                                      if n["severity"] in ("critical", "high")),
             "note": "of the open alerts", "tone": "is-warn"},
            {"label": "Acknowledged", "value": sum(1 for n in items
                                                   if n["lifecycle_status"] == "acknowledged"),
             "note": "seen, not closed"},
            {"label": "Closed", "value": sum(1 for n in items if n["lifecycle_status"]
                                             in ("resolved", "dismissed")),
             "note": "resolved or dismissed", "tone": "is-good"},
        ],
    )

    with st.container(key="ntf_filters", horizontal=True):
        category = st.selectbox("Category", [None, *CATEGORY_LABELS],
                                format_func=lambda c: "All categories" if c is None
                                else CATEGORY_LABELS[c], key="ntf_category")
        severity = st.selectbox("Severity", [None, "critical", "high", "medium", "low", "info"],
                                format_func=lambda s: "Any severity" if s is None
                                else s.capitalize(), key="ntf_severity")
    with st.container(key="ntf_toggles", horizontal=True):
        only_project = st.toggle("This project only", key="ntf_project_only")
        show_closed = st.toggle("Show closed alerts", key="ntf_show_closed")

    shown = items
    if not show_closed:
        shown = [n for n in shown if n["lifecycle_status"] in ("active", "acknowledged")]
    if category:
        shown = [n for n in shown if n["category"] == category]
    if severity:
        shown = [n for n in shown if n["severity"] == severity]
    if only_project and shell.project_id:
        shown = [n for n in shown if n["project_id"] == shell.project_id]
    shown = sorted(shown, key=lambda n: (n["lifecycle_status"] != "active",
                                         SEVERITY_ORDER.get(n["severity"], 9),
                                         n.get("created_at", "")))

    if not shown:
        empty_state("Nothing needs your attention right now. Turn on "
                    "<strong>Show closed alerts</strong> to see what has already been handled.")

    for item in shown:
        with st.container(key=f"ntf_card_{item['id']}"):
            render_template(
                "workspace/notification_card.html",
                item=item,
                when=metrics.relative_day(item.get("created_at")),
                category_label=CATEGORY_LABELS.get(item["category"], item["category"]),
                category_tag=CATEGORY_TAGS.get(item["category"], "pm"),
                entity_label=ENTITY_LABELS.get(item["entity_type"], item["entity_type"]),
                lifecycle_label=LIFECYCLE_LABELS.get(item["lifecycle_status"], ""),
                lifecycle_badge=LIFECYCLE_BADGES.get(item["lifecycle_status"], "todo"),
            )
            if item["lifecycle_status"] in ("active", "acknowledged"):
                with st.container(key=f"ntf_actions_{item['id']}", horizontal=True):
                    if item["lifecycle_status"] == "active":
                        st.button("Acknowledge", key=f"ack_{item['id']}", on_click=_set,
                                  args=(item["id"], "acknowledged"))
                    st.button("Resolve", key=f"res_{item['id']}", on_click=_set,
                              args=(item["id"], "resolved"))
                    st.button("Dismiss", key=f"dis_{item['id']}", on_click=_set,
                              args=(item["id"], "dismissed"))

    # ---- what the detector sees right now -----------------------------------
    st.html('<div class="section-label">Risk check</div>')
    if not shell.project:
        empty_state("Select a project to run the risk check against it.")
    else:
        try:
            project_tasks = workspace.list_tasks(shell.project["id"])
            flags = metrics.risk_flags(shell.project, project_tasks)
        except DataProviderError:
            flags = []
        render_template(
            "workspace/risk_list.html",
            title=f"Risk check — {shell.project['name']}", flags=flags,
            note="This runs the same rules the alerts above come from: blocked work, anything "
                 "past its due date, and a project whose elapsed schedule has run ahead of the "
                 "work completed. Detection is rules only — a model is used just to word the "
                 "message a person reads.",
        )
