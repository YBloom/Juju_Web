"""
Session 和认证相关数据模型
"""
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Field, SQLModel
import secrets

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


class UserSession(SQLModel, table=True):
    """持久化用户 Session"""
    __tablename__ = "user_session"
    
    session_id: str = Field(primary_key=True, max_length=64)
    user_id: str = Field(index=True, max_length=32)
    created_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
    expires_at: datetime = Field(index=True)
    provider: str = Field(default="qq", max_length=32)  # qq, email
    ip_address: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=512)
    
    @classmethod
    def create(cls, user_id: str, provider: str = "qq", expires_days: int = 30, 
               ip_address: str = None, user_agent: str = None) -> "UserSession":
        """创建新 Session"""
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        return cls(
            session_id=secrets.token_urlsafe(32),
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(days=expires_days),
            provider=provider,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None
        )
    
    def is_expired(self) -> bool:
        """检查 Session 是否过期"""
        return datetime.now(ZoneInfo("Asia/Shanghai")) > self.expires_at


class EmailVerification(SQLModel, table=True):
    """邮箱验证码"""
    __tablename__ = "email_verification"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, max_length=255)
    code: str = Field(max_length=6)
    purpose: str = Field(max_length=32)  # register, login, reset_password
    created_at: datetime = Field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Shanghai")))
    expires_at: datetime
    used: bool = Field(default=False)
    
    @classmethod
    def create(cls, email: str, purpose: str, expires_minutes: int = 10) -> "EmailVerification":
        """创建验证码"""
        import random
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        return cls(
            email=email.lower().strip(),
            code=str(random.randint(100000, 999999)),
            purpose=purpose,
            created_at=now,
            expires_at=now + timedelta(minutes=expires_minutes),
            used=False
        )
    
    def is_valid(self, code: str) -> bool:
        """验证码是否有效"""
        if self.used:
            return False
        if datetime.now(ZoneInfo("Asia/Shanghai")) > self.expires_at:
            return False
        return self.code == code
