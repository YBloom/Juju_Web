from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from services.db.models import User
from services.db.connection import session_scope
from typing import Optional
import jwt
import logging
import os
import uuid
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# Reuse configuration from web_app (or repeated here for independence, keeping it DRY is better but importing from web_app might cause circular imports)
# Ideally config should be in a separate module. For now, we redefine or pass dependencies.
# Given web_app.py structure, it's better to implement this as a router that expects dependencies or defined config.

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

# Config (Should match web_app.py or be imported from a config module)
JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
SESSION_COOKIE_NAME = "mb_session"
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")

# Session Store (In-memory for MVP, shared with web_app via import if possible, but circular import risk)
# We will use a separate simple store here or dependency injection. 
# For this step, let's assume we can share the session store or use a new one. 
# Actually, to properly integrate, we should define the Session Logic in a shared service or utils.
# Let's put a simple dict here. In production, use Redis.
_sessions = {} 

def get_session_store():
    return _sessions

@router.get("/magic-link")
async def login_with_magic_link(token: str, request: Request, response: Response):
    """
    Handle Magic Link Login.
    Verifies the token, creates/updates the User, and sets a session cookie.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        qq_id = payload.get("qq_id")
        nickname = payload.get("nickname", "User")
        
        if not qq_id:
            raise HTTPException(status_code=400, detail="Invalid Token Payload")
            
        logger.info(f"🔐 [Auth] Magic Link Login attempt: QQ {qq_id}")
        
        # 1. Update/Create User in DB
        with session_scope() as session:
            user = session.get(User, qq_id)
            if not user:
                logger.info(f"✨ [Auth] Creating new user for QQ {qq_id}")
                user = User(
                    user_id=qq_id,
                    nickname=nickname,
                    auth_provider="qq",
                    auth_id=qq_id
                )
                session.add(user)
            else:
                # Update info if needed
                if nickname and nickname != "User" and not user.nickname:
                    user.nickname = nickname
                # Ensure auth fields are set for legacy users
                if not user.auth_provider:
                    user.auth_provider = 'qq'
                    user.auth_id = qq_id
                
                session.add(user) # Mark for commit
            
            # Commit happens on exit of session_scope
        
        # 2. Create Session
        session_id = str(uuid.uuid4())
        # Store minimal info in session
        _sessions[session_id] = {
            "user_id": qq_id, # Using QQ ID as user_id for now
            "created_at": datetime.now().isoformat(),
            "provider": "qq"
        }
        
        # 3. Return Redirect with Cookie
        # We redirect to the home page or a 'login success' page
        redirect_url = f"{WEB_BASE_URL}/"
        resp = RedirectResponse(url=redirect_url)
        
        # Set simplified cookie (HTTPOnly)
        resp.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=30 * 24 * 60 * 60, # 30 days
            httponly=True,
            samesite="lax",
            secure=True # Should be True in Prod
        )
        
        return resp
        
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=400, content={"error": "Token has expired. Please request a new link."})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=400, content={"error": "Invalid token."})
    except Exception as e:
        logger.error(f"Login error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": "Internal Server Error during login."})

@router.get("/me")
async def get_current_user_info(request: Request):
    """Get current logged in user info."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id or session_id not in _sessions:
        return {"authenticated": False, "user": None}
        
    session_data = _sessions[session_id]
    user_id = session_data["user_id"]
    
    with session_scope() as session:
        user = session.get(User, user_id)
        if not user:
             return {"authenticated": False, "user": None}
             
        return {
            "authenticated": True,
            "user": {
                "user_id": user.user_id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "trust_score": user.trust_score
            }
        }

@router.post("/logout")
async def logout(response: Response):
    """Logout user."""
    resp = JSONResponse(content={"status": "logged_out"})
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp
