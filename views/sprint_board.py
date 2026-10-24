"""Sprint board — every task in the sprint, grouped by status.

The board itself is read-only; pick a task underneath it to see the detail and
post an update. Statuses are the ones in the tasks table.
"""
from __future__ import annotations

import streamlit as st

from components import metrics, tasks as task_view
from components.html import render_template
from components.shell import empty_state, page_header, render_shell
from components.task_panel import render_detail, render_update_form
from services import DataProviderError, workspace

ALL_SPRINTS = "__all__"
BACKLOG = "__backlog__"

shell = render_shell("board", page_css="board.css", wide=True)

with shell.main:
    if not shell.project:
        page_header("Sprint board")
        empty_state("No project selected yet. Open one from Projects.")
        st.stop()

    project = shell.project
    try:
        all_tasks = workspace.list_tasks(project["id"])
        sprints = workspace.list_sprints(project["id"])
        members = workspace.list_members(project["id"])
        load_error = None
    except DataProviderError as exc:
        all_tasks, sprints, members, load_error = [], [], [], str(exc)

    current = workspace.current_sprint(project["id"])
    options = [s["id"] for s in sprints] + [BACKLOG, ALL_SPRINTS]
    labels = {s["id"]: f"Sprint {s['sprint_number']} · {s['name']}" for s in sprints}
    labels[BACKLOG] = "Backlog"
    labels[ALL_SPRINTS] = "All sprints"
    st.session_state.setdefault("board_sprint", current["id"] if current else ALL_SPRINTS)

    with st.container(key="page_head", horizontal=True):
        page_header(
            "Sprint board",
            f"{project['name']} — drag-free board: pick a task below to open it and report "
            "progress.",
        )

    if load_error:
        st.error(f"Could not load the board: {load_error}")

    with st.container(key="board_filters", horizontal=True):
        sprint_choice = st.selectbox("Sprint", options, key="board_sprint",
                                     format_func=lambda s: labels.get(s, s))
        people = [m["user_id"] for m in members]
        name_by_id = {m["user_id"]: m["name"] for m in members}
        assignee = st.selectbox("Assignee", [None, *people], key="board_assignee",
                                format_func=lambda u: "Everyone" if u is None else name_by_id.get(u, u))
        priority = st.selectbox("Priority", [None, *workspace.PRIORITIES], key="board_priority",
                                format_func=lambda p: "Any priority" if p is None else p.capitalize())

    shown = all_tasks
    if sprint_choice == BACKLOG:
        shown = [t for t in shown if not t.get("sprint_id")]
    elif sprint_choice != ALL_SPRINTS:
        shown = [t for t in shown if t.get("sprint_id") == sprint_choice]
    if assignee:
        shown = [t for t in shown if t.get("assignee_id") == assignee]
    if priority:
        shown = [t for t in shown if t.get("priority") == priority]

    statuses = [s for s in workspace.STATUSES
                if s != metrics.BACKLOG or sprint_choice in (BACKLOG, ALL_SPRINTS)]
    columns = [{
        "status": status,
        "label": workspace.STATUS_LABELS[status],
        "tasks": task_view.rows(task_view.sort_for_board(
            [t for t in shown if t.get("status") == status])),
    } for status in statuses]

    logged, estimated = metrics.hours_progress(shown)
    render_template(
        "workspace/metric_grid.html",
        metrics=[
            {"label": "In this view", "value": len(shown), "note": labels.get(sprint_choice, "")},
            {"label": "Complete", "value": f"{metrics.percent_complete(shown)}%",
             "note": "of the scheduled tasks", "tone": "is-good"},
            {"label": "Blocked", "value": len(metrics.blocked_tasks(shown)),
             "note": "waiting on something",
             "tone": "is-bad" if metrics.blocked_tasks(shown) else ""},
            {"label": "Hours", "value": f"{logged:g}", "note": f"logged of {estimated:g} estimated"},
        ],
    )

    if shown:
        render_template("workspace/board.html", columns=columns)
    else:
        empty_state("No tasks match these filters.")

    # ---- open one task ------------------------------------------------------
    st.html('<div class="section-label">Task detail</div>')
    pickable = task_view.sort_for_board(shown)
    if not pickable:
        empty_state("Pick a sprint with tasks in it to open one here.")
        st.stop()

    ids = [t["id"] for t in pickable]
    by_id = {t["id"]: t for t in pickable}
    if st.session_state.get("board_task") not in ids:
        st.session_state["board_task"] = ids[0]
    selected_id = st.selectbox("Open a task", ids, key="board_task",
                               format_func=lambda i: f"{i} · {task_view.label(by_id[i])}")
    task = by_id[selected_id]

    try:
        updates = workspace.list_task_updates(task_id=task["id"])
    except DataProviderError:
        updates = []
    render_detail(task, updates)
    if render_update_form(task, shell.user_id, key_prefix="board"):
        st.rerun()
