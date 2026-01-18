"""盘票站 (Marketplace) API 路由 V2 - 结构化匹配."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from datetime import datetime

from services.db.connection import session_scope
from services.db.models import MarketplaceListing, ListingItem, ItemDirection, TradeStatus, ItemType
from services.marketplace.service import MarketplaceService

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


# Pydantic 模型用于请求验证
class ListingItemCreate(BaseModel):
    """创建细项请求模型."""
    direction: ItemDirection  # have or want
    show_name: Optional[str] = None
    show_time: Optional[datetime] = None
    price: float = 0.0
    quantity: int = 1
    seat_info: Optional[str] = None
    original_price: Optional[float] = None
    play_id: Optional[int] = None
    inventory_id: Optional[int] = None
    item_type: ItemType = ItemType.TICKET


class ListingCreateRequest(BaseModel):
    """创建挂单请求模型."""
    items: List[ListingItemCreate]  # 至少一个细项
    description: str = ""
    requirements: Optional[str] = None  # 特殊要求
    contact_info: Optional[str] = None
    unbundling_allowed: bool = False


class ListingUpdateStatusRequest(BaseModel):
    """更新挂单状态请求模型."""
    status: TradeStatus


def get_current_user_from_request(request: Request):
    """从请求中获取当前用户（依赖注入）."""
    from web_app import get_current_user
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    return user


@router.post("/listings")
async def create_listing(
    listing_data: ListingCreateRequest,
    request: Request,
    user: dict = Depends(get_current_user_from_request)
):
    """创建新的挂单.
    
    需要登录。支持：
    - 简单出/求：提供一个 HAVE 或 WANT 细项
    - 置换：提供一个 HAVE + 一个 WANT
    - 捆绑：提供多个 HAVE
    """
    if not listing_data.items:
        raise HTTPException(status_code=400, detail="至少需要一个细项")
    
    with session_scope() as session:
        service = MarketplaceService(session)
        
        # 转换 items
        items_data = [item.model_dump() for item in listing_data.items]
        
        listing = service.create_listing(
            user_id=user["user_id"],
            items=items_data,
            description=listing_data.description,
            requirements=listing_data.requirements,
            contact_info=listing_data.contact_info,
        )
        
        return {
            "status": "ok",
            "listing_id": listing.id,
            "message": "挂单创建成功"
        }


@router.get("/listings")
async def search_listings(
    status: Optional[TradeStatus] = None,
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """搜索挂单.
    
    所有人都可以搜索，无需登录。
    联系方式字段会被隐藏。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        
        listings = service.search_listings(
            status=status,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        
        # 转换为字典并隐藏联系方式
        results = []
        for listing in listings:
            listing_dict = listing.model_dump(mode='json')
            # 隐藏联系方式
            has_contact = bool(listing_dict.get("contact_info"))
            listing_dict["contact_info"] = None
            listing_dict["has_contact"] = has_contact
            results.append(listing_dict)
        
        return {
            "results": results,
            "count": len(results)
        }


@router.get("/items")
async def search_items(
    direction: Optional[ItemDirection] = None,
    show_name: Optional[str] = None,
    status: Optional[TradeStatus] = None,
    limit: int = 50,
    offset: int = 0,
):
    """搜索挂单细项.
    
    用于结构化匹配，可按方向、剧目名称筛选。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        
        items = service.search_items(
            direction=direction,
            show_name=show_name,
            status=status,
            limit=limit,
            offset=offset,
        )
        
        return {
            "results": [item.model_dump(mode='json') for item in items],
            "count": len(items)
        }


@router.get("/listings/{listing_id}")
async def get_listing_detail(
    listing_id: int,
    request: Request,
    reveal_contact: bool = False
):
    """获取挂单详情（包含所有细项）.
    
    如果 reveal_contact=True，则需要登录才能查看联系方式。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        listing = service.get_listing(listing_id)
        
        if not listing:
            raise HTTPException(status_code=404, detail="挂单不存在")
        
        listing_dict = listing.model_dump(mode='json')
        
        # 处理联系方式显示
        if reveal_contact:
            from web_app import get_current_user
            user = get_current_user(request)
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="需要登录才能查看联系方式"
                )
            listing_dict["has_contact"] = bool(listing.contact_info)
        else:
            has_contact = bool(listing.contact_info)
            listing_dict["contact_info"] = None
            listing_dict["has_contact"] = has_contact
        
        return listing_dict


@router.get("/match")
async def find_matches(
    show_name: str,
    direction: ItemDirection,
    limit: int = 20
):
    """智能匹配.
    
    例如：我有"女巫"，查找谁想要"女巫"。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        
        matches = service.find_matches(
            show_name=show_name,
            direction=direction,
            limit=limit
        )
        
        return {
            "results": [item.model_dump(mode='json') for item in matches],
            "count": len(matches)
        }


@router.patch("/listings/{listing_id}/status")
async def update_listing_status(
    listing_id: int,
    status_data: ListingUpdateStatusRequest,
    user: dict = Depends(get_current_user_from_request)
):
    """更新挂单状态.
    
    只有挂单发布者本人可以更新状态。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        listing = service.get_listing(listing_id)
        
        if not listing:
            raise HTTPException(status_code=404, detail="挂单不存在")
        
        # 验证是否是挂单发布者
        if listing.user_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="只能修改自己发布的挂单")
        
        updated_listing = service.update_listing_status(listing_id, status_data.status)
        
        return {
            "status": "ok",
            "listing": updated_listing.model_dump(mode='json'),
            "message": "状态更新成功"
        }


@router.delete("/listings/{listing_id}")
async def delete_listing(
    listing_id: int,
    user: dict = Depends(get_current_user_from_request)
):
    """删除挂单（级联删除所有细项）.
    
    只有挂单发布者本人可以删除。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        listing = service.get_listing(listing_id)
        
        if not listing:
            raise HTTPException(status_code=404, detail="挂单不存在")
        
        # 验证是否是挂单发布者
        if listing.user_id != user["user_id"]:
            raise HTTPException(status_code=403, detail="只能删除自己发布的挂单")
        
        success = service.delete_listing(listing_id)
        
        if success:
            return {"status": "ok", "message": "删除成功"}
        else:
            raise HTTPException(status_code=500, detail="删除失败")


@router.get("/listings/my")
async def get_my_listings(
    user: dict = Depends(get_current_user_from_request),
    limit: int = 50,
    offset: int = 0,
):
    """获取当前用户发布的所有挂单.
    
    需要登录。
    """
    with session_scope() as session:
        service = MarketplaceService(session)
        
        listings = service.search_listings(
            user_id=user["user_id"],
            limit=limit,
            offset=offset,
        )
        
        return {
            "results": [listing.model_dump(mode='json') for listing in listings],
            "count": len(listings)
        }
