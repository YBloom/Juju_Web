"""
User Settings API Router
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime

from services.db.connection import get_engine
from services.db.models import User, UserAuthMethod
from web.dependencies import get_current_user
import os

router = APIRouter(prefix="/api/user", tags=["user"])



# --- Dependencies ---

def get_session():
    """FastAPI dependency for database session"""
    engine = get_engine()
    with Session(engine) as session:
        yield session

def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# --- Models ---

class UserSettingsUpdate(BaseModel):
    bot_interaction_mode: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None  # New field

class UserSettingsResponse(BaseModel):
    user_id: str
    nickname: Optional[str]
    email: Optional[str] = None
    avatar_url: Optional[str]
    bot_interaction_mode: str

class AuthMethodResponse(BaseModel):
    """认证方式响应模型"""
    provider: str
    provider_user_id: str
    is_primary: bool
    created_at: str

@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    user_session: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """Get user settings"""
    uid = user_session.get("user_id") or user_session.get("qq_id")
    if not uid:
         raise HTTPException(status_code=400, detail="Invalid session state")

    db_user = session.get(User, uid)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserSettingsResponse(
        user_id=db_user.user_id,
        nickname=db_user.nickname,
        email=db_user.email,
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
        
    if data.bot_interaction_mode:
        if data.bot_interaction_mode not in ["hybrid", "lite", "legacy", "full"]:
             raise HTTPException(status_code=400, detail="Invalid mode")
        db_user.bot_interaction_mode = data.bot_interaction_mode
    
    if data.nickname is not None:
        clean_name = data.nickname.strip()
        if len(clean_name) > 32:
             raise HTTPException(status_code=400, detail="Nickname too long")
        db_user.nickname = clean_name
        
    if data.avatar_url is not None:
        # S3 Cleanup - Delete old avatar if it was an S3 file
        old_url = db_user.avatar_url
        bucket_name = os.getenv("AWS_BUCKET_NAME")
        
        # Check if old_url exists, is different, and belongs to our S3 bucket
        if old_url and old_url != data.avatar_url and bucket_name and bucket_name in old_url:
            try:
                import boto3
                
                # Extract Key from URL
                # Example: https://bucket.s3.region.amazonaws.com/avatars/key.webp
                # Split by bucket name to be safe
                if f"https://{bucket_name}.s3" in old_url:
                     key = old_url.split(".amazonaws.com/")[-1]
                     
                     s3 = boto3.client(
                        's3',
                        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                        region_name=os.getenv("AWS_REGION", "us-east-1")
                     )
                     s3.delete_object(Bucket=bucket_name, Key=key)
                     print(f"Deleted old avatar: {key}")
            except Exception as e:
                print(f"Failed to delete old avatar: {e}")
                
        db_user.avatar_url = data.avatar_url

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    return UserSettingsResponse(
        user_id=db_user.user_id,
        nickname=db_user.nickname,
        email=db_user.email,
        avatar_url=db_user.avatar_url,
        bot_interaction_mode=db_user.bot_interaction_mode or "hybrid"
    )


@router.get("/auth-methods")
async def get_auth_methods(
    user_session: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """获取当前用户绑定的所有认证方式"""
    uid = user_session.get("user_id") or user_session.get("qq_id")
    if not uid:
        raise HTTPException(status_code=400, detail="Invalid session state")
    
    # 查询该用户的所有认证方式
    stmt = select(UserAuthMethod).where(UserAuthMethod.user_id == uid)
    auth_methods = session.exec(stmt).all()
    
    result = []
    for auth in auth_methods:
        result.append({
            "provider": auth.provider,
            "provider_user_id": auth.provider_user_id if auth.provider == "email" else "***" + auth.provider_user_id[-4:],  # QQ号脱敏
            "is_primary": auth.is_primary,
            "created_at": auth.created_at.isoformat() if hasattr(auth, 'created_at') else None
        })
    
    return {"auth_methods": result}
