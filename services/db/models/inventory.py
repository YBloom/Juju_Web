"""用户票夹 (User Inventory) 模型."""

from enum import Enum
from typing import Optional, List
from datetime import datetime
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel
from .base import TimeStamped

class TicketSource(str, Enum):
    """票务来源."""
    MANUAL = "manual"       # 手动录入
    TRANSFERRED = "transferred" # 从他人处通过交易转入
    SYNCED = "synced"      # 从官方系统同步 (未来扩展)

class TicketStatus(str, Enum):
    """票务在票夹中的状态."""
    HOLDING = "holding"   # 持有中（闲置）
    LISTED = "listed"     # 已挂单（正在盘票站展示）
    TRADED = "traded"    # 已成交（已移出个人票夹）
    EXPIRED = "expired"   # 已过期

class UserInventory(TimeStamped, SQLModel, table=True):
    """用户票夹表.
    
    存储用户拥有的所有票务原件数据。
    """
    __tablename__ = "user_inventory"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", index=True)
    
    # 演出基本信息
    show_name: str = Field(max_length=256, index=True)
    show_time: datetime = Field(index=True)
    
    # 票务详情
    seat_info: Optional[str] = Field(default=None, max_length=128)
    original_price: Optional[float] = Field(default=None)
    
    # 管理状态
    status: TicketStatus = Field(default=TicketStatus.HOLDING, index=True)
    source: TicketSource = Field(default=TicketSource.MANUAL)
    
    # 溯源信息
    from_listing_id: Optional[int] = Field(default=None)  # 如果是转让来的，记录原挂单 ID
    
    # 流转路径 (JSON 数组存储 user_id 列表)
    # 例如: ["user001", "user002", "user003"] 表示这张票经过了三手
    # 第一个元素是原始录入者，最后一个元素是当前持有者
    transfer_path: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True)
    )
