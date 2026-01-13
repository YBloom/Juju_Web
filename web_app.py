import asyncio
import logging
import uuid
import time
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Backport for Python < 3.9 if needed, though 3.12 is used.
    from backports.zoneinfo import ZoneInfo

# 自定义日志格式化器,使用UTC+8时区
class BeijingFormatter(logging.Formatter):
    """使用北京时间(UTC+8)的日志格式化器"""
    
    def formatTime(self, record, datefmt=None):
        # 转换为北京时间
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo("Asia/Shanghai"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    def format(self, record):
        # 1. Ensure message is generated
        if not hasattr(record, 'message'):
            record.message = record.getMessage()
            
        # 2. 标识是否是系统/Uvicorn 生命周期日志
        # Use simple string checks on lowercased message
        msg_lower = record.message.lower()
        is_system_log = record.name.startswith("uvicorn") or "startup" in msg_lower or "shutdown" in msg_lower
        
        # 自定义高亮/格式化逻辑
        if is_system_log:
            # 简化无关信息，或者高亮显示
            if "started server process" in msg_lower:
                new_msg = f"🚀 [系统] 服务进程已启动 | PID: {os.getpid()}"
            elif "application startup complete" in msg_lower:
                new_msg = "✅ [系统] 应用启动完成"
            elif "shutting down" in msg_lower:
                new_msg = "🛑 [系统] 服务正在停止..."
            elif "finished server process" in msg_lower:
                new_msg = "👋 [系统] 服务进程已结束"
            elif "waiting for application startup" in msg_lower:
                 new_msg = "⏳ [系统] 等待应用启动..."
            else:
                new_msg = None
                
            if new_msg:
                # Update record in place
                record.msg = new_msg
                record.message = new_msg
                record.args = () # Clear args since we handled them
        
        # 3. 如果是 uvicorn.access 日志，且未被过滤（Filter在Handler层，这里主要修饰格式），尝试汉化
        if record.name == "uvicorn.access" and not getattr(record, "is_custom_action", False):
            # 将 "GET /path HTTP/1.1" 200 OK 这种格式稍微美化
            if '" 200' in record.message:
                 # We must update record.msg and clear args to prevent super().format() from regenerating the old message
                 new_msg = f"🌐 [访问] {record.message}"
                 record.msg = new_msg
                 record.message = new_msg
                 record.args = ()
        
        # 调用父类 format 生成基础字符串 (包含 asctime 等)
        result = super().format(record)
        
        # 如果消息很长且包含换行,增加缩进
        if len(record.message) > 100 and '\n' in record.message:
            lines = record.message.split('\n')
            # 多行消息,增加缩进
            indent = ' ' * 4
            formatted_msg = '\n'.join([lines[0]] + [indent + line for line in lines[1:]])
            result = result.replace(record.message, formatted_msg)
            
        return result

# 访问日志过滤器
class AccessLogFilter(logging.Filter):
    """过滤掉静态资源和健康检查的日志 (200 OK)"""
    def filter(self, record):
        msg = record.getMessage()
        
        # 1. 过滤静态资源 (如 /static/js/..., /static/img/...)
        if "GET /static/" in msg and " 200" in msg:
            return False
            
        # 2. 过滤健康检查/状态查询
        if "GET /api/meta/status" in msg and " 200" in msg:
            return False
            
        # 3. 过滤 Uptime 检查 (HEAD /)
        if "HEAD /" in msg and " 200" in msg:
            return False
            
        return True

# 配置日志
def setup_logging():
    """配置应用程序日志"""
    # 创建格式化器
    formatter = BeijingFormatter(
        # 确保时间戳在最前面
        fmt='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 配置根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 1. 移除现有handlers
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    # 2. 添加控制台handler (stdout) -> 被Supervisor捕获到 web_out.log / web_err.log
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 3. 添加应用级文件handler
    from logging.handlers import TimedRotatingFileHandler
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 4. 关键：强制 Uvicorn 使用我们的格式化器
    # Uvicorn 在 CLI 启动时可能已经配置了 logger，我们需要覆盖它的 handler formatter
    # 常见的 Uvicorn loggers: "uvicorn", "uvicorn.error", "uvicorn.access"
    for log_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"]:
        logger = logging.getLogger(log_name)
        
        # 为 access logger 添加过滤器
        if log_name == "uvicorn.access":
             logger.addFilter(AccessLogFilter())
        
        # 并不一定所有的 logger 都有 handler (access 可能有, error 可能有)
        # 如果有 handler，替换 formatter
        if logger.handlers:
            for h in logger.handlers:
                h.setFormatter(formatter)
        else:
            # 如果没有handler (且 propagate=False)，它可能不会输出
            # 我们强制添加 console_handler 以确保格式一致且能看到
            # 但要注意避免重复 (如果 propagate=True 则根 logger 会处理)
            # Uvicorn 默认 error propagate=False, access propagate=False
            if not logger.propagate:
                logger.addHandler(console_handler)

# Global Service Info
# Initialize with Beijing Time
START_TIME = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
# Version for cache busting (using timestamp relative to start)
SERVER_VERSION = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")

from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import secrets
import jwt
from datetime import timedelta

# --- Magic Link Auth Configuration ---
# JWT 密钥和配置
JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 5  # Token 有效期 5 分钟
SESSION_COOKIE_NAME = "mb_session"
SESSION_EXPIRE_DAYS = 30  # Cookie 有效期 30 天
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")

# 简单的内存 Session 存储 (生产环境可换成 Redis)
# Simple in-memory session store (use Redis in production)
_sessions: Dict[str, Dict[str, Any]] = {}

def create_magic_link_token(qq_id: str, nickname: str = "") -> str:
    """为 Bot 用户生成 Magic Link Token"""
    payload = {
        "qq_id": qq_id,
        "nickname": nickname,
        "exp": datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(ZoneInfo("Asia/Shanghai")),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_magic_link_token(token: str) -> Optional[Dict]:
    """验证 Magic Link Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_current_user(request: Request) -> Optional[Dict]:
    """从 Cookie 获取当前登录用户"""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    return _sessions.get(session_id)

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Setup logging with Beijing timezone
setup_logging()
logger = logging.getLogger(__name__)

# Import Service
# 导入服务
from services.hulaquan.service import HulaquanService
from services.saoju.service import SaojuService
from services.config import config

# CRITICAL: Initialize database BEFORE creating service instances
# 关键：在创建服务实例之前初始化数据库
# This ensures all tables exist before SaojuService.__init__ calls load_data()
# 这确保在 SaojuService.__init__ 调用 load_data() 之前所有表都已存在
from services.db.init import init_db
_db_engine = init_db()
logger.info(f"✓ Database initialized at module level: {_db_engine.url}")

# Initialize Service
# 初始化服务
# Enable crawler in this process if configured (Phase 3 will set config.ENABLE_CRAWLER = True for this process context)
# 如果已配置，在此进程中启用爬虫（阶段 3 将为此进程上下文设置 config.ENABLE_CRAWLER = True）
# For now, we manually ensure crawler starts if we are running as the main web process
# 目前，如果是作为主 Web 进程运行，我们需手动确保爬虫启动
service = HulaquanService()
saoju_service = SaojuService()

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    # 启动逻辑
    logger.info("Starting Hulaquan Web Service...")
    
    # Database is already initialized at module level (before service instances)
    # 数据库已在模块级别初始化（在服务实例之前）
    
    # Start Crawler if enabled (or force it for now since this is the dedicated process)
    # 如果启用则启动爬虫（或者因为这是专用进程所以强制启动）
    # TODO: In Phase 3, we will use config.ENABLE_CRAWLER, but for now let's use a simple flag or method
    # TODO: 在阶段 3 中，我们将使用 config.ENABLE_CRAWLER，但现在先使用简单的标志或方法
    # Assume service handles its own scheduling or we launch it here.
    # 假设服务处理其自己的调度，或者我们在此时启动它。
    # The original bot used ncatbot scheduler. We might need to port the scheduler or use a simple loop.
    # 原始机器人使用了 ncatbot 调度器。我们可能需要移植调度器或使用简单的循环。
    # For this MVP step, we rely on the service being just a data reader.
    # 对于此 MVP 步骤，我们依赖服务仅作为数据读取器。
    # Crawler migration is planned for full separation.
    # 计划完全分离爬虫迁移。
    
    
    # Background Scheduler Logic
    scheduler_task = None
    if config.ENABLE_CRAWLER:
        logger.info("Crawler ENABLED. Starting background scheduler...")
        
        async def _run_scheduler():
            # Timestamps for periodic tasks
            last_saoju_near = 0
            last_saoju_distant = 0
            
            # Allow some startup delay or immediate run? 
            # Let's run near sync immediately, distant sync maybe immediately too or staggered.
            
            while True:
                try:
                    now_ts = time.time()
                    
                    # 1. Hulaquan Sync (Every ~5 mins, governed by sleep)
                    logger.info("Scheduler: Starting Hulaquan data sync...")
                    await service.sync_all_data()
                    
                    # 2. Saoju Near Future (Every 4 hours = 14400s)
                    if now_ts - last_saoju_near > 14400:
                         logger.info("Scheduler: Starting Saoju Near Future sync (0-120d)...")
                         await saoju_service.sync_future_days(0, 120)
                         last_saoju_near = time.time()

                    # 3. Saoju Distant Future (Every 24 hours = 86400s)
                    if now_ts - last_saoju_distant > 86400:
                         logger.info("Scheduler: Starting Saoju Distant Tour sync (>120d)...")
                         # Default 1st arg is start buffer days
                         await saoju_service.sync_distant_tours(120)
                         last_saoju_distant = time.time()

                    # 4. Saoju 2026 Sync (Reuse Near Future Logic but target 2026 range)
                    # Sync 2026-01-01 to 2026-12-31 daily
                    # Current year is 2026, so this is "Current Year Full Sync"
                    if now_ts - last_saoju_distant > 86400: # Run with distant loop
                         logger.info("Scheduler: Starting 2026 Full Year Sync...")
                         try:
                             # Calculate offsets to cover 2026-01-01 to 2026-12-31 relative to now
                             from datetime import datetime
                             sch_now = datetime.now()
                             start_2026 = datetime(2026, 1, 1)
                             end_2026 = datetime(2026, 12, 31)
                             
                             # Offsets in days
                             start_offset = (start_2026 - sch_now).days
                             end_offset = (end_2026 - sch_now).days + 1 # +1 to ensure coverage
                             
                             # Ensure we don't sync too far past (though end_offset handles it)
                             # sync_future_days handles the loop
                             await saoju_service.sync_future_days(start_offset, end_offset)
                             
                             last_saoju_distant = time.time()
                         except Exception as e:
                             logger.error(f"Error in 2026 Sync: {e}")
                except Exception as e:
                    logger.error(f"Scheduler Error: {e}", exc_info=True)
                
                await asyncio.sleep(300)

        scheduler_task = asyncio.create_task(_run_scheduler())
    else:
        logger.info("Crawler DISABLED. (Set HLQ_ENABLE_CRAWLER=True to enable)")

    logger.info("Service is ready.")
    yield
    # Shutdown logic
    logger.info("Shutting down...")
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    
    # Close services
    await saoju_service.close()

# Helper Functions for Rate Limiting
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
app = FastAPI(lifespan=lifespan)
security = HTTPBasic()
app.state.limiter = limiter

# --- Admin Security ---
def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """Validate Basic Auth credentials for admin routes."""
    # Use env vars or default fallback
    correct_username = os.getenv("ADMIN_USERNAME", "admin").encode("utf8")
    correct_password = os.getenv("ADMIN_PASSWORD", "musicalbot").encode("utf8")
    
    current_username_bytes = credentials.username.encode("utf8")
    current_password_bytes = credentials.password.encode("utf8")
    
    is_correct_username = secrets.compare_digest(current_username_bytes, correct_username)
    is_correct_password = secrets.compare_digest(current_password_bytes, correct_password)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Custom Rate Limit Handler
async def friendly_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """处理请求频率超限的情况，返回用户友好的错误提示。"""
    return JSONResponse(
        status_code=429,
        content={
            "error": "一分钟内发起请求过多，请稍等片刻后重试", 
            "detail": str(exc),
            "tip": "每分钟最多可发起 5 次搜索请求"
        },
    )
app.add_exception_handler(RateLimitExceeded, friendly_rate_limit_handler)

# CORS
# 跨域资源共享 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
# 静态文件
static_path = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# --- API Endpoints ---
# --- API 端点 ---

# Register Auth Router

# Register Subscription Router

# Register Marketplace Router

@app.get("/api/events/list")
@limiter.limit("60/minute", key_func=key_func_remote)
@limiter.limit("1000/minute", key_func=key_func_local)
async def list_all_events(request: Request):
    """Get all events for the main listing.
    获取主要列表的所有事件。
    """
    # Manually construct to ensure no serialization ambiguity
    # 手动构建以确保没有序列化歧义

    results = []
    events = await service.get_all_events()
    for e in events:
        results.append({
            "id": e.id,
            "title": e.title,
            "location": e.location or "",
            "city": e.city or "",
            "update_time": e.update_time.isoformat() if e.update_time else None,
            "total_stock": e.total_stock,
            "price_range": e.price_range,
            "schedule_range": e.schedule_range,
            # "tickets" excluded
        })
    
    # 添加适度缓存控制：允许30秒缓存，平衡性能与数据新鲜度
    return JSONResponse(
        content={"results": results},
        headers={
            "Cache-Control": "public, max-age=30, must-revalidate"
        }
    )


@app.get("/api/events/search")
@limiter.limit("60/minute", key_func=key_func_remote)
@limiter.limit("1000/minute", key_func=key_func_local)
async def search_events(request: Request, q: str):
    """Search events by title or alias.
    按标题或别名搜索事件。
    """
    if not q:
        return {"results": []}
    
    # Log user action
    logger.info(f"🔍 [用户行为] 搜索演出: {q}")
    
    # 1. Search ID by name
    # 1. 按名称搜索 ID
    res = await service.get_event_id_by_name(q)
    if not res:
        # Fallback: search multiple
        # 后备：搜索多个
        events = await service.search_events(q)
        return {"results": [e.model_dump(mode='json') for e in events]}
    
    # 2. If ID found, get full details
    # 2. 如果找到 ID，获取完整详细信息
    event_id, title = res
    # We don't have get_event_by_id exposed yet, but search should cover it
    # 我们尚未暴露 get_event_by_id，但搜索应该涵盖它
    # Re-using search_events which does strict or partial match
    # 重用执行严格或部分匹配的 search_events
    events = await service.search_events(title)
    return {"results": [e.model_dump(mode='json') for e in events]}

@app.get("/api/events/date")
async def get_events_by_date(date: str):
    """Get events for a specific date (YYYY-MM-DD).
    获取特定日期的事件 (YYYY-MM-DD)。
    """
    from datetime import datetime
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        tickets = await service.get_events_by_date(dt)
        return {"results": [t.model_dump(mode='json') for t in tickets]}
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

@app.get("/api/tickets/recent-updates")
async def get_recent_ticket_updates(request: Request, limit: int = 20, types: str = "new,restock,back,pending"):
    """
    Get recent ticket updates for the ticket dashboard.
    获取最近的票务更新用于票务动态展示。
    
    Query Parameters:
        limit: Maximum number of updates to return (default 20, max 100)
        types: Comma-separated list of change types to filter (e.g. "new,restock")
    """
    # Log user action
    logger.info("🎫 [用户行为] 查看票务动态 (最近更新)")

    # Parse types
    change_types = [t.strip() for t in types.split(",") if t.strip()] if types else None
    
    # Fetch updates from service
    updates = await service.get_recent_updates(limit=limit, change_types=change_types)
    
    # Convert to dict for JSON response
    # Use model_dump(mode='json') to properly serialize datetime objects
    # 使用 model_dump(mode='json') 正确序列化 datetime 对象
    # 添加缓存控制headers，防止移动端浏览器缓存旧数据
    return JSONResponse(
        content={"results": [u.model_dump(mode='json') for u in updates]},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/events/co-cast")
async def get_co_casts(casts: str, only_student: bool = False):
    """Get tickets with co-performing casts. casts=name1,name2
    获取具有联合演出演员的票务信息。casts=name1,name2
    (Legacy blocking endpoint)
    """
    if not casts:
        return {"results": []}
    
    cast_list = [c.strip() for c in casts.split(",") if c.strip()]
    if not cast_list:
        return {"results": []}

    if only_student:
        # Search local Hulaquan DB for student tickets
        tickets = await service.search_co_casts(cast_list)
        return {"results": tickets, "source": "hulaquan"}
    else:
        # Legacy: Search Saoju service
        async with saoju_service as s:
            results = await s.match_co_casts(cast_list, show_others=True)
            return {"results": results, "source": "saoju"}

@app.post("/api/tasks/co-cast")
@limiter.limit("5/minute", key_func=key_func_remote)
@limiter.limit("200/minute", key_func=key_func_local)
async def start_cocast_search(request: Request):
    """Start an async background task for co-cast search."""
    data = await request.json()
    casts = data.get("casts", "")
    only_student = data.get("only_student", False)
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    
    if not casts:
        return {"error": "Missing casts"}
    
    cast_list = [c.strip() for c in casts.split(",") if c.strip()]
    
    # --- LOGGING START ---
    # Submit log to DB asynchronously with retry for database lock
    async def log_search():
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                from services.hulaquan.tables import HulaquanSearchLog
                from services.db.connection import session_scope
                import json
                
                # Normalize list: sort and unique
                normalized_list = sorted(list(set(cast_list)))
                is_combo = len(normalized_list) > 1
                
                with session_scope() as session:
                    log_entry = HulaquanSearchLog(
                        search_type="co-cast",
                        query_str=casts,
                        artists=json.dumps(normalized_list, ensure_ascii=False),
                        is_combination=is_combo
                    )
                    session.add(log_entry)
                return  # Success
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Backoff: 0.5s, 1s, 1.5s
                    continue
                logger.warning(f"Failed to log search (attempt {attempt+1}): {e}")

    asyncio.create_task(log_search())
    # --- LOGGING END ---
    
    job_id = job_manager.create_job()
    
    async def run_task(jid, c_list, is_student, s_date, e_date):
        try:
            if is_student:
                # Student tickets logic (unchanged for now)
                job_manager.update_progress(jid, 10, "正在搜索本地数据库...")
                await asyncio.sleep(0.5) 
                tickets = await service.search_co_casts(c_list)
                res = {"results": tickets, "source": "hulaquan"}
                job_manager.complete_job(jid, res)
            else:
                # Saoju search with progress and date range
                # Use global service instance directly, do NOT use async with (context manager closes it)
                s = saoju_service
                async def progress_cb(p, msg):
                    job_manager.update_progress(jid, p, msg)
                    
                results = await s.match_co_casts(
                    c_list, 
                    show_others=True, 
                    progress_callback=progress_cb,
                    start_date=s_date,
                    end_date=e_date
                )
                res = {"results": results, "source": "saoju"}
                job_manager.complete_job(jid, res)
        except Exception as e:
            logger.error(f"Task failed: {e}", exc_info=True)
            job_manager.fail_job(jid, str(e))

    # Start background task
    asyncio.create_task(run_task(job_id, cast_list, only_student, start_date, end_date))
    
    return {"task_id": job_id}

@app.post("/api/log/view")
async def log_view_event(request: Request):
    """Log when a user views an event (student ticket)."""
    data = await request.json()
    title = data.get("title", "")
    if not title:
        return {"status": "ignored"}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            from services.hulaquan.tables import HulaquanSearchLog
            from services.db.connection import session_scope
            
            with session_scope() as session:
                log_entry = HulaquanSearchLog(
                    search_type="view_event",
                    query_str=title,
                    artists=None,
                    is_combination=False
                )
                session.add(log_entry)
            return {"status": "ok"}
        except Exception as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            logger.warning(f"Failed to log view (attempt {attempt+1}): {e}")
            return {"status": "error"}

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    job = job_manager.get_job(task_id)
    if not job:
        return {"error": "Task not found"}, 404
    return job

@app.get("/api/meta/artists")
async def get_all_artists():
    """Get list of all artists for autocomplete."""
    await saoju_service._ensure_artist_map()
    artists = list(saoju_service.data.get("artists_map", {}).keys())
    return {"artists": artists}

@app.get("/api/meta/status")
async def get_service_status():
    """Get status and last update times for services."""
    # Find latest Hulaquan update from DB (approximate by checking a recent event)
    # Since we don't store a global "last update" timestamp, we can query the latest event updated_at or use a memory var.
    # Ideally HulaquanService should track last sync time.
    # For now, let's assume if we are running the scheduler, we are "Active".
    # But user wants "Last Updated: X mins ago".
    # Efficient way: HulaquanService adds a `last_sync_time` property.
    
    # For Saoju: "24小时内有效" is static policy, but we can return the cache update time if available.
    saoju_updated = saoju_service.data.get("updated_at")
    
    # For Hulaquan, let's query the latest updated_at from DB for now as a robust fallback
    from services.hulaquan.tables import HulaquanEvent
    from services.db.connection import session_scope
    from sqlmodel import select, col
    
    hlq_time = None
    with session_scope() as session:
        # Get one event with max updated_at
        stmt = select(HulaquanEvent.updated_at).order_by(col(HulaquanEvent.updated_at).desc()).limit(1)
        res = session.exec(stmt).first()
        if res:
            hlq_time = res
            
    return {
        "hulaquan": {
            "active": config.ENABLE_CRAWLER,
            "last_updated": hlq_time.isoformat() if hlq_time else None
        },
        "saoju": {
            "last_updated": saoju_updated
        },
        "service_info": {
            "version": "v1.2",
            "start_time": START_TIME
        }
    }
@app.get("/api/events/{event_id}")
async def get_event_detail(event_id: str):
    """Get full details for a specific event.
    获取特定事件的完整详细信息。
    """
    # We reuse search logic or get direct
    # 我们重用搜索逻辑或直接获取
    # Since we don't have direct request by ID in service yet exposed cleanly for "get one event object",
    # 由于服务尚未清晰地暴露"获取一个事件对象"的直接 ID 请求，
    # we can use get_event_id_by_name if we knew the name, or iterate list.
    # 如果知道名称，我们可以使用 get_event_id_by_name，或者遍历列表。
    # Let's add specific logic or use existing DB session.
    # 让我们添加特定逻辑或使用现有的 DB 会话。
    # Service implementation detail:
    # 服务实现细节：
    from sqlmodel import select, col
    from services.hulaquan.tables import HulaquanEvent, SaojuChangeLog, HulaquanSearchLog
    from services.db.connection import session_scope
    
    with session_scope() as session:
        event = session.get(HulaquanEvent, event_id)
        if not event:
            return {"error": "Event not found"}
        
        # Log user action
        logger.info(f"📄 [用户行为] 查看演出详情: {event.title} (ID: {event_id})")
        
        # Manually construct to include tickets logic same as search_events result
        # 手动构建以包含与 search_events 结果相同的票务逻辑
        # Or better: call service.search_events with exact title
        # 或者更好：使用确切标题调用 service.search_events
        # But title might be duplicate? ID is safer.
        # 但是标题可能有重复？ID 更安全。
        # Let's use the formatting logic from service.search_events but for single ID.
        # 让我们使用 service.search_events 的格式化逻辑，但是针对单个 ID。
        pass
        
    # Better approach: update Service to have get_event_by_id
    # 更好的方法：更新 Service 以拥有 get_event_by_id
    # For now, let's just do search by title from the ID... wait, ID is safer.
    # 目前，让我们仅通过 ID 进行标题搜索... 等等，ID 更安全。
    # Let's just return what we can find. Or easier:
    # 让我们只返回我们能找到的内容。或者更简单：
    # use service.search_events(event.title)
    # 使用 service.search_events(event.title)
    return {"results": await service.get_event_details_by_id(event_id)}


@app.get("/api/analytics/heatmap")
async def get_heatmap(year: int = 2025):
    """Get heatmap data for a specific year (SaojuShow)."""
    
    # Log user action
    logger.info(f"📊 [用户行为] 查看演出热力图 ({year})")
    
    # All years now read from database (2023-2026 all have data in SaojuShow table)

    from services.hulaquan.tables import SaojuShow
    from services.db.connection import session_scope
    from sqlmodel import select
    from collections import Counter
    from datetime import datetime
    
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31, 23, 59, 59)
    
    data = []
    total = 0
    peak = 0
    
    with session_scope() as session:
        # Query SaojuShow for daily show counts
        stmt = select(SaojuShow.date).where(SaojuShow.date >= start_date).where(SaojuShow.date <= end_date)
        results = session.exec(stmt).all()
        
        # Count per day (YYYY-MM-DD string)
        counts = Counter()
        for dt in results:
            d_str = dt.strftime("%Y-%m-%d")
            counts[d_str] += 1
            
        # Format for ECharts [[date, count], ...]
        data = [[k, v] for k, v in counts.items()]
        total = len(results)
        if data:
            peak = max(counts.values())
            
        # Calculate zero_days (days with 0 shows)
        # For current year, only count days until today
        # For past years, count whole year
        now = datetime.now()
        is_current_year = (year == now.year)
        
        zero_days = 0
        current_day = start_date
        
        # Determine the end date for counting: today if current year, else end of year
        count_end_date = min(now, end_date) if is_current_year else end_date
        
        # Iterate through each day
        temp_date = start_date
        while temp_date <= count_end_date:
            d_str = temp_date.strftime("%Y-%m-%d")
            if counts[d_str] == 0:
                zero_days += 1
            temp_date = datetime(temp_date.year, temp_date.month, temp_date.day) # reset time
            from datetime import timedelta
            temp_date += timedelta(days=1)
            
    return {
        "year": year,
        "total": total,
        "peak": peak,
        "zero_days": zero_days,
        "data": data
    }


# --- Frontend Routes ---
# --- 前端路由 ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(username: str = Depends(get_current_username)):
    """Serve the protected Admin Dashboard."""
    admin_file = Path(__file__).parent / "web" / "admin.html"
    if admin_file.exists():
        return admin_file.read_text(encoding="utf-8")
    return "<h1>Admin Panel Not Found</h1>"

@app.get("/api/admin/logs")
async def get_admin_logs(file: str = "web_out.log", lines: int = 500, username: str = Depends(get_current_username)):
    """Read system logs from /var/log/musicalbot/ (Protected)."""
    # Security: whitelist allowed files to prevent path traversal
    ALLOWED_FILES = ["web_out.log", "web_err.log", "auto_update.log"]
    if file not in ALLOWED_FILES:
        raise HTTPException(status_code=400, detail="Invalid log file")
    
    log_path = Path(f"/var/log/musicalbot/{file}")
    
    if not log_path.exists():
        return f"[Error] Log file not found: {log_path}"
        
    try:
        # Simple tail implementation using 'tail' command is robust, 
        # or read last N bytes. Python readlines on huge files is slow.
        # Let's use shell tail for efficiency if on Linux/Mac
        import subprocess
        # Use -n lines
        cmd = ["tail", "-n", str(lines), str(log_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return PlainTextResponse(f"[Error] Reading logs failed: {result.stderr}")
        return PlainTextResponse(result.stdout)
    except Exception as e:
        return f"[Error] Exception reading logs: {str(e)}"

@app.get("/api/admin/saoju/changes")
async def get_saoju_changes(limit: int = 50, username: str = Depends(get_current_username)):
    """Get latest Saoju data changes (CDC logs)."""
    from services.hulaquan.tables import SaojuChangeLog
    from services.db.connection import session_scope
    from sqlmodel import select, col
    
    with session_scope() as session:
        stmt = select(SaojuChangeLog).order_by(col(SaojuChangeLog.detected_at).desc()).limit(limit)
        logs = session.exec(stmt).all()
        return {
            "count": len(logs),
            "results": [l.model_dump(mode='json') for l in logs]
        }

@app.get("/api/admin/analytics/searches")
async def get_search_analytics(username: str = Depends(get_current_username)):
    """Aggregate search analytics."""
    from services.hulaquan.tables import HulaquanSearchLog
    from services.db.connection import session_scope
    from sqlmodel import select, col
    from collections import Counter
    import json
    
    with session_scope() as session:
        logs = session.exec(select(HulaquanSearchLog)).all()
        
        # 1. Artist Frequency (Individual appearances in any search)
        artist_counts = Counter()
        
        # 2. Solo Frequency (Searches with exactly 1 artist)
        solo_counts = Counter()
        
        # 3. Combo Frequency (String rep of combo)
        combo_counts = Counter()
        
        # 4. View Frequency
        view_counts = Counter()
        
        for l in logs:
            if l.search_type == "view_event":
                view_counts[l.query_str] += 1
                continue
                
            if l.search_type == "co-cast" and l.artists:
                try:
                    names = json.loads(l.artists)
                    # Count for individual artist
                    for n in names:
                        artist_counts[n] += 1
                        
                    # Logic
                    if len(names) == 1:
                        solo_counts[names[0]] += 1
                    elif len(names) > 1:
                        # Normalized string
                        combo_str = " & ".join(names)
                        combo_counts[combo_str] += 1
                except:
                    pass

        def format_top(counter, limit=20):
            return [{"name": k, "count": v} for k, v in counter.most_common(limit)]
            
        return {
            "top_artists": format_top(artist_counts),
            "top_solo": format_top(solo_counts),
            "top_combos": format_top(combo_counts),
            "top_views": format_top(view_counts)
        }

@app.get("/api/admin/bot/qr")
async def get_bot_qr_code(username: str = Depends(get_current_username)):
    """
    Retrieve NapCat QR Code or Login Status.
    Since NapCat runs in Docker/Systemd, we can try to fetch from its internal HTTP API 
    if configured, or parse the latest log file.
    
    Assumption: NapCat WebUI is not publicly exposed, but local HTTP API might be on 3000 or 6099.
    
    Fallback: Look for 'napcat.log' in standard location and grep for 'qrcode'.
    """
    # TODO: Implement robust method. 
    # For now, let's try to read a shared 'qr_code.txt' if we configure NapCat to write it, 
    # or just proxy to NapCat's local API if available.
    
    # Mock for implementation verification
    return {
        "status": "unknown", 
        "qr_code": None, 
        "message": "NapCat integration pending. Please check server logs."
    }


@app.post("/api/feedback")
@limiter.limit("5/minute", key_func=key_func_remote)
@limiter.limit("20/minute", key_func=key_func_local)
async def submit_feedback(request: Request):
    """Submit a feedback (bug, suggestion, wish)."""
    data = await request.json()
    fb_type = data.get("type")
    content = data.get("content")
    contact = data.get("contact")
    
    if not fb_type or not content:
        return JSONResponse(status_code=400, content={"error": "Missing type or content"})
        
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    
    with session_scope() as session:
        fb = Feedback(
            type=fb_type,
            content=content,
            contact=contact
        )
        session.add(fb)
    
    # 异步发送邮件通知（不阻塞响应）
    async def send_notification():
        try:
            from services.email.service import notify_feedback_received
            await notify_feedback_received(fb_type, content, contact)
        except Exception as e:
            logger.warning(f"发送反馈通知邮件失败: {e}")
    
    asyncio.create_task(send_notification())
        
    return {"status": "ok", "message": "Feedback submitted"}

@app.get("/api/admin/feedbacks")
async def get_feedbacks(limit: int = 50, username: str = Depends(get_current_username)):
    """Get latest feedbacks (excluding ignored ones)."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    from sqlmodel import select, col
    
    with session_scope() as session:
        stmt = select(Feedback).where(Feedback.is_ignored == False).order_by(col(Feedback.created_at).desc()).limit(limit)
        items = session.exec(stmt).all()
        return {
            "count": len(items),
            "results": [i.model_dump(mode='json') for i in items]
        }



@app.get("/api/feedbacks/public")
async def get_public_feedbacks():
    """Get public feedback wall (curated)."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    from sqlmodel import select, col
    
    with session_scope() as session:
        # Show public items, ordered by reply time (recently updated first) -> then create time
        stmt = select(Feedback).where(Feedback.is_public == True).order_by(
            col(Feedback.reply_at).desc(), 
            col(Feedback.created_at).desc()
        ).limit(50)
        items = session.exec(stmt).all()
        return {
            "results": [i.model_dump(mode='json') for i in items]
        }

@app.post("/api/admin/feedback/{feedback_id}/reply")
async def reply_feedback(feedback_id: int, request: Request, username: str = Depends(get_current_username)):
    """Admin reply to feedback and toggle public status."""
    data = await request.json()
    reply_content = data.get("reply")
    is_public = data.get("is_public", False)
    
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            return JSONResponse(status_code=404, content={"error": "Not found"})
            
        fb.admin_reply = reply_content
        fb.is_public = is_public
        if reply_content:
            fb.reply_at = datetime.now(ZoneInfo("Asia/Shanghai"))
            fb.status = "closed" # Auto close if replied
            
        session.add(fb)
        # Commit handled by context manager
        
    return {"status": "ok"}

@app.post("/api/admin/feedback/{feedback_id}/ignore")
async def ignore_feedback(feedback_id: int, username: str = Depends(get_current_username)):
    """Ignore a feedback item."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            return JSONResponse(status_code=404, content={"error": "Not found"})
            
        fb.is_ignored = True
        fb.ignored_at = datetime.now(ZoneInfo("Asia/Shanghai"))
        session.add(fb)
        
    return {"status": "ok", "message": "Feedback ignored"}

@app.post("/api/admin/feedback/{feedback_id}/unignore")
async def unignore_feedback(feedback_id: int, username: str = Depends(get_current_username)):
    """Unignore a feedback item."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            return JSONResponse(status_code=404, content={"error": "Not found"})
            
        fb.is_ignored = False
        fb.ignored_at = None
        session.add(fb)
        
    return {"status": "ok", "message": "Feedback restored"}

@app.get("/api/admin/feedbacks/ignored")
async def get_ignored_feedbacks(limit: int = 100, username: str = Depends(get_current_username)):
    """Get ignored feedbacks list."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    from sqlmodel import select, col
    
    with session_scope() as session:
        stmt = select(Feedback).where(Feedback.is_ignored == True).order_by(col(Feedback.ignored_at).desc()).limit(limit)
        items = session.exec(stmt).all()
        return {
            "count": len(items),
            "results": [i.model_dump(mode='json') for i in items]
        }

@app.delete("/api/admin/feedback/{feedback_id}")
async def delete_feedback(feedback_id: int, username: str = Depends(get_current_username)):
    """Permanently delete a feedback item."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            return JSONResponse(status_code=404, content={"error": "Not found"})
        session.delete(fb)
        
    return {"status": "ok", "message": "Feedback deleted"}

@app.post("/api/admin/feedback/{feedback_id}/resolve")
async def resolve_feedback(feedback_id: int, username: str = Depends(get_current_username)):
    """Mark a feedback as resolved (closed)."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            return JSONResponse(status_code=404, content={"error": "Not found"})
            
        fb.status = "closed"
        session.add(fb)
        
    return {"status": "ok", "message": "Feedback resolved"}

@app.post("/api/admin/feedback/{feedback_id}/reopen")
async def reopen_feedback(feedback_id: int, username: str = Depends(get_current_username)):
    """Reopen a resolved feedback."""
    from services.hulaquan.tables import Feedback
    from services.db.connection import session_scope
    
    with session_scope() as session:
        fb = session.get(Feedback, feedback_id)
        if not fb:
            return JSONResponse(status_code=404, content={"error": "Not found"})
            
        fb.status = "open"
        session.add(fb)
        
    return {"status": "ok", "message": "Feedback reopened"}

# --- Magic Link Auth Endpoints ---
# --- 魔术链接认证端点 ---

@app.get("/auth")
async def magic_link_auth(token: str = None):
    """
    Magic Link 登录端点。
    Bot 生成带 token 的链接，用户点击后自动登录。
    """
    if not token:
        return HTMLResponse("""
            <html><body>
            <h2>❌ 无效的登录链接</h2>
            <p>请通过 QQ 机器人私聊发送 <code>/web</code> 获取登录链接。</p>
            </body></html>
        """, status_code=400)
    
    # 验证 Token
    payload = verify_magic_link_token(token)
    if not payload:
        return HTMLResponse("""
            <html><body>
            <h2>⏰ 链接已过期</h2>
            <p>登录链接有效期为 5 分钟。请重新发送 <code>/web</code> 获取新链接。</p>
            </body></html>
        """, status_code=401)
    
    qq_id = payload.get("qq_id")
    nickname = payload.get("nickname", "")
    
    # 创建 Session
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {
        "qq_id": qq_id,
        "nickname": nickname,
        "created_at": time.time(),
    }
    
    logger.info(f"🔐 [用户登录] QQ: {qq_id}, Nickname: {nickname}")
    
    # 设置 Cookie 并重定向到首页
    response = HTMLResponse(f"""
        <html><body>
        <h2>✅ 登录成功！</h2>
        <p>欢迎回来，{nickname or qq_id}！正在跳转...</p>
        <script>setTimeout(() => window.location.href = '/', 1500);</script>
        </body></html>
    """)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )
    return response

# Removed old auth endpoints (replaced by web.routers.auth)
# @app.get("/api/me") and @app.post("/logout") are now in router

@app.head("/")
async def head_root():
    """Handle HEAD requests for uptime monitoring."""
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    """Lightweight health check endpoint."""
    return {"status": "ok", "timestamp": time.time()}

@app.get("/8726ae85b5d54209b12c399526d8e3b0.txt", response_class=PlainTextResponse)
async def wechat_verification():
    """微信验证文件"""
    return "563f0d9e2f141bb88997c42d353289de5668be13"

@app.get("/", response_class=HTMLResponse)

async def read_root(request: Request):
    index_file = static_path / "index.html"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        
        # Cache Busting Strategy A:
        # 1. Inject server version into static asset URLs
        #    Replaces ?v=... or adds ?v=... to .css and .js files
        import re
        # Pattern to find css/js links and inject/replace version
        # Matches: href="/static/css/style.css?v=old" or href="/static/css/style.css"
        
        # Replace CSS versions
        content = re.sub(
            r'href="(/static/css/[^"]+\.css)(?:\?v=[^"]*)?"', 
            f'href="\\1?v={SERVER_VERSION}"', 
            content
        )
        
        # Replace JS versions
        content = re.sub(
            r'src="(/static/js/[^"]+\.js)(?:\?v=[^"]*)?"', 
            f'src="\\1?v={SERVER_VERSION}"', 
            content
        )
        
        response = HTMLResponse(content=content)
        # 2. Force browser to re-validate HTML (Negotiated Cache)
        response.headers["Cache-Control"] = "no-cache"
        return response
        
    return HTMLResponse("<h1>Web Interface Not Found</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
