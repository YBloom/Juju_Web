"""Base models and enums shared across SQLModel tables."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp.

    SQLModel 默认使用 naive datetime，如果不做处理 SQLite 会混用本地时间。
    统一调用该 helper，确保所有表都保存 UTC 时间，满足 PRD 的约束。
    """

    return datetime.now(timezone.utc)


class TimeStamped(SQLModel, table=False):
    """Mixin that stores creation/update timestamps in UTC."""

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)


class SoftDelete(SQLModel, table=False):
    """Mixin for soft-delete semantics."""

    is_deleted: bool = Field(default=False, nullable=False)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)


class GroupType(str, Enum):
    BROADCAST = "broadcast"
    FILTERED = "filtered"
    PASSIVE = "passive"
    TOOL = "tool"


class SubscriptionFrequency(str, Enum):
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"


class SubscriptionTargetKind(str, Enum):
    PLAY = "play"
    ACTOR = "actor"
    EVENT = "event"
    KEYWORD = "keyword"


class PlaySource(str, Enum):
    SAOJU = "saoju"
    HULAQUAN = "hulaquan"
    DAMAI = "damai"
    LEGACY = "legacy"


class HLQTicketStatus(str, Enum):
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    SOLD_OUT = "sold_out"
    QUEUE = "queue"


class SendQueueStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
