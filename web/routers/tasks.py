from fastapi import APIRouter, Request
import asyncio
import logging

from web.dependencies import (
    job_manager, 
    service, 
    saoju_service, 
    limiter, 
    key_func_remote, 
    key_func_local
)

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)

@router.get("/api/events/co-cast")
async def get_co_casts(casts: str, only_student: bool = False):
    """Get tickets with co-performing casts. (Legacy blocking endpoint)"""
    if not casts:
        return {"results": []}
    
    cast_list = [c.strip() for c in casts.split(",") if c.strip()]
    if not cast_list:
        return {"results": []}

    if only_student:
        tickets = await service.search_co_casts(cast_list)
        return {"results": tickets, "source": "hulaquan"}
    else:
        async with saoju_service as s:
            results = await s.match_co_casts(cast_list, show_others=True)
            return {"results": results, "source": "saoju"}

@router.post("/api/tasks/co-cast")
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
    async def log_search():
        max_retries = 3
        for attempt in range(max_retries):
            try:
                from services.hulaquan.tables import HulaquanSearchLog
                from services.db.connection import session_scope
                import json
                
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
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                logger.warning(f"Failed to log search (attempt {attempt+1}): {e}")

    asyncio.create_task(log_search())
    # --- LOGGING END ---
    
    job_id = job_manager.create_job()
    
    async def run_task(jid, c_list, is_student, s_date, e_date):
        try:
            if is_student:
                job_manager.update_progress(jid, 10, "正在搜索本地数据库...")
                await asyncio.sleep(0.5) 
                tickets = await service.search_co_casts(c_list)
                res = {"results": tickets, "source": "hulaquan"}
                job_manager.complete_job(jid, res)
            else:
                # Use global service instance directly
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

    asyncio.create_task(run_task(job_id, cast_list, only_student, start_date, end_date))
    
    return {"task_id": job_id}

@router.post("/api/log/view")
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

@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    job = job_manager.get_job(task_id)
    if not job:
        return {"error": "Task not found"}, 404
    return job
