import asyncio
import logging
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
from services.hulaquan.service import HulaquanService
from services.config import config

# Initialize Service
# Enable crawler in this process if configured (Phase 3 will set config.ENABLE_CRAWLER = True for this process context)
# For now, we manually ensure crawler starts if we are running as the main web process
service = HulaquanService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting Hulaquan Web Service...")
    
    # Start Crawler if enabled (or force it for now since this is the dedicated process)
    # TODO: In Phase 3, we will use config.ENABLE_CRAWLER, but for now let's use a simple flag or method
    # Assume service handles its own scheduling or we launch it here.
    # The original bot used ncatbot scheduler. We might need to port the scheduler or use a simple loop.
    # For this MVP step, we rely on the service being just a data reader.
    # Crawler migration is planned for full separation.
    
    logger.info("Service is ready.")
    yield
    # Shutdown logic
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
static_path = Path(__file__).parent / "web" / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# --- API Endpoints ---

@app.get("/api/events/list")
async def list_all_events():
    """Get all events for the main listing."""
    events = await service.get_all_events()
    # Pydantic v2 uses model_dump. SQLModel objects should support it.
    # We explicitly convert to dict to ensure serialization works as expected.
    results = []
    for e in events:
        try:
            # Try model_dump (Pydantic v2)
            d = e.model_dump(exclude={"tickets"})
        except AttributeError:
            # Fallback for older Pydantic/SQLModel
            d = e.dict(exclude={"tickets"})
        results.append(d)
        
    return {"results": results}

@app.get("/api/events/{event_id}")
async def get_event_detail(event_id: str):
    """Get full details for a specific event."""
    # We reuse search logic or get direct
    # Since we don't have direct request by ID in service yet exposed cleanly for "get one event object",
    # we can use get_event_id_by_name if we knew the name, or iterate list.
    # Let's add specific logic or use existing DB session.
    # Service implementation detail:
    from sqlmodel import select
    from services.hulaquan.tables import HulaquanEvent
    from services.db.connection import session_scope
    
    with session_scope() as session:
        event = session.get(HulaquanEvent, event_id)
        if not event:
            return {"error": "Event not found"}
        
        # Manually construct to include tickets logic same as search_events result
        # Or better: call service.search_events with exact title
        # But title might be duplicate? ID is safer.
        # Let's use the formatting logic from service.search_events but for single ID.
        pass
        
    # Better approach: update Service to have get_event_by_id
    # For now, let's just do search by title from the ID... wait, ID is safer.
    # Let's just return what we can find. Or easier:
    # use service.search_events(event.title)
    return {"results": await service.get_event_details_by_id(event_id)}

@app.get("/api/events/search")
async def search_events(q: str):
    """Search events by title or alias."""
    if not q:
        return {"results": []}
    
    # 1. Search ID by name
    res = await service.get_event_id_by_name(q)
    if not res:
        # Fallback: search multiple
        events = await service.search_events(q)
        return {"results": [e.dict() for e in events]}
    
    # 2. If ID found, get full details
    event_id, title = res
    # We don't have get_event_by_id exposed yet, but search should cover it
    # Re-using search_events which does strict or partial match
    events = await service.search_events(title)
    return {"results": [e.dict() for e in events]}

@app.get("/api/events/date")
async def get_events_by_date(date: str):
    """Get events for a specific date (YYYY-MM-DD)."""
    from datetime import datetime
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        tickets = await service.get_events_by_date(dt)
        return {"results": [t.dict() for t in tickets]}
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

@app.get("/api/events/co-cast")
async def get_co_casts(casts: str):
    """Get tickets with co-performing casts. casts=name1,name2"""
    if not casts:
        return {"results": []}
    
    cast_list = [c.strip() for c in casts.split(",") if c.strip()]
    tickets = await service.search_co_casts(cast_list)
    return {"results": [t.dict() for t in tickets]}

# --- Frontend Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = static_path / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>Web Interface Not Found</h1>"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
