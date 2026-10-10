"""Generated documents — port of generated-documents.html."""
from __future__ import annotations

from typing import Any

import streamlit as st

from components.documents import export_zip, initials, sprint_dates, total_weeks, word_count_label
from components.html import render_template
from components.layout import safe_load
from components.ui import icon_rule, inject_css, load_css
from config.settings import get_settings
from services import DataProviderError
from services import projects

CREATE_PROJECT_PAGE = "views/create_project.py"

# key -> (sidebar label, sidebar icon, toolbar icon, filename)
DOCS = {
    "problem": ("Problem statement", "alert", "file", "problem-statement.md"),
    "description": ("Project description", "file-text", "file", "project-description.md"),
    "sprints": ("Sprint plan", "calendar", "calendar-sm", "sprint-plan.md"),
    "tasks": ("Task breakdown", "checklist", "checklist-sm", "task-breakdown.md"),
    "tests": ("Test cases", "shield", "shield", "test-cases.md"),
}


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _select_doc(key: str) -> None:
    st.query_params["doc"] = key


def _project_id() -> str | None:
    pid = st.query_params.get("project_id") or st.session_state.get("cp_project_id")
    # Mock mode serves the same sample documents for any id, so the page works standalone.
    return pid or ("demo" if get_settings().use_mock else None)


def _project_name(project_id: str, docs: dict[str, Any]) -> str:
    try:
        name = projects.get_project(project_id).get("name")
    except DataProviderError:
        name = None
    return name or docs.get("project_name") or "Untitled project"


def _panel_context(key: str, docs: dict[str, Any]) -> dict[str, Any]:
    _, _, toolbar_icon, filename = DOCS[key]
    ctx: dict[str, Any] = {"toolbar_icon": toolbar_icon, "filename": filename, "initials": initials}
    sprints = docs["sprints"]
    if key in ("problem", "description"):
        doc = docs["problem_statement" if key == "problem" else "project_description"]
        ctx.update(kind="sections", doc=doc, meta=word_count_label(doc))
    elif key == "sprints":
        ctx.update(
            kind="sprints",
            sprints=[{**s, "dates": sprint_dates(s)} for s in sprints],
            meta=f"{_plural(len(sprints), 'sprint')} · {_plural(total_weeks(sprints), 'week')}",
        )
    elif key == "tasks":
        groups = [{"sprint": s, "tasks": [t for t in docs["tasks"] if t["sprint"] == s["number"]]}
                  for s in sprints]
        ctx.update(kind="tasks", task_groups=groups, meta=_plural(len(docs["tasks"]), "task"))
    else:
        ctx.update(kind="tests", test_cases=docs["test_cases"],
                   meta=_plural(len(docs["test_cases"]), "test case"))
    return ctx


# ---- page -------------------------------------------------------------------

load_css("theme.css", "generated_documents.css")

active = st.query_params.get("doc", "problem")
if active not in DOCS:
    active = "problem"

css = [
    # Sidebar icons (before label) and check marks (after label).
    icon_rule(f".st-key-doc_{k} .stButton button", meta[1], size=17, color="rgba(255,255,255,0.4)")
    for k, meta in DOCS.items()
]
css += [
    icon_rule('[class*="st-key-doc_"] .stButton button', "check", size=15, stroke_width=2,
              color="rgba(51,210,160,0.65)", pseudo="after"),
    f".stApp .st-key-doc_{active} .stButton button, .stApp .st-key-doc_{active} .stButton button:hover,"
    f" .stApp .st-key-doc_{active} .stButton button:focus:not(:active)"
    " { background: rgba(51,210,160,0.14); color: #fff; }",
    f".stApp .st-key-doc_{active} .stButton button::before {{ background-color: var(--route); }}",
    icon_rule(".st-key-export button", "download", size=15, color="var(--route)"),
]
inject_css("\n".join(css))

project_id = _project_id()
docs = safe_load(lambda: projects.get_documents(project_id), "Loading documents...") if project_id else None
project_name = _project_name(project_id, docs) if docs else "Generated documents"

with st.container(key="layout"):
    rail_col, main_col = st.columns([250, 700])

with rail_col, st.container(key="rail"):
    render_template("generated_documents/brand.html", project_name=project_name)
    for key, (label, *_rest) in DOCS.items():
        st.button(label, key=f"doc_{key}", width="stretch", on_click=_select_doc, args=(key,))

with main_col, st.container(key="main"):
    with st.container(key="viewer_header", horizontal=True):
        if docs:
            ready = len(DOCS)
            status_text = (f"Generation complete · {ready} documents ready"
                           if docs.get("status", "complete") == "complete"
                           else f"Generation {docs['status']}")
            render_template(
                "generated_documents/header.html",
                project_name=project_name,
                status_text=status_text,
                chips=[_plural(len(docs["sprints"]), "sprint"), _plural(len(docs["tasks"]), "task"),
                       _plural(len(docs["test_cases"]), "test case")],
            )
        else:
            st.html('<h1 class="viewer-title">Generated documents</h1>')
        with st.container(key="header_actions", horizontal=True, wrap=False, width="content"):
            if st.button("Back to project setup", key="back"):
                st.switch_page(CREATE_PROJECT_PAGE)
            if docs:
                st.download_button(
                    "Export all",
                    data=export_zip(docs),
                    file_name=f"{project_name.lower().replace(' ', '-')}-documents.zip",
                    mime="application/zip",
                    key="export",
                    type="primary",
                    on_click="ignore",
                )

    if docs:
        render_template("generated_documents/doc_panel.html", **_panel_context(active, docs))
    elif not project_id:
        st.html('<div class="empty-state">No project selected. Set up a project and click '
                '<strong>Generate sprints</strong> to see its documents here.</div>')
