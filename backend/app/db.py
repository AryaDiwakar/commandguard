"""SQLAlchemy engine/session setup. SQLite by default (prototype)."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def engine():
    global _engine
    if _engine is None:
        connect_args = {"check_same_thread": False} if settings.db_url.startswith("sqlite") else {}
        _engine = create_engine(settings.db_url, connect_args=connect_args)
    return _engine


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


def init_db() -> None:
    import app.models  # noqa: F401  (register tables)
    if settings.db_url.startswith("sqlite"):
        import os
        from pathlib import Path as _Path

        path = _Path(settings.db_url.removeprefix("sqlite:///"))
        if not path.is_dir() and path.parent != _Path("."):
            path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine())
    # The prototype has no migration dependency, so keep the small incident
    # schema additive when an existing local SQLite file predates a column.
    if settings.db_url.startswith("sqlite"):
        inspector = inspect(engine())
        if "incidents" in inspector.get_table_names():
            columns = {column["name"] for column in inspector.get_columns("incidents")}
            if "Task_Type" not in columns:
                with engine().begin() as connection:
                    connection.execute(text("ALTER TABLE incidents ADD COLUMN Task_Type VARCHAR(32)"))
            if "Session_ID" not in columns:
                with engine().begin() as connection:
                    connection.execute(text("ALTER TABLE incidents ADD COLUMN Session_ID VARCHAR(64)"))


def db_session() -> Session:
    yield SessionLocal()()
