import pytest

from app.rag.chunking import Chunk, chunk_pages
from app.rag.parsing import ParsedPage


def test_chunk_windows_and_overlap():
    text = "".join(chr(97 + i % 26) for i in range(2500))
    chunks = chunk_pages([ParsedPage(1, text)], size=1000, overlap=150)
    assert [len(c.text) for c in chunks] == [1000, 1000, 800]
    assert chunks[0].text[-150:] == chunks[1].text[:150]
    assert [c.index for c in chunks] == [0, 1, 2]
    assert all(c.page == 1 for c in chunks)


def test_short_page_is_one_chunk():
    assert chunk_pages([ParsedPage(None, "  hello  ")], size=1000, overlap=150) == [
        Chunk("hello", None, 0)
    ]


def test_chunks_never_cross_pages():
    chunks = chunk_pages([ParsedPage(1, "first"), ParsedPage(2, "second")], 1000, 150)
    assert [(c.text, c.page, c.index) for c in chunks] == [("first", 1, 0), ("second", 2, 1)]


def test_exact_size_text_is_one_chunk():
    chunks = chunk_pages([ParsedPage(1, "x" * 1000)], size=1000, overlap=150)
    assert len(chunks) == 1


def test_whitespace_windows_skipped():
    text = "a" * 10 + " " * 30
    chunks = chunk_pages([ParsedPage(1, text)], size=10, overlap=0)
    assert [c.text for c in chunks] == ["a" * 10]


@pytest.mark.parametrize(("size", "overlap"), [(1000, 1000), (1000, -1), (0, 0)])
def test_invalid_overlap_raises(size, overlap):
    with pytest.raises(ValueError):
        chunk_pages([ParsedPage(1, "text")], size=size, overlap=overlap)
