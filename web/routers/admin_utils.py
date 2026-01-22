import os
import secrets
from fastapi import Request

# Admin session 管理（简单的内存存储）
# key: session_token, value: True
_admin_sessions = {}

# Admin cookie 名称
ADMIN_COOKIE_NAME = "admin_session"


def verify_admin_credentials(username: str, password: str) -> bool:
    """验证 admin 账号密码（从环境变量读取）"""
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    
    if not admin_password:
        # 如果没有设置密码，出于安全考虑，拒绝登录
        return False
    
    return username == admin_username and password == admin_password


def create_admin_session() -> str:
    """创建一个新的 admin session token"""
    token = secrets.token_urlsafe(32)
    _admin_sessions[token] = True
    return token


def verify_admin_session(token: str) -> bool:
    """验证 admin session token 是否有效"""
    return token in _admin_sessions


def has_admin_session(request: Request) -> bool:
    """检查请求是否有有效的 admin session（供中间件调用）"""
    admin_session = request.cookies.get(ADMIN_COOKIE_NAME)
    return admin_session and verify_admin_session(admin_session)
