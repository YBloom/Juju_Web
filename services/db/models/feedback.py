from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from services.utils.timezone import now as timezone_now

class Feedback(SQLModel, table=True):
    """
    用户意见反馈表 (统一版本)
    """
    __tablename__: str = "feedback"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=timezone_now, index=True)
    
    # 基础信息
    user_id: Optional[str] = Field(default=None, index=True)
    nickname: Optional[str] = Field(default=None)
    contact: Optional[str] = Field(default=None) # 邮箱或联系方式
    
    # 类型: "bug", "suggestion", "wish"
    type: str = Field(index=True)
    
    content: str
    
    # 状态: "open", "closed", "pending", "resolved", "ignored"
    status: str = Field(default="pending")
    
    # 管理/展示功能
    is_public: bool = Field(default=False, index=True)
    admin_reply: Optional[str] = None
    reply_at: Optional[datetime] = None
    
    # 忽略管理
    is_ignored: bool = Field(default=False)
    ignored_at: Optional[datetime] = None
