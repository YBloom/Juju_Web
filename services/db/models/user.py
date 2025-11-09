# services/db/models/user.py
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

from .base import TimeStamped, SoftDelete

class User(SQLModel, TimeStamped, SoftDelete, table=True):
    """QQ 用户。主键用 QQ 号字符串，便于对齐现网数据。"""
    user_id: str = Field(primary_key=True)
    nickname: Optional[str] = None
    active: bool = Field(default=True)
    transactions_success: int = Field(default=0, index=True)
    trust_score: int = Field(default=0, index=True)

    # 关系（可选，轻度使用，避免过度 join）
    memberships: List["Membership"] = Relationship(back_populates="user")
    subscriptions: List["Subscription"] = Relationship(back_populates="user")
