from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CastInfo(BaseModel):
    name: str
    role: Optional[str] = None

class TicketInfo(BaseModel):
    id: str
    event_id: Optional[str] = None  # 添加event_id字段用于跳转
    title: str
    session_time: Optional[datetime] = None
    price: float = 0
    stock: int = 0
    total_ticket: int = 0
    city: Optional[str] = None
    cast: List[CastInfo] = []
    status: str = "active"
    valid_from: Optional[str] = None

class EventInfo(BaseModel):
    id: str
    title: str
    location: Optional[str]
    city: Optional[str] = None
    tickets: List[TicketInfo] = []
    update_time: Optional[datetime]
    total_stock: int = 0
    price_range: str = "待定"
    schedule_range: Optional[str] = None

class TicketUpdate(BaseModel):
    ticket_id: str
    event_id: str
    event_title: str
    change_type: str # new, restock, sold_out, etc.
    # new, restock, sold_out 等
    message: str # Pre-formatted short message for now
    # 目前为预格式化的短消息
    
    # 详细字段用于前端展示
    # Detailed fields for frontend display
    session_time: Optional[datetime] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    total_ticket: Optional[int] = None
    cast_names: Optional[List[str]] = None  # ["江东旭", "韦岸"]
    created_at: Optional[datetime] = None # detection time
    valid_from: Optional[str] = None # 开票时间
    
class SearchResult(BaseModel):
    events: List[EventInfo]
