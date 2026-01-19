"""用户认证方式和账号合并日志模型。"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from .base import TimeStamped


class UserAuthMethod(TimeStamped, SQLModel, table=True):
    """用户认证方式表 - 支持一个用户绑定多个认证方式。
    
    例如:
        User(user_id="000001")
          ├─ UserAuthMethod(provider="email", provider_user_id="user@example.com")
          └─ UserAuthMethod(provider="qq", provider_user_id="3132859862")
    """
    __tablename__ = "user_auth_method"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 关联用户
    user_id: str = Field(foreign_key="user.user_id", index=True, max_length=32)
    
    # 认证方式
    provider: str = Field(max_length=32, index=True, description="认证提供商: qq, email, wechat, etc")
    provider_user_id: str = Field(max_length=255, index=True, description="该认证方式下的用户唯一标识(QQ号/邮箱地址)")
    
    # 是否为主要登录方式
    is_primary: bool = Field(default=False, nullable=False)
    
    # 额外数据(如密码哈希)
    extra_data: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="存储认证相关的额外数据,如密码哈希"
    )
    
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_provider_user",
        ),
    )


class AccountMergeLog(TimeStamped, SQLModel, table=True):
    """账号合并日志 - 用于审计和追踪账号合并操作。
    
    场景: 用户A绑定QQ时,发现该QQ已绑定用户B,合并账号后记录。
    """
    __tablename__ = "account_merge_log"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 源账号(被合并的账号)
    source_user_id: str = Field(max_length=32, index=True, description="被合并的用户ID")
    
    # 目标账号(保留的账号)
    target_user_id: str = Field(max_length=32, index=True, description="保留的用户ID")
    
    # 合并时间
    merged_at: datetime = Field(index=True)
    
    # 迁移的订阅数量
    subscriptions_count: int = Field(default=0)
    
    # 数据快照(用于回滚)
    data_snapshot: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="合并前的数据快照,包含源账号的订阅等信息"
    )
    
    # 操作人(可选)
    operator: Optional[str] = Field(default=None, max_length=64, description="执行合并的用户或系统")
