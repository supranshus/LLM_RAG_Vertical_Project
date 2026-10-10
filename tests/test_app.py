from streamlit.testing.v1 import AppTest

APP = "../app.py"


def _texts(at):
    return " ".join(h.body for h in at.get("html"))


def test_create_project_renders():
    at = AppTest.from_file(APP).run(timeout=30)
    assert not at.exception
    assert "Set up a new project" in _texts(at)
    assert at.text_input(key="cp_name").placeholder == "Fleet monitoring portal"


def test_generate_requires_name():
    at = AppTest.from_file(APP).run(timeout=30)
    at.button(key="generate").click().run(timeout=30)
    assert at.error[0].value == "Project name is required."


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
