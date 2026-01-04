import asyncio
import logging
import uuid
import time
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import Service
# 导入服务
from services.hulaquan.service import HulaquanService
from services.saoju.service import SaojuService
from services.config import config

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
    
    logger.info("Service is ready.")
    yield
    # Shutdown logic
    # 关闭逻辑
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

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

@app.get("/api/events/list")
async def list_all_events():
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
            "update_time": e.update_time,
            "total_stock": e.total_stock,
            "price_range": e.price_range,
            "schedule_range": e.schedule_range,
            # "tickets" excluded
        })
        
    return {"results": results}

@app.get("/api/events/search")
async def search_events(q: str):
    """Search events by title or alias.
    按标题或别名搜索事件。
    """
    if not q:
        return {"results": []}
    
    # 1. Search ID by name
    # 1. 按名称搜索 ID
    res = await service.get_event_id_by_name(q)
    if not res:
        # Fallback: search multiple
        # 后备：搜索多个
        events = await service.search_events(q)
        return {"results": [e.dict() for e in events]}
    
    # 2. If ID found, get full details
    # 2. 如果找到 ID，获取完整详细信息
    event_id, title = res
    # We don't have get_event_by_id exposed yet, but search should cover it
    # 我们尚未暴露 get_event_by_id，但搜索应该涵盖它
    # Re-using search_events which does strict or partial match
    # 重用执行严格或部分匹配的 search_events
    events = await service.search_events(title)
    return {"results": [e.dict() for e in events]}

@app.get("/api/events/date")
async def get_events_by_date(date: str):
    """Get events for a specific date (YYYY-MM-DD).
    获取特定日期的事件 (YYYY-MM-DD)。
    """
    from datetime import datetime
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        tickets = await service.get_events_by_date(dt)
        return {"results": [t.dict() for t in tickets]}
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

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
        return {"results": [t.dict() for t in tickets], "source": "hulaquan"}
    else:
        # Legacy: Search Saoju service
        async with saoju_service as s:
            results = await s.match_co_casts(cast_list, show_others=True)
            return {"results": results, "source": "saoju"}

@app.post("/api/tasks/co-cast")
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
    
    job_id = job_manager.create_job()
    
    async def run_task(jid, c_list, is_student, s_date, e_date):
        try:
            if is_student:
                # Student tickets logic (unchanged for now)
                job_manager.update_progress(jid, 10, "正在搜索本地数据库...")
                await asyncio.sleep(0.5) 
                tickets = await service.search_co_casts(c_list)
                res = {"results": [t.dict() for t in tickets], "source": "hulaquan"}
                job_manager.complete_job(jid, res)
            else:
                # Saoju search with progress and date range
                async with saoju_service as s:
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
    from sqlmodel import select
    from services.hulaquan.tables import HulaquanEvent
    from services.db.connection import session_scope
    
    with session_scope() as session:
        event = session.get(HulaquanEvent, event_id)
        if not event:
            return {"error": "Event not found"}
        
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


# --- Frontend Routes ---
# --- 前端路由 ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = static_path / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>Web Interface Not Found</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
