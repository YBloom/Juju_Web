"""Observability and send queue tables."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from .base import SendQueueStatus, TimeStamped, utcnow


class Metric(TimeStamped, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=128)
    value: float = Field(default=0)
    labels: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    labels_hash: Optional[str] = Field(default=None, index=True, max_length=64)


class ErrorLog(TimeStamped, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    scope: str = Field(index=True, max_length=64)
    code: Optional[str] = Field(default=None, max_length=32, index=True)
    message: str
    context: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    ts: datetime = Field(default_factory=utcnow, index=True)


class SendQueue(TimeStamped, SQLModel, table=True):
    """通知发送队列 - 支持重试和补发。"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Target
    user_id: str = Field(index=True, max_length=32)
    channel: str = Field(default="qq_private", max_length=32)  # qq_private, web_push, email
    
    # Payload
    scope: str = Field(index=True, max_length=64)  # ticket_update, broadcast, etc
    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    
    # Status
    status: SendQueueStatus = Field(default=SendQueueStatus.PENDING, index=True)
    retry_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None, max_length=512)
    next_retry_at: Optional[datetime] = Field(default=None, index=True)
    sent_at: Optional[datetime] = Field(default=None)
    
    # Reference (for deduplication)
    ref_id: Optional[str] = Field(default=None, max_length=64, index=True, description="e.g. TicketUpdateLog.id")
