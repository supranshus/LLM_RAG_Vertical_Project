from streamlit.testing.v1 import AppTest

APP = "../app.py"


def _texts(at):
    return " ".join(h.body for h in at.get("html"))


def test_create_project_renders():
    at = AppTest.from_file(APP).run(timeout=30)
    assert not at.exception
    assert "Set up a new project" in _texts(at)
    assert at.text_input(key="cp_name").placeholder == "Fleet monitoring portal"
    assert at.selectbox(key="cp_employee_selection").options


def test_add_employee_to_team_once():
    at = AppTest.from_file(APP).run(timeout=30)
    employee_label = at.selectbox(key="cp_employee_selection").options[0]
    at.selectbox(key="cp_employee_selection").set_value(employee_label).run(timeout=30)
    at.button(key="add_member").click().run(timeout=30)

    assert not at.exception
    assert at.session_state["cp_team_employee_ids"] == ["emp-001"]
    assert employee_label not in at.selectbox(key="cp_employee_selection").options


def test_generate_requires_name():
    at = AppTest.from_file(APP).run(timeout=30)
    at.button(key="generate").click().run(timeout=30)
    assert at.error[0].value == "Project name is required."


def test_imported_employee_survives_reruns_and_can_be_added():
    at = AppTest.from_file(APP).run(timeout=30)
    at.session_state["cp_imported_employees"] = {
        "excel-123": {"id": "excel-123", "name": "Alex Rivera", "role": "QA",
                      "experience_years": 3, "skills": ["Testing"]},
    }
    at.run(timeout=30)
    assert "Alex Rivera · QA" in at.selectbox(key="cp_employee_selection").options
    at.selectbox(key="cp_employee_selection").set_value("Alex Rivera · QA").run(timeout=30)
    at.button(key="add_member").click().run(timeout=30)
    assert not at.exception
    assert at.session_state["cp_team_employee_ids"] == ["excel-123"]
    assert at.session_state["cp_employee_directory"]["excel-123"]["skills"] == ["Testing"]


def test_generate_opens_documents():
    at = AppTest.from_file(APP).run(timeout=30)
    at.text_input(key="cp_name").set_value("Warehouse hub")
    at.button(key="generate").click().run(timeout=30)
    assert not at.exception
    assert "Warehouse hub" in _texts(at)
    assert "problem-statement.md" in _texts(at)


def test_documents_page_switches_tabs():
    at = AppTest.from_file(APP).run(timeout=30)
    at.switch_page("views/generated_documents.py").run(timeout=30)
    assert "Fleet monitoring portal" in _texts(at)
    at.button(key="doc_tests").click().run(timeout=30)
    assert "test-cases.md" in _texts(at) and "TC-01" in _texts(at)
