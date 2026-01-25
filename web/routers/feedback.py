from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import logging
from sqlmodel import select, col

from services.db.models import Feedback
from services.db.connection import session_scope
from services.email import notify_feedback_received
from web.dependencies import limiter, get_remote_address

router = APIRouter(tags=["feedback"])
logger = logging.getLogger(__name__)

# Rate Limit Helpers
def key_func_remote(request: Request):
    ip = get_remote_address(request)
    if ip in ["127.0.0.1", "localhost", "::1"]:
        return "localhost-remote-exempt"
    return ip

def key_func_local(request: Request):
    ip = get_remote_address(request)
    if ip in ["127.0.0.1", "localhost", "::1"]:
        return ip
    return "remote-local-exempt"

@router.post("/api/feedback")
@limiter.limit("5/minute", key_func=key_func_remote)
@limiter.limit("20/minute", key_func=key_func_local)
async def submit_feedback(request: Request):
    """Submit a feedback (bug, suggestion, wish)."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    fb_type = data.get("type")
    content = data.get("content")
    contact = data.get("contact")
    
    if not fb_type or not content:
        return JSONResponse(status_code=400, content={"error": "Missing type or content"})
        
    with session_scope() as session:
        fb = Feedback(
            type=fb_type,
            content=content,
            contact=contact
        )
        session.add(fb)
    
    # 异步发送邮件通知
    async def send_notification():
        try:
            await notify_feedback_received(fb_type, content, contact)
        except Exception as e:
            logger.warning(f"发送反馈通知邮件失败: {e}")
    
    asyncio.create_task(send_notification())
        
    return {"status": "ok", "message": "Feedback submitted"}

@router.get("/api/feedbacks/public")
async def get_public_feedbacks():
    """Get public feedback wall (curated)."""
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
