"""Validation for BRD document uploads."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

BRD_MAX_BYTES = 50 * 1024 * 1024
BRD_UPLOAD_HINT = "PDF, DOCX, or TXT. Maximum file size: 50 MB."


def validate_brd(filename: str, content: bytes) -> str | None:
    """Return a user-facing error for an invalid BRD, otherwise None."""
    extension = Path(filename).suffix.lower()
    if extension not in {".pdf", ".docx", ".txt"}:
        return "Invalid file type. Upload a PDF, DOCX, or TXT document."
    if not content:
        return "The BRD document is empty. Upload a file with content."
    if len(content) > BRD_MAX_BYTES:
        return "The BRD document must be 50 MB or smaller."
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        return "The file is not a valid PDF document."
    if extension == ".docx":
        try:
            with ZipFile(BytesIO(content)) as document:
                if not {"[Content_Types].xml", "word/document.xml"}.issubset(document.namelist()):
                    return "The file is not a valid DOCX document."
        except BadZipFile:
            return "The file is not a valid DOCX document."
    if extension == ".txt":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return "The TXT document must contain UTF-8 text."
        if "\x00" in text:
            return "The TXT document must contain text, not binary data."
        if not text.strip():
            return "The BRD document is empty. Upload a file with content."
    return None
