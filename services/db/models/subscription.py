from typing import Optional
from sqlmodel import SQLModel, Field, UniqueConstraint
from datetime import datetime

class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", index=True)
    kind: str = Field(index=True, max_length=16)   # ticket/event/actor
    target_id: str = Field(index=True, max_length=128)
    mode: int = Field(default=0)                  # 你的旧逻辑沿用
    created_at: datetime = Field(default_factory=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "kind", "target_id",
                                       name="uq_user_kind_target"),)
