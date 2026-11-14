from io import BytesIO
from zipfile import ZipFile

import pytest

from components.uploads import BRD_MAX_BYTES, validate_brd


def _docx():
    content = BytesIO()
    with ZipFile(content, "w") as document:
        document.writestr("[Content_Types].xml", "<Types/>")
        document.writestr("word/document.xml", "<document/>")
    return content.getvalue()


@pytest.mark.parametrize("filename, content", [
    ("requirements.PDF", b"%PDF-1.7\n"),
    ("requirements.docx", _docx()),
    ("requirements.txt", b"Project requirements"),
    ("requirements.TXT", "Requirements: \u00e9".encode("utf-8-sig")),
])
def test_valid_brd(filename, content):
    assert validate_brd(filename, content) is None


@pytest.mark.parametrize("filename, content, message", [
    ("malware.exe", b"binary", "Invalid file type"),
    ("requirements", b"text", "Invalid file type"),
    ("requirements.pdf.exe", b"%PDF-1.7", "Invalid file type"),
    ("requirements.pdf", b"", "empty"),
    ("requirements.docx", b"", "empty"),
    ("requirements.txt", b"", "empty"),
    ("requirements.txt", b" \n\t", "empty"),
    ("requirements.pdf", b"not a PDF", "valid PDF"),
    ("requirements.docx", b"not a DOCX", "valid DOCX"),
    ("requirements.docx", b"PK\x03\x04invalid", "valid DOCX"),
    ("requirements.txt", b"\xff\xfe", "UTF-8"),
    ("requirements.txt", b"text\x00binary", "binary data"),
])
def test_invalid_brd(filename, content, message):
    assert message in validate_brd(filename, content)


def test_docx_requires_word_document():
    content = BytesIO()
    with ZipFile(content, "w") as document:
        document.writestr("other.txt", "Not a Word document")
    assert "valid DOCX" in validate_brd("requirements.docx", content.getvalue())


def test_brd_size_boundary():
    content = b"a" * BRD_MAX_BYTES
    assert validate_brd("requirements.txt", content) is None
    assert "50 MB" in validate_brd("requirements.txt", content + b"a")
