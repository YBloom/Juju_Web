"""用户票夹服务层."""

from typing import List, Optional
from datetime import datetime

from sqlmodel import Session, select
from services.db.models import UserInventory, TicketStatus, TicketSource


class InventoryService:
    """用户票夹服务."""
    
    def __init__(self, session: Session):
        """初始化服务.
        
        Args:
            session: SQLModel/SQLAlchemy Session
        """
        self.session = session
    
    def add_ticket(
        self,
        user_id: str,
        show_name: str,
        show_time: datetime,
        seat_info: Optional[str] = None,
        original_price: Optional[float] = None,
        source: TicketSource = TicketSource.MANUAL,
    ) -> UserInventory:
        """添加票到用户票夹.
        
        Args:
            user_id: 用户 ID
            show_name: 剧目名称
            show_time: 演出时间
            seat_info: 座位信息
            original_price: 票面原价
            source: 票务来源
            
        Returns:
            创建的 UserInventory 对象
        """
        inventory = UserInventory(
            user_id=user_id,
            show_name=show_name,
            show_time=show_time,
            seat_info=seat_info,
            original_price=original_price,
            status=TicketStatus.HOLDING,
            source=source,
            transfer_path=[user_id]  # 初始化流转路径
        )
        
        self.session.add(inventory)
        self.session.commit()
        self.session.refresh(inventory)
        
        return inventory
    
    def get_user_inventory(
        self,
        user_id: str,
        status: Optional[TicketStatus] = None,
    ) -> List[UserInventory]:
        """获取用户的票夹.
        
        Args:
            user_id: 用户 ID
            status: 状态筛选
            
        Returns:
            UserInventory 列表
        """
        query = select(UserInventory).where(UserInventory.user_id == user_id)
        
        if status:
            query = query.where(UserInventory.status == status)
        
        query = query.order_by(UserInventory.show_time.asc())
        
        return list(self.session.exec(query).all())
    
    def transfer_ticket(
        self,
        inventory_id: int,
        from_user_id: str,
        to_user_id: str,
        listing_id: Optional[int] = None,
    ) -> UserInventory:
        """转让票务（成交后调用）.
        
        Args:
            inventory_id: 库存 ID
            from_user_id: 卖家 ID
            to_user_id: 买家 ID
            listing_id: 关联的挂单 ID
            
        Returns:
            买家的新库存记录
        """
        # 获取原库存
        original = self.session.get(UserInventory, inventory_id)
        if not original or original.user_id != from_user_id:
            raise ValueError("库存不存在或不属于该用户")
        
        # 更新卖家库存状态
        original.status = TicketStatus.TRADED
        self.session.add(original)
        
        # 创建买家库存（克隆数据）
        new_transfer_path = (original.transfer_path or []) + [to_user_id]
        
        new_inventory = UserInventory(
            user_id=to_user_id,
            show_name=original.show_name,
            show_time=original.show_time,
            seat_info=original.seat_info,
            original_price=original.original_price,
            status=TicketStatus.HOLDING,
            source=TicketSource.TRANSFERRED,
            from_listing_id=listing_id,
            transfer_path=new_transfer_path,
        )
        
        self.session.add(new_inventory)
        self.session.commit()
        self.session.refresh(new_inventory)
        
        return new_inventory
    
    def update_status(
        self,
        inventory_id: int,
        status: TicketStatus,
    ) -> Optional[UserInventory]:
        """更新库存状态.
        
        Args:
            inventory_id: 库存 ID
            status: 新状态
            
        Returns:
            更新后的 UserInventory，如果不存在则返回 None
        """
        inventory = self.session.get(UserInventory, inventory_id)
        if not inventory:
            return None
        
        inventory.status = status
        self.session.add(inventory)
        self.session.commit()
        self.session.refresh(inventory)
        
        return inventory
