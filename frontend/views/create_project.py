"""Create project — port of create-project.html."""
from __future__ import annotations

import json
import hashlib
from datetime import date
from typing import Any

import streamlit as st

from components.employees import import_employees
from components.html import render_string, render_template
from components.ui import icon_rule, inject_css, load_css
from components.uploads import BRD_UPLOAD_HINT, validate_brd
from services import DataProviderError
from services import projects

GENERATED_DOCS_PAGE = "views/generated_documents.py"

STEPS = [
    {"id": "details", "num": "01", "label": "Project details"},
    {"id": "deliverables", "num": "02", "label": "Deliverables"},
    {"id": "team", "num": "03", "label": "Team"},
    # {"id": "sprints", "num": "04", "label": "Sprint settings"},
]
PROJECT_TYPES = ["Web app", "Mobile app", "API / backend", "Internal tool"]
STATUSES = ["Draft", "Active", "On hold"]
SPRINT_LENGTHS = {"1 week": 1, "2 weeks": 2, "3 weeks": 3}


# ---- state ------------------------------------------------------------------

def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("cp_mode", "new")
    ss.setdefault("cp_team_employee_ids", [])
    ss.setdefault("cp_employee_selection", None)
    ss.setdefault("cp_imported_employees", {})
    ss.setdefault("cp_employee_import_digest", None)
    ss.setdefault("cp_project_id", None)  # set once saved, so later saves update it
    ss.setdefault("cp_generation_preview", None)
    ##ss.setdefault("cp_sprint_length", "2 weeks")
    ss.setdefault("cp_working_days", 5)
    ss.setdefault("cp_hours_day", 6)
    # Empty by default. Set here rather than via value=None so widget state can be restored.
    ss.setdefault("cp_start_date", None)
    ss.setdefault("cp_end_date", None)
def _set_mode(mode: str) -> None:
    st.session_state.cp_mode = mode


def _add_member() -> None:
    ss = st.session_state
    employee_id = ss.get("cp_employee_selection")
    if employee_id in ss.cp_employee_directory and employee_id not in ss.cp_team_employee_ids:
        ss.cp_team_employee_ids.append(employee_id)
    ss.cp_employee_selection = None


def _remove_member(employee_id: str) -> None:
    st.session_state.cp_team_employee_ids.remove(employee_id)


# ---- payload ----------------------------------------------------------------

def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def build_payload() -> dict[str, Any]:
    """Form values -> request body for POST /projects."""
    ss = st.session_state
    existing = ss.cp_mode == "existing"
    team = []
    for employee_id in ss.cp_team_employee_ids:
        employee = ss.cp_employee_directory.get(employee_id)
        if not employee:
            continue
        name = str(employee.get("name") or "").strip()
        if not name:
            continue
        skills = employee.get("skills") or []
        if isinstance(skills, str):
            skills = skills.split(",")
        team.append({
            "name": name,
            "experience_years": employee.get("experience_years"),
            "role": employee.get("role"),
            "skills": [str(skill).strip() for skill in skills if str(skill).strip()],
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
        # "sprint_settings": {
        #     "length_weeks": SPRINT_LENGTHS[ss.cp_sprint_length],
        #     "working_days_per_week": ss.cp_working_days,
        #     "hours_per_day": ss.cp_hours_day,
        # },
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
try:
    employee_records = projects.list_employees()
    employee_load_error = None
except DataProviderError as exc:
    employee_records = []
    employee_load_error = str(exc)
employee_directory = {
    str(employee["id"]): employee
    for employee in employee_records
    if employee.get("id") is not None
}
employee_directory.update(st.session_state.cp_imported_employees)
st.session_state.cp_employee_directory = employee_directory
load_css("theme.css", "create_project.css", "generation.css")
generation_screen = st.empty()
if st.session_state.cp_generation_preview is not None:
    generation_screen.html(render_string(
        "create_project/generation.html", **st.session_state.cp_generation_preview,
    ))

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
    with st.container(key="rail"):
        render_template("create_project/rail.html", steps=STEPS)
    main_col = st.container()

with main_col, st.container(key="main"):
    content_scroll = st.container(key="content_scroll")
    action_footer = st.container(key="action_footer")

with content_scroll:
    # Header
    with st.container(key="page_head"):
        render_template(
            "create_project/page_head.html",
            title="Set up a new project",
            subtitle="These details feed the generator that plans your sprints, "
            "breaks down tasks, and drafts test cases.",
        )
        # with st.container(key="mode_toggle", horizontal=True, gap=None):
        #     st.button("New project", key="mode_new", on_click=_set_mode, args=("new",))
        #     st.button("Existing project", key="mode_existing", on_click=_set_mode, args=("existing",))

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
        with st.container(key="brd_upload"):
            brd_upload = st.file_uploader("BRD document", key="cp_brd", help=BRD_UPLOAD_HINT)
            brd_error = validate_brd(brd_upload.name, brd_upload.getvalue()) if brd_upload is not None else None
            if brd_error:
                st.error(brd_error)
            st.caption(BRD_UPLOAD_HINT)

    # 03 Team members
    with st.container(key="block_team"):
        with st.container(key="team_head", horizontal=True):
            st.html(render_string("create_project/block_head.html", id="team", num="03",
                                  title="Team members"))
        st.html('<p class="block-note">Who\'s building it, and what they bring.</p>')
        employee_excel = st.file_uploader("Import employees from Excel", type=["xlsx"],
                                          key="cp_employee_excel")
        inject_css(
            '.st-key-cp_employee_excel [data-testid="stFileUploaderDropzone"]::after { content: '
            + json.dumps(employee_excel.name if employee_excel else "Upload employee workbook").replace("<", "\\3C ")
            + "; }"
        )
        if employee_excel is None:
            st.session_state.cp_employee_import_digest = None
        else:
            content = employee_excel.getvalue()
            digest = hashlib.sha256(content).hexdigest()
            if digest != st.session_state.cp_employee_import_digest:
                try:
                    imported = import_employees(content)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.cp_imported_employees.update(imported)
                    employee_directory.update(imported)
                    st.session_state.cp_employee_directory = employee_directory
                    st.session_state.cp_employee_import_digest = digest
                    st.success(f"Imported {len(imported)} employees.")
        if employee_load_error:
            st.warning(f"Could not load employees: {employee_load_error}")
        elif not employee_directory:
            st.caption("No employees are available to add.")
        available_employee_ids = [
            employee_id for employee_id in employee_directory
            if employee_id not in st.session_state.cp_team_employee_ids
        ]
        with st.container(key="team_picker", horizontal=True):
            selected_employee_id = st.selectbox(
                "Available employees",
                available_employee_ids,
                format_func=lambda employee_id: (
                    f"{employee_directory[employee_id].get('name', 'Employee')} · "
                    f"{employee_directory[employee_id].get('role') or 'Role not set'}"
                ),
                key="cp_employee_selection",
                index=None,
                placeholder="Select an employee",
                disabled=not available_employee_ids,
            )
            st.button("Add member", key="add_member", on_click=_add_member,
                      disabled=selected_employee_id is None)
        with st.container(key="members"):
            if not st.session_state.cp_team_employee_ids:
                st.caption("No team members added yet.")
            for index, employee_id in enumerate(st.session_state.cp_team_employee_ids):
                employee = employee_directory.get(employee_id)
                if not employee:
                    continue
                with st.container(key=f"member_row_{index}"):
                    details, remove = st.columns([1, 0.12])
                    details.markdown(f"**{employee.get('name', 'Employee')}**")
                    skills = employee.get("skills") or []
                    if isinstance(skills, str):
                        skills = [skill.strip() for skill in skills.split(",") if skill.strip()]
                    summary = [employee.get("role") or "Role not set"]
                    if employee.get("experience_years") is not None:
                        summary.append(f"{employee['experience_years']} years")
                    if skills:
                        summary.append(", ".join(skills))
                    details.caption(" · ".join(summary))
                    remove.button("Remove member", key=f"member_remove_{index}",
                                  on_click=_remove_member, args=(employee_id,))

    # 04 Sprint settings
    # with st.container(key="block_sprints"):
    #     render_template("create_project/block_head.html", id="sprints", num="04",
    #                     title="Sprint settings", note="How work gets paced once a sprint starts.")
    #     c1, c2, c3 = st.columns(3)
    #     c1.selectbox("Sprint length", list(SPRINT_LENGTHS), key="cp_sprint_length")
    #     c2.number_input("Working days / week", key="cp_working_days", min_value=1, max_value=7, step=1)
    #     c3.number_input("Hours / day per person", key="cp_hours_day", min_value=1, max_value=12, step=1)

with action_footer:
    # Actions
    with st.container(key="actions", horizontal=True):
        save_clicked = st.button("Save as draft", key="save_draft", disabled=bool(brd_error))
        generate_clicked = st.button("Generate sprints", key="generate", type="primary",
                                     disabled=bool(brd_error))

        if save_clicked or generate_clicked:
            payload = build_payload()
            errors = validate(payload)
            if brd_error:
                errors.append(brd_error)
            if errors:
                st.error(" ".join(errors))
            else:
                try:
                    if save_clicked:
                        _save(payload)
                        st.toast("Draft saved")
                    else:
                        generation_screen.html(render_string(
                            "create_project/generation.html", generating=False, has_brd=brd_upload is not None,
                        ))
                        project_id = _save(payload)
                        generation_screen.html(render_string(
                            "create_project/generation.html", generating=True, has_brd=brd_upload is not None,
                        ))
                        projects.generate_documents(project_id)
                        st.session_state.cp_generation_preview = {
                            "generating": True, "has_brd": brd_upload is not None,
                        }
                        # Temporarily keep the generation screen instead of opening documents.
                        # generation_screen.empty()
                        # st.switch_page(GENERATED_DOCS_PAGE, query_params={"project_id": project_id})
                except DataProviderError as exc:
                    generation_screen.empty()
                    action = "save the project" if save_clicked else "generate the sprint plan"
                    st.error(f"Could not {action}: {exc}")

with st.container(key="scroll_spy"):
    st.iframe(render_string("create_project/scroll_spy.html"), height=1)
