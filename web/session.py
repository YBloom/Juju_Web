"""
Session 管理 - 使用 SQLite 持久化
"""
from typing import Dict, Any, Optional
from services.db.models import UserSession
from services.db.connection import session_scope

SESSION_COOKIE_NAME = "mb_session"

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """从数据库获取 Session"""
    if not session_id:
        return None
    
    with session_scope() as db:
        session = db.get(UserSession, session_id)
        if session and not session.is_expired():
            return {
                "user_id": session.user_id,
                "provider": session.provider,
                "created_at": session.created_at.isoformat()
            }
    return None


def delete_session(session_id: str) -> bool:
    """删除 Session"""
    if not session_id:
        return False
    
    with session_scope() as db:
        session = db.get(UserSession, session_id)
        if session:
            db.delete(session)
            return True
    return False


# 兼容旧代码的全局字典（已弃用，仅为向后兼容）
# 新代码应使用 get_session() 函数
sessions: Dict[str, Dict[str, Any]] = {}
