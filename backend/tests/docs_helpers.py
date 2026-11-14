"""Builds small PDF and DOCX files in memory for document tests."""

import io

import docx
from reportlab.pdfgen import canvas


def make_pdf(pages: list[str]) -> bytes:
    """One PDF page per entry; an empty string makes a page with no text."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in pages:
        if text:
            pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
