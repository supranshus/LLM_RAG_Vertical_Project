from app.db.base import make_engine


def test_make_engine_creates_sqlite_parent_dir(tmp_path):
    eng = make_engine(f"sqlite:///{(tmp_path / 'a' / 'b' / 'app.db').as_posix()}")
    with eng.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert (tmp_path / "a" / "b").is_dir()
