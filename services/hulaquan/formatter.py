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
        if event.schedule_range:
            header += f"\n排期: {event.schedule_range}"
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

    @staticmethod
    def format_co_casts(results: List[Dict], limit: int = 5, show_link: str = None) -> str:
        """Format co-cast search results."""
        if not results:
            return "👥 未找到同场演出信息。"
            
        lines = [f"👥 找到 {len(results)} 场同台演出:"]
        
        # Filter future only for concise list? Or just list all?
        # User request: "Default generate from now to future"
        # The logic for filtering should be in Service or Handler, here we format what we get.
        
        count = 0
        for item in results:
            if count >= limit:
                break
                
            date_str = item.get("date", "未知日期")
            title = item.get("title", "未知剧目")
            city = item.get("city", "")
            city_str = f"[{city}]" if city else ""
            
            # Format: 1. 02月14日 星期五 19:30 《粉丝来信》 [上海]
            lines.append(f"{count+1}. {date_str} 《{title}》{city_str}")
            count += 1
            
        if len(results) > limit:
            lines.append(f"...等 {len(results)} 场 (仅显示前 {limit} 场)")
            
        if show_link:
            lines.append(f"\n🔗 网页快速筛选: {show_link}")
            
        return "\n".join(lines)
