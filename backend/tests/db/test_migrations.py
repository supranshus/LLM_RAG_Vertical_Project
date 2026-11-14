from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

import app.db.models  # noqa: F401  (registers models on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base, make_engine

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_alembic_upgrade_head_matches_models(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    try:
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()

    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "conversations", "messages", "documents"} <= tables
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    engine.dispose()
