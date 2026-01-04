from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from services.utils.timezone import now as timezone_now

class TicketCastAssociation(SQLModel, table=True):
    ticket_id: str = Field(foreign_key="hulaquanticket.id", primary_key=True)
    cast_id: int = Field(foreign_key="hulaquancast.id", primary_key=True)
    role: Optional[str] = None  # e.g. "本杰明·巴顿"
    # 例如 "本杰明·巴顿"

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
    
    status: str = "active" # active, sold_out, pending
    valid_from: Optional[str] = None # "11-01 12:00"
    
    event: Optional[HulaquanEvent] = Relationship(back_populates="tickets")
    cast_members: List["HulaquanCast"] = Relationship(back_populates="tickets", link_model=TicketCastAssociation)

class HulaquanCast(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True) # e.g. "王培杰"
    # 例如 "王培杰"
    tickets: List[HulaquanTicket] = Relationship(back_populates="cast_members", link_model=TicketCastAssociation)

class HulaquanSubscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True) # User or Group ID
    # 用户或群组 ID
    target_id: str # event_id or cast_name
    # event_id 或 cast_name
    target_type: str = "event" # "event", "cast", "ticket", "global"
    mode: int = 1 # 1: basic, 2: return, 3: back/sold
    # 1: 基础, 2: 回流, 3: 票增/售罄
    created_at: datetime = Field(default_factory=timezone_now)

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

