import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        os.makedirs(s.data_dir, exist_ok=True)
        _engine = create_engine(s.db_url, connect_args={"check_same_thread": False})

        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


@contextmanager
def get_connection() -> Generator:
    """Read-only connection (autobegin, no explicit commit)."""
    with get_engine().connect() as conn:
        yield conn


@contextmanager
def get_transaction() -> Generator:
    """Write connection — auto-commits on success, rolls back on exception."""
    with get_engine().begin() as conn:
        yield conn


def run_migrations() -> None:
    """Apply Alembic migrations at startup."""
    from alembic import command
    from alembic.config import Config

    settings = get_settings()
    os.makedirs(settings.data_dir, exist_ok=True)
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.db_url)
    command.upgrade(alembic_cfg, "head")
