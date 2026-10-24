"""The workspace pages: dashboard, board, my tasks, assistant and notifications."""
from streamlit.testing.v1 import AppTest

import pytest

from components import assistant as brain
from components import metrics
from services import workspace

APP = "../app.py"
PAGES = ["views/projects.py", "views/dashboard.py", "views/sprint_board.py",
         "views/my_tasks.py", "views/assistant.py", "views/notifications.py"]
FLEET = "prj-fleet"


def _texts(at):
    return " ".join(h.body for h in at.get("html"))


def _open(page, timeout=30):
    at = AppTest.from_file(APP).run(timeout=timeout)
    return at.switch_page(page).run(timeout=timeout)


# ---- pages render -----------------------------------------------------------

@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_with_the_shell(page):
    at = _open(page)
    assert not at.exception
    body = _texts(at)
    assert "Project Management System" in body          # the rail
    assert at.selectbox(key="app_project_pick").value == FLEET
    assert at.selectbox(key="app_user_pick").value == "usr-sana"
    assert at.button(key="nav_dashboard")                # navigation is present


def test_projects_page_lists_every_visible_project():
    at = _open("views/projects.py")
    body = _texts(at)
    for name in ("Fleet monitoring portal", "Warehouse inventory app", "Billing API v2"):
        assert name in body
    assert at.button(key="open_proj_prj-warehouse")


def test_opening_a_project_switches_the_current_project():
    at = _open("views/projects.py")
    at.button(key="open_proj_prj-warehouse").click().run(timeout=30)
    assert not at.exception
    assert at.session_state["app_project_id"] == "prj-warehouse"


def test_dashboard_reports_the_computed_figures():
    at = _open("views/dashboard.py")
    body = _texts(at)
    tasks = workspace.list_tasks(FLEET)
    assert f"{metrics.percent_complete(tasks)}%" in body
    assert "Sprint progress" in body and "Needs attention" in body
    assert "Driver scorecards" in body   # the name is HTML-escaped in the markup


def test_board_groups_tasks_by_status():
    at = _open("views/sprint_board.py")
    body = _texts(at)
    assert "In review" in body and "Blocked" in body
    # The board opens on the sprint in flight.
    assert at.selectbox(key="board_sprint").value == "spr-f3"


def test_board_filters_by_assignee():
    at = _open("views/sprint_board.py")
    at.selectbox(key="board_assignee").set_value("usr-ananya").run(timeout=30)
    assert not at.exception
    body = _texts(at)
    assert "Scorecard dashboard UI" in body
    assert "Trip data gaps on provider timeout" not in body


def test_my_tasks_follows_the_viewing_as_switcher():
    at = _open("views/my_tasks.py")
    at.selectbox(key="app_user_pick").set_value("usr-karan").run(timeout=30)
    assert not at.exception
    body = _texts(at)
    assert "End-to-end scorecard QA" in body
    assert "Scorecard dashboard UI" not in body


def test_posting_an_update_moves_the_task_and_records_a_note():
    at = _open("views/my_tasks.py")
    at.selectbox(key="app_user_pick").set_value("usr-arjun").run(timeout=30)
    at.selectbox(key="mine_task").set_value("tsk-017").run(timeout=30)
    at.text_area(key="mine_note").set_value("Started the keyboard pass.").run(timeout=30)
    at.selectbox(key="mine_status").set_value("in_progress").run(timeout=30)
    at.button(key="mine_post").click().run(timeout=30)
    assert not at.exception
    assert workspace.get_task("tsk-017")["status"] == "in_progress"
    notes = workspace.list_task_updates(task_id="tsk-017")
    assert any(n["note"] == "Started the keyboard pass." for n in notes)


def test_notifications_can_be_acknowledged():
    at = _open("views/notifications.py")
    assert "is behind schedule" in _texts(at)
    at.button(key="ack_ntf-002").click().run(timeout=30)
    assert not at.exception
    assert "Acknowledged" in _texts(at)


def test_notifications_hide_closed_alerts_by_default():
    at = _open("views/notifications.py")
    assert "Warehouse sprint 2 ends today" not in _texts(at)   # dismissed
    at.toggle(key="ntf_show_closed").set_value(True).run(timeout=30)
    assert "Warehouse sprint 2 ends today" in _texts(at)


# ---- assistant --------------------------------------------------------------

@pytest.mark.parametrize("message, intent", [
    ("what is blocked right now?", brain.STATUS_QUERY),
    ("How is the project doing?", brain.STATUS_QUERY),
    ("anything overdue", brain.STATUS_QUERY),
    ("finished the scorecard dashboard and opened it for review", brain.TASK_UPDATE),
    ("blocked on staging data for the scorecard QA", brain.TASK_UPDATE),
    ("hello there", brain.UNKNOWN),
])
def test_intent_classification(message, intent):
    assert brain.classify(message) == intent


def test_status_answers_use_the_computed_numbers():
    project = next(p for p in workspace.list_projects() if p["id"] == FLEET)
    tasks = workspace.list_tasks(FLEET)
    answer = brain.answer_status("how is the project doing?", project, tasks,
                                 workspace.list_sprints(FLEET))
    assert f"{metrics.percent_complete(tasks)}% complete" in answer
    blocked = brain.answer_status("what is blocked?", project, tasks, [])
    for task in metrics.blocked_tasks(tasks):
        assert task["title"] in blocked


def test_assistant_answers_a_status_question_in_the_page():
    at = _open("views/assistant.py")
    at.button(key="suggest_1").click().run(timeout=30)     # "What is blocked right now?"
    assert not at.exception
    body = _texts(at)
    assert "Status question" in body
    assert "End-to-end scorecard QA" in body


def test_assistant_records_an_update_from_chat():
    at = _open("views/assistant.py")
    at.selectbox(key="app_user_pick").set_value("usr-vikram").run(timeout=30)
    at.text_area(key="chat_input").set_value(
        "finished fix scorecard export to CSV, logged 3h").run(timeout=30)
    at.button(key="chat_send").click().run(timeout=30)
    assert not at.exception
    assert "Task update" in _texts(at)
    task = next(t for t in workspace.list_tasks(FLEET)
                if t["title"] == "Fix scorecard export to CSV")
    assert task["status"] == "done"
    assert any(u["source"] == "chat" for u in workspace.list_task_updates(task_id=task["id"]))


def test_assistant_asks_again_when_the_intent_is_unclear():
    at = _open("views/assistant.py")
    at.text_area(key="chat_input").set_value("hmm").run(timeout=30)
    at.button(key="chat_send").click().run(timeout=30)
    assert not at.exception
    assert "could not tell" in _texts(at)


# ---- role-based visibility (FR-011) -----------------------------------------

def test_a_member_only_sees_their_own_projects():
    # The mock store is shared across the session, so other tests may have
    # created projects. Check the seeded ones rather than an exact count.
    everything = {p["id"] for p in workspace.visible_projects("usr-sana", "pm")}
    assert {"prj-fleet", "prj-warehouse", "prj-billing", "prj-support"} <= everything
    meera = workspace.visible_projects("usr-meera", "member")
    assert [p["id"] for p in meera] == [FLEET]


def test_role_switch_narrows_the_project_picker():
    at = _open("views/projects.py")
    at.selectbox(key="app_user_pick").set_value("usr-meera").run(timeout=30)
    assert not at.exception
    assert at.selectbox(key="app_project_pick").options == ["Fleet monitoring portal"]
    assert "Warehouse inventory app" not in _texts(at)


# ---- text rendering ---------------------------------------------------------

def test_rich_escapes_before_adding_bold():
    from components.html import rich
    assert str(rich("**Done** now")) == "<strong>Done</strong> now"
    # Anything in the text itself is escaped, so it can never become markup.
    assert "<script>" not in str(rich("<script>alert(1)</script>"))
    assert str(rich("a < b")) == "a &lt; b"


def test_text_blocks_groups_bullets():
    from components.html import text_blocks
    blocks = text_blocks("Intro line\n\n- one\n- two\nClosing line")
    assert [b["type"] for b in blocks] == ["paragraph", "list", "paragraph"]
    assert blocks[1]["items"] == ["one", "two"]


def test_injected_css_cannot_break_out_of_the_style_tag():
    # A literal "<" anywhere in a stylesheet makes the sanitiser drop all of it,
    # which silently unstyles every page.
    import pathlib
    for path in pathlib.Path("assets/css").glob("*.css"):
        assert "<" not in path.read_text(encoding="utf-8"), f"{path.name} contains '<'"
