"""
User Settings API Router
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime

from services.db.connection import get_engine
from services.db.models import User
from web.session import sessions

router = APIRouter(prefix="/api/user", tags=["user"])


# --- Dependencies ---

def get_session():
    """FastAPI dependency for database session"""
    engine = get_engine()
    with Session(engine) as session:
        yield session

def get_current_user(request: Request) -> Optional[dict]:
    """Delegate to web_app logic or session check"""
    # This is a bit circular if we import web_app, so we duplicate the session logic cleanly here
    # or rely on the same utility.
    # For now, let's use the session cookie logic directly as it's simple.
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        return None
    return sessions[session_id]

def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# --- Models ---

class UserSettingsUpdate(BaseModel):
    bot_interaction_mode: str

class UserSettingsResponse(BaseModel):
    user_id: str
    nickname: Optional[str]
    avatar_url: Optional[str]
    bot_interaction_mode: str


# --- Endpoints ---

@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    request: Request,
    user_session: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """Get current user settings"""
    # User session has 'user_id' or 'qq_id'
    # Check session structure from auth.py or logs.
    # Usually it saves 'user_id' if logged via magic link? 
    # Let's check keys. If magic link uses 'qq_id', we map it.
    
    uid = user_session.get("user_id") or user_session.get("qq_id")
    if not uid:
         raise HTTPException(status_code=400, detail="Invalid session state")

    db_user = session.get(User, uid)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserSettingsResponse(
        user_id=db_user.user_id,
        nickname=db_user.nickname,
        avatar_url=db_user.avatar_url,
        bot_interaction_mode=db_user.bot_interaction_mode or "hybrid"
    )

@router.put("/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    data: UserSettingsUpdate,
    request: Request,
    user_session: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """Update user settings"""
    uid = user_session.get("user_id") or user_session.get("qq_id")
    if not uid:
         raise HTTPException(status_code=400, detail="Invalid session state")

    db_user = session.get(User, uid)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if data.bot_interaction_mode not in ["hybrid", "lite", "legacy", "full"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
        
    db_user.bot_interaction_mode = data.bot_interaction_mode
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    return UserSettingsResponse(
        user_id=db_user.user_id,
        nickname=db_user.nickname,
        avatar_url=db_user.avatar_url,
        bot_interaction_mode=db_user.bot_interaction_mode
    )
