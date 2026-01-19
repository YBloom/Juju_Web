"""User table definition."""

from typing import List, Optional

from sqlalchemy import JSON, Column
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .base import SoftDelete, TimeStamped


class User(TimeStamped, SoftDelete, SQLModel, table=True):
    """QQ 用户模型，对应 PRD 中的 User 表。"""

    user_id: str = Field(primary_key=True, max_length=32)
    nickname: Optional[str] = Field(default=None, max_length=128)
    active: bool = Field(default=True, nullable=False)
    transactions_success: int = Field(default=0, nullable=False, index=True)
    trust_score: int = Field(default=0, nullable=False, index=True)

    # Web Auth Fields
    auth_provider: Optional[str] = Field(default="qq", max_length=32, description="oauth provider (qq, google, etc)")
    auth_id: Optional[str] = Field(default=None, max_length=128, description="unique id from provider")
    email: Optional[str] = Field(default=None, max_length=255, index=True)
    avatar_url: Optional[str] = Field(default=None, max_length=512)

    # Bot Settings
    bot_interaction_mode: str = Field(default="hybrid", max_length=20, description="hybrid, lite, legacy")
    global_notification_level: int = Field(default=0, nullable=False, description="0=off, 1=new, 2=new+restock, 3=+back, 4=+decrease, 5=all")

    extra_json: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    memberships: Mapped[List["Membership"]] = Relationship(
        back_populates="user",
        sa_relationship=relationship("Membership", back_populates="user"),
    )
    subscriptions: Mapped[List["Subscription"]] = Relationship(
        back_populates="user",
        sa_relationship=relationship("Subscription", back_populates="user"),
    )
