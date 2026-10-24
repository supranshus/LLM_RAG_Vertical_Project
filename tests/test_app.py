from streamlit.testing.v1 import AppTest
from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec
from streamlit.proto.Common_pb2 import FileURLs

import streamlit as st
import pytest

from components import html
from services import DataProviderError, projects

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


@pytest.mark.parametrize("filename, content, message", [
    ("requirements.exe", b"invalid", "Invalid file type"),
    ("requirements.pdf", b"", "empty"),
    ("requirements.pdf", b"invalid", "valid PDF"),
    ("requirements.docx", b"invalid", "valid DOCX"),
    ("requirements.txt", b"\xff", "UTF-8"),
    ("requirements.txt", b"a" * (50 * 1024 * 1024 + 1), "50 MB"),
], ids=["unsupported-type", "empty", "invalid-pdf", "invalid-docx", "invalid-text", "oversized"])
def test_brd_validation_is_inline_and_clears_on_replacement_or_removal(
    monkeypatch, filename, content, message
):
    original_uploader = st.file_uploader
    upload = UploadedFile(
        UploadedFileRec("invalid", filename, "application/octet-stream", content),
        FileURLs(),
    )
    invalid_upload = upload

    def uploader(label, **kwargs):
        if kwargs.get("key") == "cp_brd":
            st.session_state["cp_brd"] = upload
            return upload
        return original_uploader(label, **kwargs)

    monkeypatch.setattr(st, "file_uploader", uploader)
    at = AppTest.from_file(APP).run(timeout=30)
    assert not at.exception
    container = next(block for block in at.get("flex_container") if block.key == "brd_upload")
    assert message in container.error[0].value
    assert at.button(key="save_draft").disabled
    assert at.button(key="generate").disabled
    assert at.session_state["cp_project_id"] is None

    upload = None
    at.run(timeout=30)
    assert not at.exception
    assert not at.error
    assert not at.button(key="save_draft").disabled
    assert not at.button(key="generate").disabled

    upload = invalid_upload
    at.run(timeout=30)
    assert message in at.error[0].value
    assert at.button(key="save_draft").disabled
    assert at.button(key="generate").disabled

    upload = UploadedFile(
        UploadedFileRec("valid", "requirements.txt", "text/plain", b"Project requirements"),
        FileURLs(),
    )
    at.run(timeout=30)
    assert not at.exception
    assert not at.error
    assert not at.button(key="save_draft").disabled
    assert not at.button(key="generate").disabled
    at.text_input(key="cp_name").set_value("Validated project")
    at.button(key="save_draft").click().run(timeout=30)
    assert not at.exception
    assert at.session_state["cp_project_id"] is not None

    upload = None
    at.run(timeout=30)
    assert not at.exception
    assert not at.error
    assert not at.button(key="save_draft").disabled
    assert not at.button(key="generate").disabled


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


def test_generate_stays_on_generation_screen():
    at = AppTest.from_file(APP).run(timeout=30)
    at.text_input(key="cp_name").set_value("Warehouse hub")
    at.button(key="generate").click().run(timeout=30)
    assert not at.exception
    assert "Generating your sprint plan" in _texts(at)
    assert "problem-statement.md" not in _texts(at)
    assert at.session_state["cp_project_id"] is not None
    at.run(timeout=30)
    assert not at.exception
    assert "Generating your sprint plan" in _texts(at)
    assert "problem-statement.md" not in _texts(at)


def test_generation_screen_renders_before_saving_and_generating(monkeypatch):
    original_render = html.render_string
    original_create = projects.create_project
    original_generate = projects.generate_documents
    screens = []

    def render(template, **context):
        result = original_render(template, **context)
        if template == "create_project/generation.html":
            screens.append((context, result))
        return result

    def create(payload, brd=None):
        assert screens[-1][0] == {"generating": False, "has_brd": False}
        assert "Saving your project details" in screens[-1][1]
        return original_create(payload, brd)

    def generate(project_id):
        assert screens[-1][0] == {"generating": True, "has_brd": False}
        assert "No BRD attached" in screens[-1][1]
        assert "Creating tasks and subtasks" in screens[-1][1]
        assert "Allocating work to sprints" in screens[-1][1]
        assert "Preparing your documents" in screens[-1][1]
        return original_generate(project_id)

    monkeypatch.setattr(html, "render_string", render)
    monkeypatch.setattr(projects, "create_project", create)
    monkeypatch.setattr(projects, "generate_documents", generate)
    at = AppTest.from_file(APP).run(timeout=30)
    at.text_input(key="cp_name").set_value("Generation screen")
    at.button(key="generate").click().run(timeout=30)
    assert not at.exception
    assert len(screens) == 2
    assert "problem-statement.md" not in _texts(at)
    assert '<section class="generation-screen"' in _texts(at)
    at.run(timeout=30)
    assert not at.exception
    assert len(screens) == 3
    assert '<section class="generation-screen"' in _texts(at)


@pytest.mark.parametrize("failed_action", ["create_project", "generate_documents"])
def test_generation_failure_restores_form_and_allows_retry(monkeypatch, failed_action):
    original_action = getattr(projects, failed_action)

    def fail(*args, **kwargs):
        raise DataProviderError("Service unavailable")

    monkeypatch.setattr(projects, failed_action, fail)
    at = AppTest.from_file(APP).run(timeout=30)
    at.text_input(key="cp_name").set_value("Retry project")
    at.button(key="generate").click().run(timeout=30)
    assert not at.exception
    assert at.error[0].value == "Could not generate the sprint plan: Service unavailable"
    assert '<section class="generation-screen"' not in _texts(at)
    assert at.text_input(key="cp_name").value == "Retry project"
    assert not at.button(key="generate").disabled

    monkeypatch.setattr(projects, failed_action, original_action)
    at.button(key="generate").click().run(timeout=30)
    assert not at.exception
    assert "Generating your sprint plan" in _texts(at)
    assert "problem-statement.md" not in _texts(at)


def test_generation_template_with_brd():
    screen = html.render_string("create_project/generation.html", generating=True, has_brd=True)
    assert "BRD ready for analysis" in screen
    assert "No BRD attached" not in screen
    assert screen.count('generation-step complete') == 2
    assert screen.count('generation-step active') == 1
    assert "aria-busy=\"true\"" in screen


def test_documents_page_switches_tabs():
    at = AppTest.from_file(APP).run(timeout=30)
    at.switch_page("views/generated_documents.py").run(timeout=30)
    assert "Fleet monitoring portal" in _texts(at)
    at.button(key="doc_tests").click().run(timeout=30)
    assert "test-cases.md" in _texts(at) and "TC-01" in _texts(at)
