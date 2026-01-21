"""Subscription-related tables."""

from datetime import datetime
from enum import IntEnum
from typing import List, Optional

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .base import SubscriptionFrequency, SubscriptionTargetKind, TimeStamped


class NotificationLevel(IntEnum):
    OFF = 0          # 无通知
    NEW = 1          # 上新
    NEW_RESTOCK = 2  # 上新+补票
    WITH_BACK = 3    # 上新+补票+回流
    WITH_DECREASE = 4 # 上新+补票+回流+余票减
    ALL = 5          # 全量


class Subscription(TimeStamped, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", ondelete="CASCADE", index=True)

    user: Mapped["User"] = Relationship(
        back_populates="subscriptions",
        sa_relationship=relationship("User", back_populates="subscriptions"),
    )
    targets: Mapped[List["SubscriptionTarget"]] = Relationship(
        back_populates="subscription",
        sa_relationship=relationship(
            "SubscriptionTarget", 
            back_populates="subscription",
            cascade="all, delete-orphan",
            passive_deletes=True
        ),
    )
    options: Mapped[List["SubscriptionOption"]] = Relationship(
        back_populates="subscription",
        sa_relationship=relationship(
            "SubscriptionOption", 
            back_populates="subscription",
            cascade="all, delete-orphan",
            passive_deletes=True
        ),
    )


class SubscriptionTarget(TimeStamped, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="subscription.id", ondelete="CASCADE", nullable=False)
    kind: SubscriptionTargetKind = Field(nullable=False, index=True)
    target_id: Optional[str] = Field(default=None, index=True, max_length=128)
    name: Optional[str] = Field(default=None, max_length=256)
    city_filter: Optional[str] = Field(default=None, max_length=64)
    
    # Filtering for actor subscriptions
    include_plays: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    exclude_plays: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))

    flags: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))

    subscription: Mapped["Subscription"] = Relationship(
        back_populates="targets",
        sa_relationship=relationship("Subscription", back_populates="targets"),
    )

    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "kind",
            "target_id",
            name="uq_subscription_target",
        ),
        Index('idx_sub_kind_target', 'subscription_id', 'kind', 'target_id'),
    )


class SubscriptionOption(TimeStamped, SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subscription_id: int = Field(foreign_key="subscription.id", ondelete="CASCADE", nullable=False, unique=True)
    mute: bool = Field(default=False, nullable=False)
    freq: SubscriptionFrequency = Field(default=SubscriptionFrequency.REALTIME, nullable=False)
    notification_level: int = Field(default=2, nullable=False, description="1=new, 2=new+restock, 3=+back, 4=+decrease, 5=all")
    allow_broadcast: bool = Field(default=True, nullable=False)
    last_notified_at: Optional[datetime] = Field(default=None)
    silent_hours: Optional[str] = Field(default=None, max_length=32, description="e.g. '23:00-08:00' for quiet hours")

    subscription: Mapped["Subscription"] = Relationship(
        back_populates="options",
        sa_relationship=relationship("Subscription", back_populates="options"),
    )
