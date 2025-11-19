"""Lightweight key-value tables for manager metadata."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field

from .base import TimeStamped


class ManagerMetadata(TimeStamped, table=True):
    """Store misc serialized payloads migrated from legacy managers."""

    key: str = Field(primary_key=True, max_length=64)
    payload: Optional[Any] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

