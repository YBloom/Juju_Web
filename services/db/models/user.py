"""User table definition."""

from datetime import datetime
from typing import List, Optional
import threading

from sqlalchemy import JSON, Column
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .base import SoftDelete, TimeStamped, SubscriptionFrequency, InternalMetadata
from services.db.connection import session_scope


# 模块级别的ID生成器 (避免SQLModel元类干扰)
_user_id_counter: int = 0
_user_id_lock = threading.Lock()


class User(TimeStamped, SoftDelete, SQLModel, table=True):
    """用户模型 - 使用6位数字ID作为主键。"""
    
    user_id: str = Field(primary_key=True, max_length=32, description="6位数字ID,格式: 000001")
    nickname: Optional[str] = Field(default=None, max_length=128)
    active: bool = Field(default=True, nullable=False)
    transactions_success: int = Field(default=0, nullable=False, index=True)
    trust_score: int = Field(default=0, nullable=False, index=True)

    # Web Display
    email: Optional[str] = Field(default=None, max_length=255, index=True, description="用户邮箱,可能为空(纯QQ用户)")
    avatar_url: Optional[str] = Field(default=None, max_length=512)

    # Bot Settings (Unified from SubscriptionOption)
    bot_interaction_mode: str = Field(default="hybrid", max_length=20, description="hybrid, lite, legacy")
    global_notification_level: int = Field(default=0, nullable=False, description="0=off, 1=new, 2=new+restock, 3=+back, 4=+decrease, 5=all")
    
    notification_freq: SubscriptionFrequency = Field(
        default=SubscriptionFrequency.REALTIME, 
        nullable=False,
        sa_column_kwargs={"server_default": "REALTIME"}
    )
    is_muted: bool = Field(default=False, nullable=False)
    allow_broadcast: bool = Field(default=True, nullable=False)
    silent_hours: Optional[str] = Field(default=None, max_length=32, description="e.g. '23:00-08:00'")
    last_notified_at: Optional[datetime] = Field(default=None)

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
        sa_relationship=relationship(
            "Subscription", 
            back_populates="user",
            cascade="all, delete-orphan",
            passive_deletes=True
        ),
    )
    
    @classmethod
    def generate_next_id(cls, session=None) -> str:
        """生成下一个数字ID,格式: 000001, 000002, ...
        
        跨进程安全的原子自增ID生成器。
        使用 internal_metadata 表进行状态同步。
        """
        from sqlalchemy import text

        
        def _get_and_inc(s):
            # SQLite BEGIN IMMEDIATE 确保写锁,防止并发竞态
            s.execute(text("BEGIN IMMEDIATE"))
            
            row = s.get(InternalMetadata, "last_user_id")
            if not row:
                # 如果元数据表没记录,则初始化
                # 兼容性: 检查 user 表中已有的最大 ID
                max_id = cls._query_max_id_from_db(s)
                row = InternalMetadata(key="last_user_id", value=str(max_id))
                s.add(row)
            
            new_id_val = int(row.value) + 1
            row.value = str(new_id_val)
            s.add(row)
            # 注意: session_scope 会在退出时 commit, 释放 IMMEDIATE 锁
            return f"{new_id_val:06d}"

        if session:
            # 如果传入了 session, 假设调用方已经管理了事务
            # 但为了安全, 建议由 generate_next_id 独立管理 ID 分配事务
            return _get_and_inc(session)
        else:
            with session_scope() as s:
                return _get_and_inc(s)
    
    @classmethod
    def _query_max_id_from_db(cls, session) -> int:
        """仅用于初始化时从数据库查找当前最大的数字ID。"""
        from sqlmodel import select, func
        statement = select(func.max(func.cast(cls.user_id, JSON))).where(
            func.length(cls.user_id) == 6
        )
        res = session.exec(statement).first()
        return int(res) if res else 0

    @classmethod
    def set_id_counter(cls, start_from: int):
        """设置ID计数器起始值 (用于迁移或重置)。"""
        """设置ID计数器起始值 (用于迁移或重置)。"""
        with session_scope() as s:
            row = s.get(InternalMetadata, "last_user_id")
            if row:
                row.value = str(start_from)
            else:
                row = InternalMetadata(key="last_user_id", value=str(start_from))
            s.add(row)

