from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CastInfo(BaseModel):
    name: str
    role: Optional[str] = None

class TicketInfo(BaseModel):
    id: str
    title: str
    session_time: Optional[datetime]
    price: float
    stock: int
    total_ticket: int
    city: Optional[str]
    cast: List[CastInfo] = []
    status: str
    valid_from: Optional[str]

class EventInfo(BaseModel):
    id: str
    title: str
    location: Optional[str]
    tickets: List[TicketInfo] = []
    update_time: Optional[datetime]

class TicketUpdate(BaseModel):
    ticket_id: str
    event_id: str
    event_title: str
    change_type: str # new, restock, sold_out, etc.
    # new, restock, sold_out 等
    message: str # Pre-formatted short message for now
    # 目前为预格式化的短消息
    
class SearchResult(BaseModel):
    events: List[EventInfo]
