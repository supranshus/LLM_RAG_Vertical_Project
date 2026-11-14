import pytest

from app.rag.parsing import SUPPORTED_EXTENSIONS, DocumentParseError, ParsedPage, parse_document
from tests.docs_helpers import make_docx, make_pdf


def _write(tmp_path, name, data: bytes):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_supported_extensions():
    assert {".pdf", ".docx", ".txt", ".md"} == SUPPORTED_EXTENSIONS


def test_pdf_pages_numbered(tmp_path):
    path = _write(tmp_path, "a.pdf", make_pdf(["alpha", "beta"]))
    assert [(p.page, p.text.strip()) for p in parse_document(path, ".pdf")] == [
        (1, "alpha"),
        (2, "beta"),
    ]


def test_pdf_blank_pages_dropped(tmp_path):
    path = _write(tmp_path, "a.pdf", make_pdf(["", "gamma"]))
    assert [(p.page, p.text.strip()) for p in parse_document(path, ".pdf")] == [(2, "gamma")]


def test_blank_pdf_returns_no_pages(tmp_path):
    path = _write(tmp_path, "blank.pdf", make_pdf([""]))
    assert parse_document(path, ".pdf") == []


def test_docx_paragraphs(tmp_path):
    path = _write(tmp_path, "a.docx", make_docx(["one", "two"]))
    assert parse_document(path, ".docx") == [ParsedPage(None, "one\ntwo")]


def test_txt_utf8_and_md(tmp_path):
    txt = _write(tmp_path, "a.txt", "नमस्ते world".encode())
    assert parse_document(txt, ".txt") == [ParsedPage(None, "नमस्ते world")]
    md = _write(tmp_path, "a.md", "﻿# Title\nbody".encode())
    assert parse_document(md, ".md") == [ParsedPage(None, "# Title\nbody")]


def test_whitespace_only_text_returns_no_pages(tmp_path):
    assert parse_document(_write(tmp_path, "a.txt", b"  \n\t "), ".txt") == []


def test_corrupt_pdf_raises(tmp_path):
    with pytest.raises(DocumentParseError, match="Could not read this file"):
        parse_document(_write(tmp_path, "bad.pdf", b"not a pdf at all"), ".pdf")


def test_corrupt_docx_raises(tmp_path):
    with pytest.raises(DocumentParseError):
        parse_document(_write(tmp_path, "bad.docx", b"nope"), ".docx")


def test_unsupported_extension_raises(tmp_path):
    with pytest.raises(DocumentParseError):
        parse_document(_write(tmp_path, "a.exe", b"MZ"), ".exe")
