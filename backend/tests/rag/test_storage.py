import pytest

from app.rag.storage import FileStorage


def test_storage_creates_root_and_round_trips(tmp_path):
    storage = FileStorage(str(tmp_path / "data" / "uploads"))
    name = storage.save(b"hi", ".txt")
    assert name.endswith(".txt") and len(name) == 32 + len(".txt")
    assert storage.path(name).read_bytes() == b"hi"
    assert storage.path(name).parent == tmp_path / "data" / "uploads"
    storage.delete(name)
    storage.delete(name)  # deleting a missing file is fine
    assert not storage.path(name).exists()


def test_storage_names_are_unique(tmp_path):
    storage = FileStorage(str(tmp_path))
    assert storage.save(b"a", ".txt") != storage.save(b"a", ".txt")


@pytest.mark.parametrize("bad", ["../x.txt", "..\\x.txt", "sub/x.txt", "", ".."])
def test_storage_rejects_path_names(tmp_path, bad):
    with pytest.raises(ValueError):
        FileStorage(str(tmp_path)).path(bad)
