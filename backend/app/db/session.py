"""Database session management (Layer 3)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


def _resolve_db_url() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///") and ":memory:" not in url:
        path_part = url.replace("sqlite:///", "", 1)
        from pathlib import Path

        p = Path(path_part)
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent.parent.parent / p).resolve()
            url = f"sqlite:///{p.as_posix()}"
        p.parent.mkdir(parents=True, exist_ok=True)
    return url


engine = create_engine(
    _resolve_db_url(),
    connect_args={"check_same_thread": False} if "sqlite" in _resolve_db_url() else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
