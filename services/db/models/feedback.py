from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from services.utils.timezone import now as timezone_now

class Feedback(SQLModel, table=True):
    """
    用户意见反馈表
    """
    __tablename__: str = "feedback"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    nickname: Optional[str] = Field(default=None)
    
    # 类型: "bug" | "suggestion"
    feedback_type: str = Field(index=True)
    
    content: str
    
    # 状态: "pending", "resolved", "ignored"
    status: str = Field(default="pending")
    
    created_at: datetime = Field(default_factory=timezone_now)
