from typing import Optional, List
from enum import Enum
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from services.utils.timezone import now as timezone_now


class TicketStatus(str, Enum):
    ACTIVE = "active"
    SOLD_OUT = "sold_out"
    PENDING = "pending"
    EXPIRED = "expired"

class TicketCastAssociation(SQLModel, table=True):
    ticket_id: str = Field(foreign_key="hulaquanticket.id", primary_key=True)
    cast_id: int = Field(foreign_key="hulaquancast.id", primary_key=True)
    role: Optional[str] = None  # e.g. "陆光"
    # 例如 "陆光"
    rank: int = Field(default=999)  # 角色排序序号，越小越靠前
    # 角色排序序号，越小越靠前

class HulaquanEvent(SQLModel, table=True):
    id: str = Field(primary_key=True) # e.g. "3911"
    # 例如 "3911"
    title: str = Field(index=True)
    location: Optional[str] = None
    poster_url: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    update_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=timezone_now)
    updated_at: datetime = Field(default_factory=timezone_now)
    
    # Saoju Mapping
    saoju_musical_id: Optional[str] = Field(default=None, index=True)
    last_synced_at: Optional[datetime] = None

    tickets: List["HulaquanTicket"] = Relationship(back_populates="event")

class HulaquanTicket(SQLModel, table=True):
    id: str = Field(primary_key=True) # e.g. "34865"
    # 例如 "34865"
    event_id: str = Field(foreign_key="hulaquanevent.id", index=True)
    
    title: str # Original full title line
    # 原始完整标题行
    session_time: Optional[datetime] = None # Parsed from start_time
    # 从 start_time 解析
    price: float = 0
    stock: int = 0
    total_ticket: int = 0
    city: Optional[str] = None
    
    status: str = Field(default="active") # active, sold_out, pending

    valid_from: Optional[str] = None # "11-01 12:00"
    
    event: Optional[HulaquanEvent] = Relationship(back_populates="tickets")
    cast_members: List["HulaquanCast"] = Relationship(back_populates="tickets", link_model=TicketCastAssociation)

class HulaquanCast(SQLModel, table=True):
    id: int = Field(primary_key=True)
    name: str = Field(index=True) # e.g. "丁辰西"
    # 例如 "丁辰西"
    tickets: List[HulaquanTicket] = Relationship(back_populates="cast_members", link_model=TicketCastAssociation)



class HulaquanAlias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    alias: str = Field(index=True, unique=True)
    event_id: Optional[str] = None
    search_names: Optional[str] = None # Comma separated
    # 逗号分隔
    no_response_times: int = 0

class SaojuCache(SQLModel, table=True):
    key: str = Field(primary_key=True)
    data: str # Stores JSON string
    updated_at: datetime = Field(default_factory=timezone_now)


class SaojuShow(SQLModel, table=True):
    date: datetime = Field(primary_key=True)
    musical_name: str = Field(primary_key=True)
    city: str = Field(index=True)
    cast_str: Optional[str] = None # "A / B / C"
    theatre: Optional[str] = None
    tour_name: Optional[str] = None
    source: str = "api_unknown" # "csv_history", "api_daily", "api_tour"
    updated_at: datetime = Field(default_factory=timezone_now)


class SaojuChangeLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    detected_at: datetime = Field(default_factory=timezone_now)
    show_date: datetime
    musical_name: str
    change_type: str # "NEW", "UPDATE"
    details: str # JSON or text summary


class HulaquanSearchLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=timezone_now)
    search_type: str # "co-cast", "view_event"
    query_str: str # Raw input or Event Title
    artists: Optional[str] = None # JSON list or null
    is_combination: bool = False



class Feedback(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=timezone_now)
    type: str # "bug", "suggestion", "wish"
    content: str
    contact: Optional[str] = None
    status: str = "open" # "open", "closed"
    
    # Roadmap / Feedback Wall Columns
    is_public: bool = Field(default=False)
    admin_reply: Optional[str] = None
    reply_at: Optional[datetime] = None
    
    # Ignore Management
    is_ignored: bool = Field(default=False)
    ignored_at: Optional[datetime] = None


class TicketUpdateLog(SQLModel, table=True):
    """票务更新日志表，用于持久化和展示票务动态"""
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: str = Field(index=True)
    event_id: str = Field(index=True)
    event_title: str
    change_type: str  # new, restock, back, pending
    message: str
    
    # 详细字段用于前端展示
    # Detailed fields for frontend display
    session_time: Optional[datetime] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    total_ticket: Optional[int] = None
    cast_names: Optional[str] = None  # JSON string: ["江东旭", "韦岸"]
    valid_from: Optional[str] = None
    
    created_at: datetime = Field(default_factory=timezone_now, index=True)
