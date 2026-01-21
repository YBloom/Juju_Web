"""盘票站 (Ticket Marketplace) 数据模型 V2 - 结构化匹配."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import JSON, Column
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import Field, Relationship, SQLModel

from .base import TimeStamped, TradeStatus


class ItemDirection(str, Enum):
    """挂单细项方向."""
    HAVE = "have"  # 持有 (我有)
    WANT = "want"  # 期待 (我想要)


class ItemType(str, Enum):
    """细项类型."""
    TICKET = "ticket"        # 演出票
    CASH = "cash"           # 现金


class MarketplaceListing(TimeStamped, SQLModel, table=True):
    """盘票挂单表.
    
    代表用户的一次发布行为，可以包含多个细项（票务）。
    """
    
    __tablename__ = "marketplace_listing"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", index=True)
    
    # 挂单状态
    status: TradeStatus = Field(default=TradeStatus.OPEN, index=True)
    
    # 文本描述字段
    description: str = Field(default="", max_length=1024)  # 自由文本备注
    requirements: Optional[str] = Field(default=None, max_length=512)  # 特殊要求 (如：回收抽卡、需拍立得)
    
    # 捆绑设置
    unbundling_allowed: bool = Field(default=False)  # 是否允许拆分捆绑 (默认为 False，即必须打包)
    
    # 联系方式 (隐藏字段)
    contact_info: Optional[str] = Field(default=None, max_length=256)
    
    # 关系
    items: Mapped[List["ListingItem"]] = Relationship(
        back_populates="listing",
        sa_relationship=relationship("ListingItem", back_populates="listing", cascade="all, delete-orphan"),
    )


class ListingItem(TimeStamped, SQLModel, table=True):
    """挂单细项表.
    
    代表挂单中的具体一场演出/票务。
    用于结构化匹配和订阅。
    """
    
    __tablename__ = "listing_item"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketplace_listing.id", index=True)
    
    # 关联库存 (如果是 HAVE 类型，建议关联)
    inventory_id: Optional[int] = Field(default=None, foreign_key="user_inventory.id", index=True)

    # 方向：持有 or 想要
    direction: ItemDirection = Field(index=True)
    
    # 类型：票务 or 现金
    item_type: ItemType = Field(default=ItemType.TICKET, index=True)
    
    # 演出信息
    play_id: Optional[int] = Field(default=None, foreign_key="play.id", index=True)
    show_name: Optional[str] = Field(default=None, max_length=256, index=True)  # 剧目名称
    show_time: Optional[datetime] = Field(default=None, index=True)  # 演出时间
    
    # 价格信息
    price: float = Field(default=0.0)  # 价格 (WANT 模式下为期望价格)
    original_price: Optional[float] = Field(default=None)  # 票面原价
    
    # 票务详情
    quantity: int = Field(default=1)  # 数量
    seat_info: Optional[str] = Field(default=None, max_length=128)  # 座位信息
    
    # 关系
    listing: Mapped["MarketplaceListing"] = Relationship(
        back_populates="items",
        sa_relationship=relationship("MarketplaceListing", back_populates="items"),
    )
