from typing import List, Dict
from datetime import datetime
from .models import TicketInfo, EventInfo, TicketUpdate

class HulaquanFormatter:
    """Format Hulaquan data for bot messages with improved clarity."""
    
    @staticmethod
    def format_ticket_detail(ticket: TicketInfo, show_id=False) -> str:
        # Essential status only
        if ticket.status == "pending":
            status_icon = "⏱"
        elif ticket.stock > 0:
            status_icon = "●" # Active/Stock available
        else:
            status_icon = "○" # Sold out
            
        cast_str = " ".join([f"{c.name}" for c in ticket.cast])
        if cast_str:
            cast_str = f" | {cast_str}"
            
        tid_str = f" [ID:{ticket.id}]" if show_id else ""
        city_str = f"[{ticket.city}]" if ticket.city else ""
        
        time_info = ""
        if ticket.status == "pending" and ticket.valid_from:
            time_info = f"\n   开票: {ticket.valid_from}"
            
        return (
            f"{status_icon} {city_str}{ticket.title}\n"
            f"   余票: {ticket.stock}/{ticket.total_ticket} | ￥{ticket.price}{cast_str}{tid_str}{time_info}"
        )

    @staticmethod
    def format_event_search_result(event: EventInfo, show_id=False) -> str:
        header = f"--- {event.title} ---"
        lines = [header]
        if event.location:
            lines.append(f"地点: {event.location}")
        
        sorted_tickets = sorted(event.tickets, key=lambda x: x.session_time or datetime.max)
        active_tickets = [t for t in sorted_tickets if t.status != "expired"]
        for t in active_tickets[:12]: 
            lines.append(HulaquanFormatter.format_ticket_detail(t, show_id))
            
        if len(active_tickets) > 12:
            lines.append(f"\n...等 {len(active_tickets)} 个场次")
            
        return "\n".join(lines)

    @staticmethod
    def format_updates_announcement(updates: List[TicketUpdate]) -> List[str]:
        if not updates:
            return []
            
        grouped: Dict[str, List[TicketUpdate]] = {}
        for u in updates:
            grouped.setdefault(u.event_id, []).append(u)
            
        messages = []
        for eid, event_updates in grouped.items():
            event_title = event_updates[0].event_title
            lines = [f"[呼啦圈动态] {event_title}\n"]
            for u in event_updates:
                # Remove emojis from sub-messages if any (u.message might have them from service sync)
                # But u.message is generated in HulaquanService._sync_event_details, let's clean it there too or just accept it.
                # For now, keep as is but minimize formatter's additions.
                lines.append(f"  {u.message}")
            lines.append(f"\n查询详情请回复: /hlq {event_title}")
            messages.append("\n".join(lines))
            
        return messages

    @staticmethod
    def format_date_events(date: datetime, tickets: List[TicketInfo]) -> str:
        date_str = date.strftime("%Y-%m-%d")
        lines = [f"📅 {date_str} 演出信息：\n"]
        if not tickets:
            lines.append("😴 暂无学生票演出安排")
            return "\n".join(lines)
            
        for t in tickets:
            lines.append(HulaquanFormatter.format_ticket_detail(t))
            
        return "\n".join(lines)
