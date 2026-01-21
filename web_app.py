import asyncio
import logging
import time
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env file immediately
load_dotenv()

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from contextlib import asynccontextmanager

# Import shared dependencies
from web.dependencies import (
    START_TIME,
    SERVER_VERSION,
    limiter,
    service,
    saoju_service,
    notification_engine
)
from services.config import config

# 自定义日志格式化器,使用UTC+8时区
class BeijingFormatter(logging.Formatter):
    """使用北京时间(UTC+8)的日志格式化器"""
    
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=ZoneInfo("Asia/Shanghai"))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    def format(self, record):
        if not hasattr(record, 'message'):
            record.message = record.getMessage()
            
        msg_lower = record.message.lower()
        is_system_log = record.name.startswith("uvicorn") or "startup" in msg_lower or "shutdown" in msg_lower
        
        if is_system_log:
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
                record.msg = new_msg
                record.message = new_msg
                record.args = () 
        
        if record.name == "uvicorn.access" and not getattr(record, "is_custom_action", False):
            if '" 200' in record.message:
                 new_msg = f"🌐 [访问] {record.message}"
                 record.msg = new_msg
                 record.message = new_msg
                 record.args = ()
        
        result = super().format(record)
        
        if len(record.message) > 100 and '\n' in record.message:
            lines = record.message.split('\n')
            indent = ' ' * 4
            formatted_msg = '\n'.join([lines[0]] + [indent + line for line in lines[1:]])
            result = result.replace(record.message, formatted_msg)
            
        return result

# 访问日志过滤器
class AccessLogFilter(logging.Filter):
    """过滤掉静态资源和健康检查的日志 (200 OK)"""
    def filter(self, record):
        msg = record.getMessage()
        if "GET /static/" in msg and " 200" in msg:
            return False
        if "GET /api/meta/status" in msg and " 200" in msg:
            return False
        if "HEAD /" in msg and " 200" in msg:
            return False
        return True

# 配置日志
def setup_logging():
    """配置应用程序日志"""
    formatter = BeijingFormatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

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
    
    for log_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"]:
        logger = logging.getLogger(log_name)
        if log_name == "uvicorn.access":
             logger.addFilter(AccessLogFilter())
        
        if logger.handlers:
            for h in logger.handlers:
                h.setFormatter(formatter)
        else:
            if not logger.propagate:
                logger.addHandler(console_handler)

# Setup logging with Beijing timezone
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting 剧剧 (YYJ) Web Service...")
    
    # Background Scheduler Logic
    scheduler_task = None
    
    # NOTE: Notification Consumer is NOW MOVED to Bot Service.
    # Web service only produces SendQueue items (via process_updates).

    if config.ENABLE_CRAWLER:
        logger.info("Crawler ENABLED. Starting background scheduler...")
        
        async def _run_scheduler():
            last_saoju_near = 0
            last_saoju_distant = 0
            
            while True:
                try:
                    now_ts = time.time()
                    
                    # 1. Hulaquan Sync (Every ~5 mins)
                    logger.info("Scheduler: Starting Hulaquan data sync...")
                    updates = await service.sync_all_data()
                    
                    if updates:
                         logger.info(f"Scheduler: Detected {len(updates)} updates, processing notifications...")
                         enqueued = await notification_engine.process_updates(updates)
                         logger.info(f"Scheduler: Enqueued {enqueued} new notifications.")
                    
                    # 2. Saoju Near Future (Every 4 hours)
                    if now_ts - last_saoju_near > 14400:
                         logger.info("Scheduler: Starting Saoju Near Future sync (0-120d)...")
                         await saoju_service.sync_future_days(0, 120)
                         last_saoju_near = time.time()

                    # 3. Saoju Distant Future (Every 24 hours)
                    if now_ts - last_saoju_distant > 86400:
                         logger.info("Scheduler: Starting Saoju Distant Tour sync (>120d)...")
                         await saoju_service.sync_distant_tours(120)
                         
                         logger.info("Scheduler: Starting 2026 Full Year Sync...")
                         try:
                             sch_now = datetime.now()
                             start_2026 = datetime(2026, 1, 1)
                             end_2026 = datetime(2026, 12, 31)
                             start_offset = (start_2026 - sch_now).days
                             end_offset = (end_2026 - sch_now).days + 1
                             await saoju_service.sync_future_days(start_offset, end_offset)
                         except Exception as e:
                             logger.error(f"Error in 2026 Sync: {e}")
                             
                         last_saoju_distant = time.time()
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
    
    tasks_to_cancel = []
    if scheduler_task: tasks_to_cancel.append(scheduler_task)
    
    for t in tasks_to_cancel:
        t.cancel()
    
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
    
    # Close services
    await saoju_service.close()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter

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

# 404 Redirect Handler
from fastapi.responses import RedirectResponse
async def not_found_handler(request: Request, exc):
    """
    Redirect all 404 (Not Found) requests to the homepage.
    """
    return RedirectResponse(url="/")

app.add_exception_handler(404, not_found_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Proxy Headers (Trust all proxies for now, essential for Nginx/Cloudflare)
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Define static path first
static_path = Path(__file__).parent / "web" / "static"

# Maintenance Mode (must be added BEFORE mounting static files)
from web.middleware.maintenance import MaintenanceMiddleware
maintenance_page = static_path / "maintenance.html"
app.add_middleware(MaintenanceMiddleware, maintenance_page_path=maintenance_page)

# Static Files (mount after middleware)
app.mount("/static", StaticFiles(directory=static_path), name="static")


# --- API Endpoints ---
from web.routers import auth, subscription, marketplace, user, events, tasks, avatar, admin, analytics, feedback

app.include_router(auth.router)

@app.get("/auth")
async def magic_link_legacy_redirect(token: str = None):
    """Legacy /auth endpoint redirecting to new /auth/magic-link"""
    from fastapi.responses import RedirectResponse
    if token:
        return RedirectResponse(f"/auth/magic-link?token={token}")
    return Response(status_code=400, content="Invalid Link")
app.include_router(subscription.router)
app.include_router(marketplace.router)
app.include_router(user.router)
app.include_router(events.router)
app.include_router(tasks.router)
app.include_router(avatar.router)
app.include_router(admin.router)
app.include_router(admin.api_router)
app.include_router(analytics.router)
app.include_router(feedback.router)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve favicon.ico"""
    return Response(content=None, status_code=301, headers={"Location": "/static/img/logo.png"})

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

@app.get("/api/meta/config")
async def get_public_config():
    """获取公开的配置信息 (前端使用)"""
    from services.captcha import get_site_key
    
    return {
        "bot_uin": os.getenv("BOT_UIN", "3044829389"),
        "turnstile_site_key": get_site_key()
    }

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    index_file = static_path / "index.html"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        
        # Cache Busting
        import re
        content = re.sub(
            r'href="(/static/css/[^"]+\.css)(?:\?v=[^"]*)?"', 
            f'href="\\1?v={SERVER_VERSION}"', 
            content
        )
        content = re.sub(
            r'src="(/static/js/[^"]+\.js)(?:\?v=[^"]*)?"', 
            f'src="\\1?v={SERVER_VERSION}"', 
            content
        )
        
        response = HTMLResponse(content=content)
        response.headers["Cache-Control"] = "no-cache"
        return response
        
    return HTMLResponse("<h1>Web Interface Not Found</h1>")

@app.get("/help", response_class=HTMLResponse)
async def help_page():
    """Serve the static help page."""
    help_file = static_path / "help.html"
    if help_file.exists():
        content = help_file.read_text(encoding="utf-8")
        response = HTMLResponse(content=content)
        # Prevent caching to ensure updates are seen immediately
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    return HTMLResponse("<h1>Help Page Not Found</h1>", status_code=404)

if __name__ == "__main__":
    import uvicorn
    # 允许外部访问
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
