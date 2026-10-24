"""The task detail panel and the "post an update" form.

Shared by the sprint board and My tasks so a task reads and behaves the same on
both. Posting an update writes a progress note and moves the task to match it
(FR-008).
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from components import metrics
from components.documents import initials
from components.html import render_template, text_blocks
from services import DataProviderError, workspace


def update_feed(updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**u, "initials": initials(u.get("author_name") or "?"),
             "when": metrics.relative_day(u.get("created_at"))} for u in updates]


def _facts(task: dict[str, Any]) -> list[dict[str, str]]:
    logged = float(task.get("actual_hours") or 0)
    estimated = float(task.get("estimated_hours") or 0)
    return [
        {"label": "Assignee", "value": task.get("assignee_name") or "Unassigned"},
        {"label": "Sprint", "value": task.get("sprint_name") or "Backlog"},
        {"label": "Due", "value": (f"{metrics.short_date(task.get('due_date'))}"
                                   f" · {metrics.relative_day(task.get('due_date'))}")
                                  if task.get("due_date") else "No date"},
        {"label": "Estimate", "value": f"{logged:g}h logged of {estimated:g}h"},
        {"label": "Story points", "value": str(task.get("story_points") or "–")},
    ]


def render_detail(task: dict[str, Any], updates: list[dict[str, Any]]) -> None:
    render_template(
        "workspace/task_detail.html",
        task=task,
        status_label=workspace.STATUS_LABELS.get(task.get("status", ""), ""),
        is_late=metrics.is_overdue(task),
        description_blocks=text_blocks(str(task.get("description") or "")),
        facts=_facts(task),
        updates=update_feed(updates),
    )


def render_update_form(task: dict[str, Any], author_id: str, *, key_prefix: str) -> bool:
    """The update composer. Returns True when an update was posted."""
    posted = False
    # Streamlit refuses a write to a widget's key once the widget exists, so the
    # box is emptied at the start of the run after a successful post.
    if st.session_state.pop(f"{key_prefix}_clear", False):
        st.session_state[f"{key_prefix}_note"] = ""
    with st.container(key=f"{key_prefix}_post_composer"):
        st.html('<p class="composer-label">Post an update</p>')
        note = st.text_area(
            "Update", key=f"{key_prefix}_note", label_visibility="collapsed",
            placeholder="What moved today? For example: finished the retry logic, waiting on "
                        "review from Rohit.",
        )
        with st.container(key=f"{key_prefix}_post_fields", horizontal=True):
            status = st.selectbox(
                "Status", workspace.STATUSES,
                index=workspace.STATUSES.index(task.get("status", "todo"))
                if task.get("status") in workspace.STATUSES else 1,
                format_func=lambda s: workspace.STATUS_LABELS[s], key=f"{key_prefix}_status",
            )
            hours = st.number_input("Hours logged", min_value=0.0, max_value=24.0, step=0.5,
                                    value=0.0, key=f"{key_prefix}_hours")
        progress = st.slider("Progress", 0, 100, step=5, key=f"{key_prefix}_progress",
                             value=100 if task.get("status") == metrics.DONE else 0,
                             format="%d%%")
        with st.container(key=f"{key_prefix}_post_actions", horizontal=True):
            blocker = st.button("Flag as blocked", key=f"{key_prefix}_block")
            send = st.button("Post update", key=f"{key_prefix}_post", type="primary")

        if send or blocker:
            if not note.strip():
                st.error("Write a short note so the update has something to say.")
            else:
                try:
                    workspace.post_task_update(
                        task["id"], author_id, note,
                        status_after=metrics.BLOCKED if blocker else status,
                        progress_percentage=progress, hours_logged=float(hours), source="form",
                    )
                    st.session_state[f"{key_prefix}_clear"] = True
                    st.toast("Update posted")
                    posted = True
                except DataProviderError as exc:
                    st.error(f"Could not post the update: {exc}")
    return posted
