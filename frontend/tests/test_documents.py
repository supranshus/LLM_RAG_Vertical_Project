import io
import json
import zipfile

from components.documents import export_zip, initials, sprint_dates, total_weeks, word_count_label
from config.settings import get_settings

DOCS = json.loads((get_settings().mock_data_dir / "generated_documents.json").read_text())


def test_formatting_matches_design():
    assert initials("Ananya Rao") == "AR"
    assert sprint_dates(DOCS["sprints"][0]) == "Mon, Sep 14 – Fri, Sep 25, 2026"
    assert total_weeks(DOCS["sprints"]) == 6
    assert word_count_label(DOCS["problem_statement"]) == "~210 words"


def test_word_count_falls_back_to_content():
    doc = {"sections": [{"heading": "One two", "blocks": [{"type": "paragraph", "text": "a " * 48}]}]}
    assert word_count_label(doc) == "~50 words"


def test_export_zip_contains_all_documents():
    with zipfile.ZipFile(io.BytesIO(export_zip(DOCS))) as zf:
        assert sorted(zf.namelist()) == sorted([
            "problem-statement.md", "project-description.md", "sprint-plan.md",
            "task-breakdown.md", "test-cases.md",
        ])
        assert "TC-06" in zf.read("test-cases.md").decode()
