"""View helpers for generated documents: formatting and Markdown export."""
from __future__ import annotations

import io
import zipfile
from datetime import date
from typing import Any


def initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0] for p in parts[:2]).upper() if parts else "?"


def format_date(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d:%a}, {d:%b} {d.day}"


def sprint_dates(sprint: dict[str, Any]) -> str:
    end = date.fromisoformat(sprint["end_date"])
    return f"{format_date(sprint['start_date'])} – {format_date(sprint['end_date'])}, {end.year}"


def total_weeks(sprints: list[dict[str, Any]]) -> int:
    if not sprints:
        return 0
    start = min(date.fromisoformat(s["start_date"]) for s in sprints)
    end = max(date.fromisoformat(s["end_date"]) for s in sprints)
    return round(((end - start).days + 3) / 7)


def _item_text(item: Any) -> str:
    return f"{item['term']} — {item['text']}" if isinstance(item, dict) else str(item)


def _section_words(sections: list[dict[str, Any]]) -> int:
    words = 0
    for section in sections:
        words += len(section["heading"].split())
        for block in section["blocks"]:
            if block["type"] == "paragraph":
                words += len(block["text"].split())
            elif block["type"] == "list":
                words += sum(len(_item_text(i).split()) for i in block["items"])
            elif block["type"] == "scope":
                words += sum(len(i.split()) for i in block["in_scope"] + block["out_of_scope"])
    return words


def word_count_label(doc: dict[str, Any]) -> str:
    """Uses the API's ``word_count`` when provided, else counts the content."""
    count = doc.get("word_count") or _section_words(doc["sections"])
    return f"~{round(count, -1)} words"


# ---- Markdown export -----------------------------------------------------------

def _sections_md(title: str, sections: list[dict[str, Any]]) -> str:
    out = [f"# {title}", ""]
    for section in sections:
        out += [f"## {section['heading']}", ""]
        for block in section["blocks"]:
            if block["type"] == "paragraph":
                out += [block["text"], ""]
            elif block["type"] == "list":
                out += [
                    f"- **{i['term']}** — {i['text']}" if isinstance(i, dict) else f"- {i}"
                    for i in block["items"]
                ] + [""]
            elif block["type"] == "scope":
                out += ["**In scope**", ""] + [f"- {i}" for i in block["in_scope"]] + [""]
                out += ["**Out of scope (this phase)**", ""]
                out += [f"- {i}" for i in block["out_of_scope"]] + [""]
    return "\n".join(out)


def _sprints_md(sprints: list[dict[str, Any]]) -> str:
    out = ["# Sprint plan", ""]
    for s in sprints:
        out += [
            f"## Sprint {s['number']:02d} — {s['name']}",
            "",
            f"*{sprint_dates(s)}*",
            "",
            s["goal"],
            "",
            f"Team: {', '.join(s['members'])} ({len(s['members'])} members · ~{s['capacity_hours']} hrs capacity)",
            "",
        ]
    return "\n".join(out)


def _tasks_md(sprints: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> str:
    out = ["# Task breakdown", ""]
    for s in sprints:
        out += [f"## Sprint {s['number']} — {s['name']}", "",
                "| Task | Area | Assignee | Priority | Est. |", "|---|---|---|---|---|"]
        out += [
            f"| {t['title']} | {t['area']} | {t['assignee']} | {t['priority']} | {t['estimate_hours']}h |"
            for t in tasks if t["sprint"] == s["number"]
        ] + [""]
    return "\n".join(out)


def _tests_md(test_cases: list[dict[str, Any]]) -> str:
    out = ["# Test cases", ""]
    for tc in test_cases:
        out += [
            f"## {tc['id']} — {tc['title']} ({tc['priority']})",
            "",
            f"Feature: {tc['feature']}",
            "",
            f"**Precondition:** {tc['precondition']}",
            "",
            "**Steps:**",
            "",
        ]
        out += [f"{i}. {step}" for i, step in enumerate(tc["steps"], 1)]
        out += ["", f"**Expected result:** {tc['expected_result']}", ""]
    return "\n".join(out)


def to_markdown_files(docs: dict[str, Any]) -> dict[str, str]:
    return {
        "problem-statement.md": _sections_md("Problem statement", docs["problem_statement"]["sections"]),
        "project-description.md": _sections_md("Project description", docs["project_description"]["sections"]),
        "sprint-plan.md": _sprints_md(docs["sprints"]),
        "task-breakdown.md": _tasks_md(docs["sprints"], docs["tasks"]),
        "test-cases.md": _tests_md(docs["test_cases"]),
    }


def export_zip(docs: dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in to_markdown_files(docs).items():
            zf.writestr(name, content)
    return buf.getvalue()
