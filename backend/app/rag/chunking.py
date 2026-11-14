from collections.abc import Sequence
from dataclasses import dataclass

from app.rag.parsing import ParsedPage


@dataclass(frozen=True)
class Chunk:
    text: str
    page: int | None
    index: int  # position in the whole document, from 0


def chunk_pages(pages: Sequence[ParsedPage], size: int, overlap: int) -> list[Chunk]:
    """Split each page into fixed-size character windows that overlap by `overlap`.

    Windows never span two pages, so every chunk keeps an accurate page number.
    """
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("chunk size must be positive and overlap must be in [0, size)")

    step = size - overlap
    chunks: list[Chunk] = []
    for page in pages:
        text = page.text
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            window = text[start:end].strip()
            if window:
                chunks.append(Chunk(window, page.page, len(chunks)))
            if end == len(text):
                break
            start += step
    return chunks
