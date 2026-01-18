"""盘票站服务层 V2 - 结构化匹配."""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlmodel import Session, select, or_, and_

from services.db.models import MarketplaceListing, ListingItem, ItemDirection, TradeStatus, ItemType


class MarketplaceService:
    """盘票站服务，提供挂单和匹配操作."""
    
    def __init__(self, session: Session):
        """初始化服务.
        
        Args:
            session: SQLModel/SQLAlchemy Session
        """
        self.session = session
    
    def create_listing(
        self,
        user_id: str,
        items: List[Dict[str, Any]],
        description: str = "",
        requirements: Optional[str] = None,
        contact_info: Optional[str] = None,
        unbundling_allowed: bool = False,
    ) -> MarketplaceListing:
        """创建新挂单及其细项.
        
        Args:
            user_id: 发布者 ID
            items: 细项列表，每个元素包含:
                - direction: "have" or "want"
                - show_name: 剧目名称
                - show_time: 演出时间
                - price: 价格
                - quantity: 数量 (可选)
                - seat_info: 座位信息 (可选)
                - original_price: 票面原价 (可选)
                - play_id: 关联剧目 ID (可选)
            description: 描述
            requirements: 特殊要求
            contact_info: 联系方式 (隐藏字段)
            
        Returns:
            创建的 MarketplaceListing 对象
        """
        # 创建挂单
        listing = MarketplaceListing(
            user_id=user_id,
            status=TradeStatus.OPEN,
            description=description,
            requirements=requirements,
            contact_info=contact_info,
            unbundling_allowed=unbundling_allowed,
        )
        
        self.session.add(listing)
        self.session.flush()  # 获取 listing.id
        
        # 创建细项
        for item_data in items:
            item = ListingItem(
                listing_id=listing.id,
                direction=ItemDirection(item_data["direction"]),
                show_name=item_data.get("show_name"),
                show_time=item_data.get("show_time"),
                price=item_data.get("price", 0.0),
                quantity=item_data.get("quantity", 1),
                seat_info=item_data.get("seat_info"),
                original_price=item_data.get("original_price"),
                play_id=item_data.get("play_id"),
                inventory_id=item_data.get("inventory_id"),
                item_type=ItemType(item_data.get("item_type", ItemType.TICKET)),
            )
            self.session.add(item)
        
        self.session.commit()
        self.session.refresh(listing)
        
        return listing
    
    def get_listing(self, listing_id: int) -> Optional[MarketplaceListing]:
        """获取挂单详情（包含细项）.
        
        Args:
            listing_id: 挂单 ID
            
        Returns:
            MarketplaceListing 对象，如果不存在则返回 None
        """
        return self.session.get(MarketplaceListing, listing_id)
    
    def search_listings(
        self,
        status: Optional[TradeStatus] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[MarketplaceListing]:
        """搜索挂单.
        
        Args:
            status: 状态筛选
            user_id: 用户 ID 筛选
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            MarketplaceListing 列表
        """
        query = select(MarketplaceListing)
        
        if status:
            query = query.where(MarketplaceListing.status == status)
        if user_id:
            query = query.where(MarketplaceListing.user_id == user_id)
        
        # 按创建时间倒序排列
        query = query.order_by(MarketplaceListing.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        return list(self.session.exec(query).all())
    
    def search_items(
        self,
        direction: Optional[ItemDirection] = None,
        show_name: Optional[str] = None,
        status: Optional[TradeStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ListingItem]:
        """搜索挂单细项（用于匹配）.
        
        Args:
            direction: 方向筛选 (have/want)
            show_name: 剧目名称搜索 (模糊匹配)
            status: 挂单状态筛选
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            ListingItem 列表
        """
        query = select(ListingItem).join(MarketplaceListing)
        
        if direction:
            query = query.where(ListingItem.direction == direction)
        if show_name:
            query = query.where(ListingItem.show_name.contains(show_name))
        if status:
            query = query.where(MarketplaceListing.status == status)
        
        # 按创建时间倒序排列
        query = query.order_by(ListingItem.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        return list(self.session.exec(query).all())
    
    def find_matches(
        self,
        show_name: str,
        direction: ItemDirection,
        limit: int = 20
    ) -> List[ListingItem]:
        """查找匹配的细项.
        
        例如：我有"女巫"，想找谁想要"女巫"
        
        Args:
            show_name: 剧目名称
            direction: 要匹配的方向 (如果我有，则搜索 want)
            limit: 返回数量限制
            
        Returns:
            匹配的 ListingItem 列表
        """
        # 匹配相反方向
        target_direction = ItemDirection.WANT if direction == ItemDirection.HAVE else ItemDirection.HAVE
        
        query = select(ListingItem).join(MarketplaceListing).where(
            and_(
                ListingItem.direction == target_direction,
                ListingItem.show_name.contains(show_name),
                MarketplaceListing.status == TradeStatus.OPEN
            )
        )
        
        query = query.order_by(ListingItem.created_at.desc()).limit(limit)
        
        return list(self.session.exec(query).all())
    
    def update_listing_status(
        self,
        listing_id: int,
        status: TradeStatus,
    ) -> Optional[MarketplaceListing]:
        """更新挂单状态.
        
        Args:
            listing_id: 挂单 ID
            status: 新状态
            
        Returns:
            更新后的 MarketplaceListing 对象，如果不存在则返回 None
        """
        listing = self.get_listing(listing_id)
        if not listing:
            return None
        
        listing.status = status
        self.session.add(listing)
        self.session.commit()
        self.session.refresh(listing)
        
        return listing
    
    def delete_listing(self, listing_id: int) -> bool:
        """删除挂单（级联删除细项）.
        
        Args:
            listing_id: 挂单 ID
            
        Returns:
            成功返回 True，失败返回 False
        """
        listing = self.get_listing(listing_id)
        if not listing:
            return False
        
        # 由于设置了 cascade="all, delete-orphan"，删除 listing 会自动删除关联的 items
        self.session.delete(listing)
        self.session.commit()
        
        return True
