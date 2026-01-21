"""Initialize database schema."""

from __future__ import annotations

from typing import Optional

from sqlmodel import SQLModel

from .connection import get_engine
from .models import *  # noqa: F401,F403


def init_db(db_path: Optional[str] = None):
    engine = get_engine(db_path)
    SQLModel.metadata.create_all(engine)
    return engine
