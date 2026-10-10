"""Create project — port of create-project.html."""
from __future__ import annotations

import json
from datetime import date
from typing import Any

import streamlit as st

from components.html import render_string, render_template
from components.ui import icon_rule, inject_css, load_css
from services import DataProviderError
from services import projects

GENERATED_DOCS_PAGE = "views/generated_documents.py"

STEPS = [
    {"id": "details", "num": "01", "label": "Project details"},
    {"id": "deliverables", "num": "02", "label": "Deliverables"},
    {"id": "team", "num": "03", "label": "Team"},
    {"id": "sprints", "num": "04", "label": "Sprint settings"},
]
PROJECT_TYPES = ["Web app", "Mobile app", "API / backend", "Internal tool"]
STATUSES = ["Draft", "Active", "On hold"]
ROLES = ["Frontend dev", "Backend dev", "QA", "Designer", "PM"]
SPRINT_LENGTHS = {"1 week": 1, "2 weeks": 2, "3 weeks": 3}


# ---- state ------------------------------------------------------------------

def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("cp_mode", "new")
    ss.setdefault("cp_member_ids", [0])
    ss.setdefault("cp_next_member_id", 1)
    ss.setdefault("cp_project_id", None)  # set once saved, so later saves update it
    ss.setdefault("cp_sprint_length", "2 weeks")
    ss.setdefault("cp_working_days", 5)
    ss.setdefault("cp_hours_day", 6)
    # Empty by default. Set here rather than via value=None so widget state can be restored.
    ss.setdefault("cp_start_date", None)
    ss.setdefault("cp_end_date", None)
    for mid in ss.cp_member_ids:
        ss.setdefault(f"cp_m{mid}_exp", None)


def _set_mode(mode: str) -> None:
    st.session_state.cp_mode = mode


def _add_member() -> None:
    ss = st.session_state
    ss.cp_member_ids.append(ss.cp_next_member_id)
    ss[f"cp_m{ss.cp_next_member_id}_exp"] = None
    ss.cp_next_member_id += 1


def _remove_member(member_id: int) -> None:
    ids = st.session_state.cp_member_ids
    if len(ids) > 1:
        ids.remove(member_id)


# ---- payload ----------------------------------------------------------------

def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def build_payload() -> dict[str, Any]:
    """Form values -> request body for POST /projects."""
    ss = st.session_state
    existing = ss.cp_mode == "existing"
    team = []
    for mid in ss.cp_member_ids:
        name = (ss.get(f"cp_m{mid}_name") or "").strip()
        if not name:
            continue
        team.append({
            "name": name,
            "experience_years": ss.get(f"cp_m{mid}_exp"),
            "role": ss.get(f"cp_m{mid}_role"),
            "skills": [s.strip() for s in (ss.get(f"cp_m{mid}_skills") or "").split(",") if s.strip()],
        })
    return {
        "mode": ss.cp_mode,
        "name": (ss.get("cp_name") or "").strip(),
        "type": ss.get("cp_type"),
        "description": (ss.get("cp_description") or "").strip(),
        "existing_features": (ss.get("cp_existing_features") or "").strip() if existing else None,
        "start_date": _iso(ss.get("cp_start_date")),
        "end_date": _iso(ss.get("cp_end_date")),
        "status": ss.get("cp_status"),
        "deliverables": [l.strip() for l in (ss.get("cp_deliverables") or "").splitlines() if l.strip()],
        "team": team,
        "sprint_settings": {
            "length_weeks": SPRINT_LENGTHS[ss.cp_sprint_length],
            "working_days_per_week": ss.cp_working_days,
            "hours_per_day": ss.cp_hours_day,
        },
    }


def validate(payload: dict[str, Any]) -> list[str]:
    errors = []
    if not payload["name"]:
        errors.append("Project name is required.")
    if payload["start_date"] and payload["end_date"] and payload["end_date"] < payload["start_date"]:
        errors.append("Preferred end date must be after the start date.")
    return errors


def _save(payload: dict[str, Any]) -> str:
    """Create the project on first save, update it afterwards. Returns its id."""
    ss = st.session_state
    upload = ss.get("cp_brd")
    brd = (upload.name, upload.getvalue(), upload.type or "application/octet-stream") if upload else None
    if ss.cp_project_id:
        projects.update_project(ss.cp_project_id, payload, brd)
    else:
        ss.cp_project_id = projects.create_project(payload, brd)["id"]
    return ss.cp_project_id


# ---- page -------------------------------------------------------------------

_init_state()
load_css("theme.css", "create_project.css")

mode = st.session_state.cp_mode
upload = st.session_state.get("cp_brd")
inject_css(
    # Active mode-toggle button.
    f".stApp .st-key-mode_{mode} .stButton button, .stApp .st-key-mode_{mode} .stButton button:hover,"
    f" .stApp .st-key-mode_{mode} .stButton button:focus:not(:active)"
    " { background: var(--accent-soft); color: var(--accent-dark); }"
    # Icons drawn on native buttons / the upload zone.
    + icon_rule(".st-key-add_member button", "plus", size=15, stroke_width=2)
    + icon_rule('[class*="st-key-member_remove_"] button', "close", size=14, stroke_width=2)
    + icon_rule(".st-key-generate button", "pin-sm", size=16, color="var(--route)")
    + icon_rule('[data-testid="stFileUploaderDropzone"]', "upload", size=18, color="var(--text-muted)")
    + '[data-testid="stFileUploaderDropzone"]:hover::before { background-color: var(--accent); }'
    + '[data-testid="stFileUploaderDropzone"]::before { display: block; }'
    + '[data-testid="stFileUploaderDropzone"]::after { display: block; content: '
    # Escape "<" so a crafted filename can't close the <style> tag.
    + json.dumps(upload.name if upload else "Attach a file, or drop it here").replace("<", "\\3C ")
    + "; }"
)

with st.container(key="layout"):
    rail_col, main_col = st.columns([250, 700])

with rail_col, st.container(key="rail"):
    render_template("create_project/rail.html", steps=STEPS)

with main_col, st.container(key="main"):
    # Header
    with st.container(key="page_head"):
        render_template(
            "create_project/page_head.html",
            title="Set up a new project",
            subtitle="These details feed the generator that plans your sprints, "
            "breaks down tasks, and drafts test cases.",
        )
        with st.container(key="mode_toggle", horizontal=True, gap=None):
            st.button("New project", key="mode_new", on_click=_set_mode, args=("new",))
            st.button("Existing project", key="mode_existing", on_click=_set_mode, args=("existing",))

    # 01 Project details
    with st.container(key="block_details"):
        render_template("create_project/block_head.html", id="details", num="01",
                        title="Project details", note="The basics that anchor everything else.")
        c1, c2 = st.columns(2)
        c1.text_input("Project name", key="cp_name", placeholder="Fleet monitoring portal")
        c2.selectbox("Project type", PROJECT_TYPES, key="cp_type")
        st.text_area("Description", key="cp_description",
                     placeholder="Fleet tracking and monitoring portal for logistics teams")
        if mode == "existing":
            st.text_area("Existing features / modules", key="cp_existing_features",
                         placeholder="Vehicle tracking, driver management, alerts module")
        c1, c2, c3 = st.columns(3)
        c1.date_input("Start date", key="cp_start_date", format="MM/DD/YYYY")
        c2.date_input("Preferred end date", key="cp_end_date", format="MM/DD/YYYY")
        c3.selectbox("Status", STATUSES, key="cp_status")

    # 02 Deliverables
    with st.container(key="block_deliverables"):
        render_template("create_project/block_head.html", id="deliverables", num="02",
                        title="Deliverables", note="What you want to ship, in your own words.")
        st.text_area("Expected deliverables", key="cp_deliverables",
                     placeholder="Live vehicle map, geofence alerts, driver scorecards")
        st.html('<div class="field-hint">One per line — each becomes a candidate epic.</div>')
        st.file_uploader("BRD document", key="cp_brd")

    # 03 Team members
    with st.container(key="block_team"):
        with st.container(key="team_head", horizontal=True):
            st.html(render_string("create_project/block_head.html", id="team", num="03",
                                  title="Team members"))
            st.button("Add member", key="add_member", on_click=_add_member)
        st.html('<p class="block-note">Who\'s building it, and what they bring.</p>')
        with st.container(key="members"):
            for mid in st.session_state.cp_member_ids:
                with st.container(key=f"member_row_{mid}"):
                    name, exp, role, skills, remove = st.columns([1.3, 0.7, 1, 1.2, 0.34])
                    name.text_input("Name", key=f"cp_m{mid}_name", placeholder="Name",
                                    label_visibility="collapsed")
                    exp.number_input("Years of experience", key=f"cp_m{mid}_exp",
                                     min_value=0, step=1, placeholder="Yrs exp",
                                     label_visibility="collapsed")
                    role.selectbox("Role", ROLES, key=f"cp_m{mid}_role", label_visibility="collapsed")
                    skills.text_input("Skills", key=f"cp_m{mid}_skills",
                                      placeholder="Skills, comma separated",
                                      label_visibility="collapsed")
                    remove.button("Remove member", key=f"member_remove_{mid}",
                                  on_click=_remove_member, args=(mid,))

    # 04 Sprint settings
    with st.container(key="block_sprints"):
        render_template("create_project/block_head.html", id="sprints", num="04",
                        title="Sprint settings", note="How work gets paced once a sprint starts.")
        c1, c2, c3 = st.columns(3)
        c1.selectbox("Sprint length", list(SPRINT_LENGTHS), key="cp_sprint_length")
        c2.number_input("Working days / week", key="cp_working_days", min_value=1, max_value=7, step=1)
        c3.number_input("Hours / day per person", key="cp_hours_day", min_value=1, max_value=12, step=1)

    # Actions
    with st.container(key="actions", horizontal=True):
        save_clicked = st.button("Save as draft", key="save_draft")
        generate_clicked = st.button("Generate sprints", key="generate", type="primary")

        if save_clicked or generate_clicked:
            payload = build_payload()
            errors = validate(payload)
            if errors:
                st.error(" ".join(errors))
            else:
                try:
                    if save_clicked:
                        _save(payload)
                        st.toast("Draft saved")
                    else:
                        with st.spinner("Generating sprints, tasks and test cases..."):
                            project_id = _save(payload)
                            projects.generate_documents(project_id)
                        st.switch_page(GENERATED_DOCS_PAGE, query_params={"project_id": project_id})
                except DataProviderError as exc:
                    st.error(f"Could not save the project: {exc}")

with st.container(key="scroll_spy"):
    st.iframe(render_string("create_project/scroll_spy.html"), height=1)
