"""The app shell shared by the workspace pages.

Every workspace page starts with ``render_shell(...)``: it draws the dark rail
(brand, navigation, project picker, role switcher, signed-in user) and hands
back the current user, role and project plus the main column to fill.

The signed-in user is a session value rather than real authentication, which is
out of scope for this phase. Switching it is how the role-based views are
demonstrated (FR-011).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from components.html import render_template
from components.ui import icon_rule, inject_css, load_css
from services import DataProviderError, workspace

# page key -> (label, icon, script path). The order is the order in the rail.
NAV = {
    "projects": ("Projects", "layers", "views/projects.py"),
    "dashboard": ("Dashboard", "gauge", "views/dashboard.py"),
    "board": ("Sprint board", "board", "views/sprint_board.py"),
    "my_tasks": ("My tasks", "tasks", "views/my_tasks.py"),
    "assistant": ("Assistant", "chat", "views/assistant.py"),
    "notifications": ("Notifications", "bell", "views/notifications.py"),
    "documents": ("Documents", "file-text", "views/generated_documents.py"),
}
CREATE_PROJECT_PAGE = "views/create_project.py"
DEFAULT_USER = "usr-sana"  # the project manager: the role with the widest useful view


@dataclass
class Shell:
    """What a page needs after the rail is drawn."""
    user: dict[str, Any]
    role: str
    project: dict[str, Any] | None
    projects: list[dict[str, Any]]
    main: Any

    @property
    def user_id(self) -> str:
        return self.user["id"]

    @property
    def project_id(self) -> str | None:
        return self.project["id"] if self.project else None


# ---- state ------------------------------------------------------------------

def _go(page_key: str) -> None:
    st.session_state["app_nav_target"] = NAV[page_key][2]


def _pick_user() -> None:
    st.session_state["app_user_id"] = st.session_state.get("app_user_pick") or DEFAULT_USER


def _pick_project() -> None:
    st.session_state["app_project_id"] = st.session_state.get("app_project_pick")


def current_user() -> dict[str, Any]:
    """The signed-in person, falling back to the default if the id is unknown."""
    users = workspace.list_users()
    by_id = {u["id"]: u for u in users}
    user_id = st.session_state.get("app_user_id", DEFAULT_USER)
    return by_id.get(user_id) or by_id.get(DEFAULT_USER) or (users[0] if users else
                                                             {"id": "", "name": "Unknown",
                                                              "role": "member"})


def select_project(project_id: str) -> None:
    """Make a project current, from anywhere (e.g. a row on the Projects page)."""
    st.session_state["app_project_id"] = project_id
    st.session_state["app_project_pick"] = project_id


# ---- rail -------------------------------------------------------------------

def _nav_css(active: str, alert_count: int) -> str:
    rules = [
        icon_rule(f".st-key-nav_{key} .stButton button", meta[1], size=17,
                  color="rgba(255,255,255,0.4)")
        for key, meta in NAV.items()
    ]
    rules.append(icon_rule(".st-key-nav_new .stButton button", "plus", size=16, stroke_width=2,
                           color="var(--route)"))
    if active in NAV:
        rules += [
            f".stApp .st-key-nav_{active} .stButton button,"
            f" .stApp .st-key-nav_{active} .stButton button:hover,"
            f" .stApp .st-key-nav_{active} .stButton button:focus:not(:active)"
            " { background: rgba(51,210,160,0.14); color: #fff; font-weight: 500; }",
            f".stApp .st-key-nav_{active} .stButton button::before"
            " { background-color: var(--route); }",
        ]
    if alert_count:
        rules.append(
            '.st-key-nav_notifications .stButton button::after'
            f' {{ content: "{alert_count}"; margin-left: auto; font-family: var(--font-mono);'
            ' font-size: 11px; line-height: 1; padding: 3px 7px; border-radius: 999px;'
            ' background: var(--route); color: #0E2B24; font-weight: 600; }'
        )
    return "\n".join(rules)


def _render_rail(active: str, user: dict[str, Any], projects: list[dict[str, Any]],
                 project: dict[str, Any] | None, alert_count: int) -> None:
    render_template(
        "shell/brand.html",
        title="Project Management System",
        subtitle=project["name"] if project else "No project selected",
    )
    if projects:
        st.selectbox(
            "Project", [p["id"] for p in projects],
            format_func=lambda pid: next(p["name"] for p in projects if p["id"] == pid),
            key="app_project_pick", on_change=_pick_project, label_visibility="collapsed",
        )
    for key, (label, *_rest) in NAV.items():
        st.button(label, key=f"nav_{key}", width="stretch", on_click=_go, args=(key,))
    st.html('<div class="rail-divider"></div>')
    st.button("New project", key="nav_new", width="stretch",
              on_click=lambda: st.session_state.update(app_nav_target=CREATE_PROJECT_PAGE))
    render_template("shell/user_chip.html", user=user,
                    role_label=workspace.ROLE_LABELS.get(user.get("role", ""), "Team member"))
    st.selectbox(
        "Viewing as", [u["id"] for u in workspace.list_users()],
        format_func=lambda uid: next(
            f"{u['name']} · {workspace.ROLE_LABELS.get(u['role'], u['role'])}"
            for u in workspace.list_users() if u["id"] == uid),
        key="app_user_pick", on_change=_pick_user,
    )


# ---- entry point ------------------------------------------------------------

def render_shell(active: str, *, page_css: str | None = None, wide: bool = False) -> Shell:
    """Draw the rail and return the page context plus the main column."""
    # A nav click is handled on the next run, so the rail finishes drawing first.
    target = st.session_state.pop("app_nav_target", None)

    load_css("theme.css", "shell.css", *( [page_css] if page_css else [] ))

    user = current_user()
    st.session_state.setdefault("app_user_pick", user["id"])
    role = user.get("role", "member")

    try:
        projects = workspace.visible_projects(user["id"], role)
        alert_count = workspace.unread_count(user["id"])
        load_error = None
    except DataProviderError as exc:
        projects, alert_count, load_error = [], 0, str(exc)

    project_id = st.session_state.get("app_project_id")
    if not any(p["id"] == project_id for p in projects):
        project_id = projects[0]["id"] if projects else None
        st.session_state["app_project_id"] = project_id
    st.session_state["app_project_pick"] = project_id
    project = next((p for p in projects if p["id"] == project_id), None)

    inject_css(_nav_css(active, alert_count))

    with st.container(key="layout"):
        rail_col, main_col = st.columns([250, 700])
    with rail_col, st.container(key="rail"):
        _render_rail(active, user, projects, project, alert_count)

    if wide:
        inject_css(".st-key-layout > [data-testid='stLayoutWrapper'] >"
                   " [data-testid='stHorizontalBlock'] > [data-testid='stColumn']:last-child"
                   " { max-width: 790px; }")

    if target:
        st.switch_page(target)

    with main_col:
        main = st.container(key="main")
    if load_error:
        with main:
            st.error(f"Could not load the workspace: {load_error}")
    return Shell(user=user, role=role, project=project, projects=projects, main=main)


def page_header(title: str, subtitle: str = "", *, status: str = "", status_tone: str = "",
                chips: list[str] | None = None) -> None:
    """The title block every workspace page opens with.

    ``status_tone`` is "", "is-warn" or "is-late" and colours the status dot.
    """
    render_template("shell/page_header.html", title=title, subtitle=subtitle,
                    status=status, status_tone=status_tone, chips=chips or [])


def empty_state(message: str) -> None:
    st.html(f'<div class="empty-state">{message}</div>')
