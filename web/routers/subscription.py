"""
订阅管理 API Router
提供用户订阅的 CRUD 操作
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime

from services.db.connection import get_engine
from services.db.models import Subscription, SubscriptionTarget, SubscriptionOption
from services.db.models.base import SubscriptionTargetKind, SubscriptionFrequency
from web.dependencies import get_current_user

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


# --- Database Session Dependency ---

def get_session():
    """FastAPI dependency for database session"""
    engine = get_engine()
    with Session(engine) as session:
        yield session



# --- Pydantic Models for Request/Response ---

class SubscriptionTargetCreate(BaseModel):
    """创建订阅目标的请求模型"""
    kind: SubscriptionTargetKind
    target_id: Optional[str] = None
    name: Optional[str] = None
    city_filter: Optional[str] = None
    flags: Optional[dict] = None


class SubscriptionOptionCreate(BaseModel):
    """创建订阅选项的请求模型"""
    mute: bool = False
    freq: SubscriptionFrequency = SubscriptionFrequency.REALTIME
    allow_broadcast: bool = True
    notification_level: int = 2


class SubscriptionCreate(BaseModel):
    """创建订阅的请求模型"""
    targets: List[SubscriptionTargetCreate]
    options: Optional[SubscriptionOptionCreate] = None


class SubscriptionTargetResponse(BaseModel):
    """订阅目标的响应模型"""
    id: int
    kind: str
    target_id: Optional[str]
    name: Optional[str]
    city_filter: Optional[str]
    include_plays: Optional[List[str]]
    exclude_plays: Optional[List[str]]
    flags: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionOptionResponse(BaseModel):
    """订阅选项的响应模型"""
    id: int
    mute: bool
    freq: str
    allow_broadcast: bool
    notification_level: int
    last_notified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """订阅的响应模型"""
    id: int
    user_id: str
    targets: List[SubscriptionTargetResponse]
    options: Optional[SubscriptionOptionResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Auth Dependency ---




def require_auth(request: Request) -> dict:
    """要求用户必须登录"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


# --- API Endpoints ---

@router.get("", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    request: Request,
    user: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """
    获取当前用户的所有订阅
    """
    user_id = user.get("user_id") or user.get("qq_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="无效的用户信息")
    
    # 查询用户的所有订阅
    statement = select(Subscription).where(Subscription.user_id == user_id)
    subscriptions = session.exec(statement).all()
    
    # 手动加载关系（eager loading）
    results = []
    for sub in subscriptions:
        # 加载 targets
        targets_stmt = select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)
        targets = session.exec(targets_stmt).all()
        
        # 加载 options
        options_stmt = select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)
        options = session.exec(options_stmt).first()
        
        results.append(SubscriptionResponse(
            id=sub.id,
            user_id=sub.user_id,
            targets=[SubscriptionTargetResponse.model_validate(t) for t in targets],
            options=SubscriptionOptionResponse.model_validate(options) if options else None,
            created_at=sub.created_at,
            updated_at=sub.updated_at
        ))
    
    return results


@router.post("", response_model=SubscriptionResponse)
async def create_subscription(
    data: SubscriptionCreate,
    request: Request,
    user: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """
    创建新订阅
    """
    user_id = user.get("user_id") or user.get("qq_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="无效的用户信息")
    
    if not data.targets:
        raise HTTPException(status_code=400, detail="至少需要一个订阅目标")
    
    # 检查是否已存在 Subscription
    statement = select(Subscription).where(Subscription.user_id == user_id)
    subscription = session.exec(statement).first()
    
    if not subscription:
        subscription = Subscription(user_id=user_id)
        session.add(subscription)
        session.flush()  # 获取 subscription.id
    
    # 创建 SubscriptionTargets
    for target_data in data.targets:
        target = SubscriptionTarget(
            subscription_id=subscription.id,
            kind=target_data.kind,
            target_id=target_data.target_id,
            name=target_data.name,
            city_filter=target_data.city_filter,
            flags=target_data.flags
        )
        session.add(target)
    
    # 创建 SubscriptionOption
    if data.options:
        option = SubscriptionOption(
            subscription_id=subscription.id,
            mute=data.options.mute,
            freq=data.options.freq,
            allow_broadcast=data.options.allow_broadcast
        )
        session.add(option)
    else:
        # 默认选项
        option = SubscriptionOption(
            subscription_id=subscription.id,
            mute=False,
            freq=SubscriptionFrequency.REALTIME,
            allow_broadcast=True
        )
        session.add(option)
    
    session.commit()
    session.refresh(subscription)
    
    # 重新加载以包含关系
    targets = session.exec(
        select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == subscription.id)
    ).all()
    options = session.exec(
        select(SubscriptionOption).where(SubscriptionOption.subscription_id == subscription.id)
    ).first()
    
    return SubscriptionResponse(
        id=subscription.id,
        user_id=subscription.user_id,
        targets=[SubscriptionTargetResponse.model_validate(t) for t in targets],
        options=SubscriptionOptionResponse.model_validate(options) if options else None,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at
    )


@router.delete("/{subscription_id}")
async def delete_subscription(
    subscription_id: int,
    request: Request,
    user: dict = Depends(require_auth),
    session: Session = Depends(get_session)
):
    """
    删除订阅
    """
    user_id = user.get("user_id") or user.get("qq_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="无效的用户信息")
    
    # 查找订阅
    subscription = session.get(Subscription, subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="订阅不存在")
    
    # 验证所有权
    if subscription.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权删除此订阅")
    
    # 删除关联的 targets 和 options（如果有级联删除配置会自动处理，否则手动删除）
    targets = session.exec(
        select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == subscription_id)
    ).all()
    for target in targets:
        session.delete(target)
    
    options = session.exec(
        select(SubscriptionOption).where(SubscriptionOption.subscription_id == subscription_id)
    ).first()
    if options:
        session.delete(options)
    
    # 删除订阅本身
    session.delete(subscription)
    session.commit()
    
    return {"status": "ok", "message": "订阅已删除"}



@router.patch("/options/{subscription_id}")
async def update_subscription_options(
    subscription_id: int,
    options: SubscriptionOptionCreate,
    db: Session = Depends(get_session),
    user: dict = Depends(get_current_user)
):
    """更新订阅选项"""
    stmt = select(SubscriptionOption).where(SubscriptionOption.subscription_id == subscription_id)
    db_options = db.exec(stmt).first()
    if not db_options:
        raise HTTPException(status_code=404, detail="Options not found")
        
    for key, value in options.dict().items():
        setattr(db_options, key, value)
    
    db.add(db_options)
    db.commit()
    return db_options

@router.patch("/global-level")
async def update_global_level(
    level: int,
    db: Session = Depends(get_session),
    user: dict = Depends(get_current_user)
):
    """更新全局推送级别"""
    from services.db.models import User
    user_id = user.get("user_id") or user.get("qq_id")
    db_user = db.get(User, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.global_notification_level = level
    db.add(db_user)
    db.commit()
    return {"status": "ok", "level": level}
