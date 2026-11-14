"""Assistant — report progress and ask about status in plain language.

The flow mirrors the design: classify the message into an intent first, then
route it to a handler (FR-007, FR-008, FR-009). Status answers take their
numbers from the metrics engine, never from a model.

Right now the classifier is the keyword stand-in in ``components.assistant``.
Swapping it for the Groq call leaves this page unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from components import assistant as brain
from components.html import render_template, text_blocks
from components.shell import empty_state, page_header, render_shell
from components.ui import icon_rule, inject_css
from services import DataProviderError, workspace

SUGGESTIONS = [
    "How is the project doing?",
    "What is blocked right now?",
    "Anything overdue?",
    "How is the current sprint going?",
]
GREETING = ("Tell me what you worked on and I'll record it against the task, or ask me about "
            "progress and I'll answer from the live task data.")


def _history() -> list[dict[str, Any]]:
    return st.session_state.setdefault("chat_history", [])


def _say(role: str, text: str, intent: str | None = None) -> None:
    _history().append({"role": role, "text": text, "intent": intent})


def _handle(message: str, project: dict[str, Any], user_id: str) -> None:
    """Classify, then route — the same two steps the real assistant takes."""
    _say("user", message)
    intent = brain.classify(message)

    if intent == brain.UNKNOWN:
        _say("assistant", brain.rephrase_prompt(), intent)
        return

    try:
        tasks = workspace.list_tasks(project["id"])
        sprints = workspace.list_sprints(project["id"])
    except DataProviderError as exc:
        _say("assistant", f"I could not reach the project data: {exc}", intent)
        return

    if intent == brain.STATUS_QUERY:
        _say("assistant", brain.answer_status(message, project, tasks, sprints, user_id), intent)
        return

    open_tasks = [t for t in tasks if t["status"] != "done"] or tasks
    task, score = brain.resolve_task(message, open_tasks)
    if not task or score < 0.3:
        _say("assistant",
             "I could not tell which task that is about. Name it, or paste its id "
             f"(for example `{open_tasks[0]['id']}`) and I'll record the update.", intent)
        return

    extracted = brain.extract_update(message, task)
    try:
        workspace.post_task_update(
            task["id"], user_id, message, status_after=extracted["status"],
            progress_percentage=extracted["progress"], hours_logged=extracted["hours"],
            source="chat",
        )
    except DataProviderError as exc:
        _say("assistant", f"I could not save that update: {exc}", intent)
        return
    _say("assistant", brain.confirm_update(task, extracted), intent)


# ---- page -------------------------------------------------------------------

shell = render_shell("assistant", page_css="assistant.css")

with shell.main:
    with st.container(key="page_head", horizontal=True):
        page_header(
            "Assistant",
            "Report progress in your own words, or ask how the project is doing.",
            status=f"Answering about {shell.project['name']}" if shell.project
                   else "No project selected",
        )
        with st.container(key="head_actions", horizontal=True, wrap=False, width="content"):
            if st.button("Clear chat", key="clear_chat"):
                st.session_state["chat_history"] = []
                st.rerun()

    if not shell.project:
        empty_state("No project selected yet. Open one from Projects and come back.")
        st.stop()

    inject_css(icon_rule(".st-key-chat_send button", "send", size=15, color="var(--route)"))

    # Streamlit refuses a write to a widget's key once the widget exists, so the
    # box is emptied at the start of the run after a message is sent.
    if st.session_state.pop("chat_clear", False):
        st.session_state["chat_input"] = ""

    pending = st.session_state.pop("chat_pending", None)
    if pending:
        _handle(pending, shell.project, shell.user_id)

    history = _history()
    if not history:
        render_template("workspace/chat_intro.html", greeting=GREETING,
                        user_name=shell.user["name"].split()[0])
    else:
        render_template(
            "workspace/chat_log.html",
            messages=[{**m, "intent_label": brain.INTENT_LABELS.get(m.get("intent") or "", ""),
                       "blocks": text_blocks(m["text"])} for m in history],
        )

    with st.container(key="chat_suggestions", horizontal=True):
        for index, suggestion in enumerate(SUGGESTIONS):
            if st.button(suggestion, key=f"suggest_{index}"):
                st.session_state["chat_pending"] = suggestion
                st.rerun()

    with st.container(key="chat_box"):
        message = st.text_area(
            "Message", key="chat_input", label_visibility="collapsed",
            placeholder="e.g. finished the scorecard dashboard and opened it for review — "
                        "or ask: what is blocked right now?",
        )
        with st.container(key="chat_actions", horizontal=True):
            if st.button("Send", key="chat_send", type="primary"):
                if message.strip():
                    st.session_state["chat_pending"] = message.strip()
                    st.session_state["chat_clear"] = True
                    st.rerun()
                else:
                    st.error("Type a message first.")

    st.html(
        '<p class="hint-note">The assistant works out the intent first, then either records a '
        'progress note against the matching task or answers from the task data. Every figure in '
        'an answer is computed from the database, so the chat, the dashboard and the board always '
        'report the same number.</p>'
    )
