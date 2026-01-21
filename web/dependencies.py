import logging
import time
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from services.hulaquan.service import HulaquanService
from services.saoju.service import SaojuService
from services.db.init import init_db
from web.session import get_session, SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)

# --- Global Constants ---
# Initialize with Beijing Time
START_TIME = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
# Version for cache busting (using timestamp relative to start)
# Version for cache busting (using Git Commit Hash for persistence across restarts)
def get_git_revision_short_hash() -> str:
    import subprocess
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
    except Exception:
        # Fallback to timestamp if not a git repo or git not found
        return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")

SERVER_VERSION = get_git_revision_short_hash()


# --- Services ---
# Initialize DB before services
_db_engine = init_db()
logger.info(f"✓ Database initialized at module level: {_db_engine.url}")

# Service Singletons
service = HulaquanService()
saoju_service = SaojuService()

# Bot & Notification
from services.notification.engine import NotificationEngine

# Initialize NotificationEngine in Producer-Only mode (Web side)
# Web app creates SendQueue items but does not send them directly.
# The Bot service will consume the queue.
notification_engine = NotificationEngine(bot_api=None)


# --- Job System ---
class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
    
    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = {
            "id": job_id,
            "status": "pending", # pending, running, completed, failed
            "progress": 0,
            "message": "等待开始...",
            "result": None,
            "error": None,
            "created_at": time.time()
        }
        return job_id
        
    def update_progress(self, job_id: str, progress: int, message: str = None):
        if job_id in self.jobs:
            self.jobs[job_id]["progress"] = progress
            self.jobs[job_id]["status"] = "running"
            if message:
                self.jobs[job_id]["message"] = message
                
    def complete_job(self, job_id: str, result: Any):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["progress"] = 100
            self.jobs[job_id]["message"] = "完成"
            self.jobs[job_id]["result"] = result
            
    def fail_job(self, job_id: str, error: str):
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = error
            self.jobs[job_id]["message"] = f"错误: {error}"

    def get_job(self, job_id: str) -> Optional[Dict]:
        return self.jobs.get(job_id)

job_manager = JobManager()


# --- Rate Limiting Helpers ---
def key_func_remote(request: Request):
    """Return key for remote users (applies standard limits)."""
    ip = get_remote_address(request)
    if ip in ["127.0.0.1", "localhost", "::1"]:
        return "localhost-remote-exempt" # Exempt from remote limits
    return ip

def key_func_local(request: Request):
    """Return key for local users (applies relaxed limits)."""
    ip = get_remote_address(request)
    if ip in ["127.0.0.1", "localhost", "::1"]:
        return ip # Apply local limits
    return "remote-local-exempt" # Exempt from local limits

# Initialize Limiter
limiter = Limiter(key_func=get_remote_address)


# --- Auth Dependency ---
def get_current_user(request: Request) -> Optional[Dict]:
    """从 Cookie 获取当前登录用户 (使用统一的 web.session)"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    # 使用统一的 Session 获取逻辑
    return get_session(session_id)
