from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

from web.dependencies import (
    service, 
    limiter, 
    key_func_remote, 
    key_func_local,
    saoju_service,
    START_TIME
)

router = APIRouter(tags=["events"])
logger = logging.getLogger(__name__)

@router.get("/api/events/list")
@limiter.limit("60/minute", key_func=key_func_remote)
@limiter.limit("1000/minute", key_func=key_func_local)
async def list_all_events(request: Request):
    """Get all events for the main listing."""
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
        })
    
    return JSONResponse(
        content={"results": results},
        headers={
            "Cache-Control": "public, max-age=30, must-revalidate"
        }
    )


@router.get("/api/events/search")
@limiter.limit("60/minute", key_func=key_func_remote)
@limiter.limit("1000/minute", key_func=key_func_local)
async def search_events(request: Request, q: str):
    """Search events by title or alias."""
    if not q:
        return {"results": []}
    
    logger.info(f"🔍 [用户行为] 搜索演出: {q}")
    
    # 1. Search ID by name
    res = await service.get_event_id_by_name(q)
    if not res:
        # Fallback: search multiple
        events = await service.search_events(q)
        return {"results": [e.model_dump(mode='json') for e in events]}
    
    # 2. If ID found, get full details
    event_id, title = res
    events = await service.search_events(title)
    return {"results": [e.model_dump(mode='json') for e in events]}

@router.get("/api/events/date")
async def get_events_by_date(date: str):
    """Get events for a specific date (YYYY-MM-DD)."""
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        tickets = await service.get_events_by_date(dt)
        return {"results": [t.model_dump(mode='json') for t in tickets]}
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}

@router.get("/api/events/{event_id}")
async def get_event_detail(event_id: str):
    """Get full details for a specific event."""
    # Note: Using get_event from service
    result = await service.get_event(event_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": "Event not found"})
        
    # Frontend expects {results: [...]} format for compatibility
    return {"results": [result.model_dump(mode='json')]}

@router.get("/api/tickets/recent-updates")
async def get_recent_ticket_updates(request: Request, limit: int = 20, types: str = "new,restock,back,pending"):
    """Get recent ticket updates."""
    logger.info("🎫 [用户行为] 查看票务动态 (最近更新)")

    change_types = [t.strip() for t in types.split(",") if t.strip()] if types else None
    
    updates = await service.get_recent_updates(limit=limit, change_types=change_types)
    
    return JSONResponse(
        content={"results": [u.model_dump(mode='json') for u in updates]},
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@router.get("/api/meta/artists")
async def get_all_artists():
    """Get list of all artists for autocomplete."""
    await saoju_service._ensure_artist_map()
    artists = list(saoju_service.data.get("artists_map", {}).keys())
    return {"artists": artists}

@router.get("/api/meta/status")
async def get_service_status():
    """Get status and last update times for services."""
    from services.config import config
    
    saoju_updated = saoju_service.data.get("updated_at")
    
    from services.hulaquan.tables import HulaquanEvent
    from services.db.connection import session_scope
    from sqlmodel import select, col
    
    hlq_time = None
    with session_scope() as session:
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
            "version": "v1.4",
            "start_time": START_TIME
        }
    }
