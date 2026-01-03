"""Database engine/session helpers for SQLModel."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator, Optional

from sqlmodel import Session, create_engine

DEFAULT_DB_PATH = Path("data/musicalbot.db")


def _ensure_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _create_engine(db_path: Path, *, echo: bool = False):
    url = f"sqlite:///{db_path}"
    engine = create_engine(
        url,
        echo=echo,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
        conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
    return engine


@lru_cache(maxsize=1)
def get_engine(db_path: Optional[str] = None, *, echo: Optional[bool] = None):
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    echo_flag = echo if echo is not None else False
    return _create_engine(_ensure_parent(path), echo=echo_flag)


@contextmanager
def session_scope(db_path: Optional[str] = None) -> Iterator[Session]:
    engine = get_engine(db_path)
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
