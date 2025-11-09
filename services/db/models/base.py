# services/db/models/base.py
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import SQLModel, Field

class TimeStamped(SQLModel, table=False):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SoftDelete(SQLModel, table=False):
    is_deleted: bool = Field(default=False)

# 业务枚举
class GroupType(str, Enum):
    BROADCAST = "broadcast"     # 广播群
    FILTERED  = "filtered"      # 过滤群
    PASSIVE   = "passive"       # 入驻/被动群
    TOOL      = "tool"

class ListingType(str, Enum):
    SELL = "sell"
    BUY  = "buy"
    EXCHANGE = "exchange"
