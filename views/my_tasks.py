"""My tasks — everything assigned to the signed-in person, and the day's update.

Use the "Viewing as" switcher in the rail to see this as someone else.
"""
from __future__ import annotations

import streamlit as st

from components import metrics, tasks as task_view
from components.html import render_template
from components.shell import empty_state, page_header, render_shell
from components.task_panel import render_detail, render_update_form
from services import DataProviderError, workspace

ASSISTANT_PAGE = "views/assistant.py"

shell = render_shell("my_tasks", page_css="board.css")

with shell.main:
    with st.container(key="page_head", horizontal=True):
        page_header(
            "My tasks",
            f"Work assigned to {shell.user['name']} · "
            f"{workspace.ROLE_LABELS.get(shell.role, shell.role)}.",
        )
        with st.container(key="head_actions", horizontal=True, wrap=False, width="content"):
            if st.button("Report by chat", key="to_assistant", type="primary"):
                st.switch_page(ASSISTANT_PAGE)

    everywhere = st.toggle("Show every project", key="mine_all_projects")
    try:
        mine = workspace.my_tasks(shell.user_id,
                                 None if everywhere else shell.project_id)
        load_error = None
    except DataProviderError as exc:
        mine, load_error = [], str(exc)
    if load_error:
        st.error(f"Could not load your tasks: {load_error}")

    open_tasks = [t for t in mine if t["status"] not in (metrics.DONE, metrics.BACKLOG)]
    overdue = metrics.overdue_tasks(mine)
    blocked = metrics.blocked_tasks(mine)
    logged, estimated = metrics.hours_progress(mine)

    render_template(
        "workspace/metric_grid.html",
        metrics=[
            {"label": "Open", "value": len(open_tasks), "note": "assigned to you"},
            {"label": "In progress", "value": sum(1 for t in mine if t["status"] == "in_progress"),
             "note": "started, not finished", "tone": "is-good" if open_tasks else ""},
            {"label": "Overdue", "value": len(overdue), "note": "past the due date",
             "tone": "is-bad" if overdue else "is-good"},
            {"label": "Blocked", "value": len(blocked), "note": "waiting on someone",
             "tone": "is-bad" if blocked else "is-good"},
        ],
    )

    if not mine:
        empty_state("Nothing is assigned to you here. Switch the project in the rail, or turn on "
                    "<strong>Show every project</strong>.")
        st.stop()

    needs_attention = task_view.sort_for_attention(
        [t for t in open_tasks if metrics.is_overdue(t) or t["status"] == metrics.BLOCKED])
    rest = task_view.sort_for_attention([t for t in open_tasks if t not in needs_attention])
    done = [t for t in mine if t["status"] == metrics.DONE]

    if needs_attention:
        st.html('<div class="section-label">Needs attention <span class="count">'
                f'{len(needs_attention)} tasks</span></div>')
        render_template("workspace/task_rows.html", tasks=task_view.rows(needs_attention))
    if rest:
        st.html('<div class="section-label">Open <span class="count">'
                f'{len(rest)} tasks</span></div>')
        render_template("workspace/task_rows.html", tasks=task_view.rows(rest))
    if done:
        st.html('<div class="section-label">Done <span class="count">'
                f'{len(done)} tasks</span></div>')
        render_template("workspace/task_rows.html", tasks=task_view.rows(done[:6]))

    # ---- report progress ----------------------------------------------------
    st.html('<div class="section-label">Report progress</div>')
    pickable = needs_attention + rest or mine
    ids = [t["id"] for t in pickable]
    by_id = {t["id"]: t for t in pickable}
    if st.session_state.get("mine_task") not in ids:
        st.session_state["mine_task"] = ids[0]
    selected = st.selectbox("Task", ids, key="mine_task",
                            format_func=lambda i: task_view.label(by_id[i]))
    task = by_id[selected]

    try:
        updates = workspace.list_task_updates(task_id=task["id"])
    except DataProviderError:
        updates = []
    render_detail(task, updates)
    if render_update_form(task, shell.user_id, key_prefix="mine"):
        st.rerun()
    st.html('<p class="hint-note">Posting an update records a progress note against the task and '
            'moves its status. The same thing happens when you report in through the Assistant.</p>')
