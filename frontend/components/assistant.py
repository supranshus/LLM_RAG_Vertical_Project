"""A stand-in for the conversational assistant, so the chat page works on mocks.

The real assistant classifies the message with the fast model, then routes it to
a handler (FR-007, FR-008). This module keeps that shape — ``classify`` then a
handler — but uses keyword rules instead of a model call, so the page can be
built and demonstrated before the backend exists.

The split that matters is kept: **numbers are computed in Python**, in
``components.metrics``. Only the sentence around them would come from a model.
Replace ``classify``, ``extract_update`` and the phrasing in ``answer_status``
with Groq calls and the page itself does not change.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from components import metrics
from services.workspace import STATUS_LABELS

TASK_UPDATE = "TASK_UPDATE"
STATUS_QUERY = "STATUS_QUERY"
UNKNOWN = "UNKNOWN"

INTENT_LABELS = {TASK_UPDATE: "Task update", STATUS_QUERY: "Status question", UNKNOWN: "Unclear"}

_QUESTION_WORDS = ("what", "how", "when", "which", "who", "why", "where", "is ", "are ", "show",
                   "list", "status", "progress", "behind", "on track", "left", "remaining",
                   "any", "anything", "tell me", "give me", "do we", "did we", "?")
# Words that ask about the state of the work rather than report on it.
_QUERY_TOPICS = ("overdue", "at risk", "on track", "how many", "how much", "what's left",
                 "whats left", "summary", "workload")
_UPDATE_WORDS = ("finished", "done", "completed", "started", "working on", "wip", "in progress",
                 "blocked", "waiting on", "stuck", "review", "pushed", "merged", "fixed",
                 "deployed", "wrapped up", "picked up", "logged")
_BLOCKED_WORDS = ("blocked", "waiting on", "stuck", "can't", "cannot", "held up")
_DONE_WORDS = ("finished", "done", "completed", "wrapped up", "shipped", "merged and deployed")
_REVIEW_WORDS = ("review", "pr open", "raised a pr", "opened a pr")


def classify(message: str) -> str:
    """TASK_UPDATE, STATUS_QUERY or UNKNOWN.

    A question wins over an update when the message asks something; otherwise a
    progress verb makes it an update.
    """
    text = message.lower().strip()
    if not text:
        return UNKNOWN
    asks = (text.endswith("?")
            or any(text.startswith(w) for w in _QUESTION_WORDS)
            or any(topic in text for topic in _QUERY_TOPICS))
    reports = any(w in text for w in _UPDATE_WORDS)
    if asks and not text.startswith(("i ", "we ", "just ")):
        return STATUS_QUERY
    if reports:
        return TASK_UPDATE
    if asks:
        return STATUS_QUERY
    return UNKNOWN


# ---- task update ------------------------------------------------------------

def _score(text: str, task: dict[str, Any]) -> float:
    """How well a message matches a task: id, then words, then fuzzy title.

    Matching more distinct words counts for something of its own, so a short
    title like "End-to-end scorecard QA" — one long word — cannot tie with
    "Fix scorecard export to CSV" when the message names both of its words.
    """
    text = text.lower()
    if task["id"].lower() in text:
        return 1.0
    title = task["title"].lower()
    words = {w for w in re.findall(r"[a-z]{4,}", title)}
    hits = sum(1 for w in words if w in text)
    coverage = hits / len(words) if words else 0.0
    specificity = hits / (hits + 1)  # 0.50 for one word, 0.67 for two, 0.75 for three
    return max(0.6 * coverage + 0.4 * specificity,
               SequenceMatcher(None, title, text).ratio() * 0.8)


def resolve_task(message: str, tasks: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    """Best-matching task and its score. Below ~0.3 treat it as no match."""
    if not tasks:
        return None, 0.0
    best = max(tasks, key=lambda t: _score(message, t))
    return best, _score(message, best)


def extract_update(message: str, task: dict[str, Any]) -> dict[str, Any]:
    """Pull a status and a progress figure out of a plain-language update."""
    text = message.lower()
    status = task.get("status", "todo")
    if any(w in text for w in _BLOCKED_WORDS):
        status = "blocked"
    elif any(w in text for w in _DONE_WORDS):
        status = "done"
    elif any(w in text for w in _REVIEW_WORDS):
        status = "in_review"
    elif task.get("status") in ("todo", "backlog", "blocked"):
        status = "in_progress"

    percent = None
    match = re.search(r"(\d{1,3})\s?%", text)
    if match:
        percent = min(100, int(match.group(1)))
    elif status == "done":
        percent = 100

    hours = 0.0
    match = re.search(r"(\d+(?:\.\d+)?)\s?(?:h|hr|hrs|hours?)\b", text)
    if match:
        hours = float(match.group(1))
    return {"status": status, "progress": percent, "hours": hours}


def confirm_update(task: dict[str, Any], extracted: dict[str, Any]) -> str:
    """What the assistant says back after recording an update."""
    parts = [f"Recorded against **{task['title']}**.",
             f"Status is now **{STATUS_LABELS.get(extracted['status'], extracted['status'])}**."]
    if extracted.get("hours"):
        parts.append(f"Logged {extracted['hours']:g}h.")
    if extracted["status"] == "blocked":
        parts.append("It is flagged as blocked, so it will show up on the project's alerts.")
    return " ".join(parts)


# ---- status questions -------------------------------------------------------

def answer_status(question: str, project: dict[str, Any], tasks: list[dict[str, Any]],
                  sprints: list[dict[str, Any]], user_id: str | None = None) -> str:
    """Answer from the metrics engine. Every figure here is computed, never guessed."""
    text = question.lower()
    scheduled = metrics.scheduled(tasks)
    percent = metrics.percent_complete(tasks)
    overdue = metrics.overdue_tasks(tasks)
    blocked = metrics.blocked_tasks(tasks)
    health = metrics.health(project, tasks)

    if any(w in text for w in ("blocked", "stuck", "waiting")):
        if not blocked:
            return "Nothing is blocked on this project right now."
        lines = [f"{len(blocked)} task{'' if len(blocked) == 1 else 's'} blocked on "
                 f"**{project['name']}**:"]
        lines += [f"- **{t['title']}** — {t.get('assignee_name') or 'unassigned'}"
                  f"{', due ' + metrics.short_date(t['due_date']) if t.get('due_date') else ''}"
                  for t in blocked]
        return "\n".join(lines)

    if any(w in text for w in ("overdue", "late", "past due", "missed")):
        if not overdue:
            return "No task is past its due date."
        lines = [f"{len(overdue)} task{'' if len(overdue) == 1 else 's'} past the due date:"]
        lines += [f"- **{t['title']}** — due {metrics.short_date(t['due_date'])}"
                  f" ({metrics.relative_day(t['due_date'])}), "
                  f"{t.get('assignee_name') or 'unassigned'}" for t in overdue]
        return "\n".join(lines)

    if any(w in text for w in ("sprint", "this week", "current")):
        current = next((s for s in sprints if s.get("status") == "active"), None) \
            or (sprints[-1] if sprints else None)
        if not current:
            return "This project has no sprints yet."
        progress = metrics.sprint_progress(current, tasks)
        return (f"**{current['name']}** ({metrics.date_range(current['start_date'], current['end_date'])}) "
                f"is {progress['percent']}% complete: {progress['done_count']} of "
                f"{progress['task_count']} tasks done, {progress['open_count']} still open. "
                f"{progress['hours_logged']:g}h logged against {progress['hours_estimated']:g}h estimated.")

    if any(w in text for w in ("who", "workload", "busy", "team")) and user_id is None:
        by_person: dict[str, int] = {}
        for task in scheduled:
            if task["status"] != metrics.DONE and task.get("assignee_name"):
                by_person[task["assignee_name"]] = by_person.get(task["assignee_name"], 0) + 1
        if not by_person:
            return "Nobody has open work on this project."
        ranked = sorted(by_person.items(), key=lambda kv: -kv[1])
        lines = ["Open tasks per person:"] + [f"- {n}: {c}" for n, c in ranked]
        return "\n".join(lines)

    if any(w in text for w in ("my", "mine", "i have")) and user_id:
        mine = [t for t in scheduled
                if t.get("assignee_id") == user_id and t["status"] != metrics.DONE]
        if not mine:
            return "You have nothing open on this project."
        lines = [f"You have {len(mine)} open task{'' if len(mine) == 1 else 's'}:"]
        lines += [f"- **{t['title']}** — {STATUS_LABELS.get(t['status'], t['status'])}"
                  f"{', due ' + metrics.short_date(t['due_date']) if t.get('due_date') else ''}"
                  for t in mine]
        return "\n".join(lines)

    # Default: overall status.
    done = sum(1 for t in scheduled if t["status"] == metrics.DONE)
    left = metrics.days_left(project)
    answer = (f"**{project['name']}** is {percent}% complete — {done} of {len(scheduled)} "
              f"scheduled tasks are done, and it is **{metrics.HEALTH_LABELS[health].lower()}**.")
    if left is not None:
        answer += (f" There {'is' if abs(left) == 1 else 'are'} {abs(left)} day"
                   f"{'' if abs(left) == 1 else 's'} "
                   f"{'left before' if left >= 0 else 'past'} the preferred end date "
                   f"({metrics.short_date(project.get('preferred_end_date'))}).")
    if overdue or blocked:
        answer += (f" {len(overdue)} task{'' if len(overdue) == 1 else 's'} overdue and "
                   f"{len(blocked)} blocked.")
    return answer


def rephrase_prompt() -> str:
    return ("I could not tell whether that was a progress update or a question. Try something "
            "like *\"finished the scorecard dashboard, opened it for review\"* or "
            "*\"what is blocked right now?\"*")
