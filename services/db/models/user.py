"""User table definition."""

from typing import List, Optional
import threading

from sqlalchemy import JSON, Column
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .base import SoftDelete, TimeStamped


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
    
    @classmethod
    def generate_next_id(cls) -> str:
        """生成下一个数字ID,格式: 000001, 000002, ...
        
        线程安全的自增ID生成器。
        """
        global _user_id_counter, _user_id_lock
        with _user_id_lock:
            _user_id_counter += 1
            return f"{_user_id_counter:06d}"
    
    @classmethod
    def set_id_counter(cls, start_from: int):
        """设置ID计数器起始值 (用于初始化或测试)。"""
        global _user_id_counter, _user_id_lock
        with _user_id_lock:
            _user_id_counter = start_from

