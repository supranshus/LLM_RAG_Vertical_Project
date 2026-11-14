import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


@dataclass(frozen=True)
class ParsedPage:
    page: int | None  # 1-based page number; None for formats without pages
    text: str


class DocumentParseError(Exception):
    pass


def parse_document(path: Path, extension: str) -> list[ParsedPage]:
    """Extract text from a file. Pages with no text are left out."""
    extension = extension.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError("Could not read this file")
    try:
        if extension == ".pdf":
            pages = _parse_pdf(path)
        elif extension == ".docx":
            pages = _parse_docx(path)
        else:
            pages = [ParsedPage(None, path.read_bytes().decode("utf-8-sig", errors="replace"))]
    except Exception as exc:
        logger.warning("Could not parse %s file: %s", extension, type(exc).__name__)
        raise DocumentParseError("Could not read this file") from exc
    return [page for page in pages if page.text.strip()]


def _parse_pdf(path: Path) -> list[ParsedPage]:
    from pypdf import PdfReader

    reader = PdfReader(path, strict=False)
    return [
        ParsedPage(number, page.extract_text() or "")
        for number, page in enumerate(reader.pages, start=1)
    ]


def _parse_docx(path: Path) -> list[ParsedPage]:
    import docx

    document = docx.Document(str(path))
    return [ParsedPage(None, "\n".join(p.text for p in document.paragraphs))]
