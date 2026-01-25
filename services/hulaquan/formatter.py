"""
HulaquanFormatter - 呼啦圈数据格式化（匹配旧版输出格式）
"""
from typing import List, Dict, Optional
from datetime import datetime
from .models import TicketInfo, EventInfo, TicketUpdate
from .utils import extract_text_in_brackets

# Web 链接配置
import os
import urllib.parse
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")
# Official Ticket Link
HLQ_OFFICIAL_URL_TEMPLATE = "https://clubz.cloudsation.com/event/{event_id}.html"
# Web App Link
WEB_DETAIL_URL_TEMPLATE = "{base_url}/#/detail/{event_id}"
WEB_DATE_URL_TEMPLATE = "{base_url}/#/date?d={date_str}"
WEB_CAST_URL_TEMPLATE = "{base_url}/?tab=cocast&actors={actors}"


class HulaquanFormatter:
    """Format Hulaquan data for bot messages - 旧版兼容格式"""
    
    @staticmethod
    def _format_ticket_line(ticket: TicketInfo, show_title: bool = True) -> str:
        """
        格式化单条票务信息（旧版格式）
        示例: ✨《雕像》01-17 19:30 ￥199 学生票 余票5/30 于滨嘉 琚茂林
        """
        # 状态图标
        if ticket.status == "pending":
            icon = "⏲️"  # 待开票
        elif ticket.stock > 0:
            icon = "✨"  # 有票
        else:
            icon = "❌"  # 售罄
        
        # 识别冗余信息：如果 title 已经包含了日期、时间或价格，则不再重复显示
        title_val = ticket.title
        
        # 处理书名号：强制提取《》内部内容，去除营销文案
        clean_title = title_val.strip()
        if show_title:
            title_str = extract_text_in_brackets(clean_title, keep_brackets=True)
        else:
            title_str = ""

        # 检查价格冗余
        price_in_title = f"{int(ticket.price)}" in title_val or f"{ticket.price:.1f}" in title_val or f"￥{int(ticket.price)}" in title_val
        if price_in_title:
            price_str = ""
        else:
            # 价格（含原价）
            if hasattr(ticket, 'original_price') and ticket.original_price and ticket.original_price != ticket.price:
                price_str = f" ￥{int(ticket.price)}(原价：￥{int(ticket.original_price)})"
            else:
                price_str = f" ￥{int(ticket.price)}"

        # 检查时间冗余 (MM-DD HH:MM)
        date_in_title = False
        if ticket.session_time and show_title:
            short_date = ticket.session_time.strftime("%m-%d")
            short_time = ticket.session_time.strftime("%H:%M")
            if short_date in title_val and short_time in title_val:
                date_in_title = True
        
        if date_in_title:
            date_str = ""
        else:
            # 日期时间
            if ticket.session_time:
                date_str = " " + ticket.session_time.strftime("%m-%d %H:%M")
            else:
                date_str = " 日期未知"

        # 卡司
        if ticket.cast:
            if isinstance(ticket.cast[0], str):
                cast_str = " ".join(ticket.cast)
            else:
                cast_str = " ".join([c.name for c in ticket.cast if hasattr(c, 'name')])
        else:
            cast_str = "无卡司信息"

        # 检查是否已包含“学生票”
        type_str = "" if "学生票" in title_val else " 学生票"

        # 拼接行，注意处理空格
        parts = [icon, title_str]
        if date_str: parts.append(date_str)
        if price_str: parts.append(price_str)
        parts.append(f"{type_str} 余票{ticket.stock}/{ticket.total_ticket} {cast_str}")
        
        return "".join(parts).replace("  ", " ").strip()

    @staticmethod
    def format_ticket_detail(ticket: TicketInfo, show_id: bool = False) -> str:
        """兼容旧接口"""
        line = HulaquanFormatter._format_ticket_line(ticket, show_title=True)
        if show_id:
            line += f" [ID:{ticket.id}]"
        return line

    @staticmethod
    def format_event_search_result(event: EventInfo, show_id: bool = False, show_all: bool = False) -> str:
        """
        格式化剧目搜索结果（/hlq 命令）- 旧版格式
        """
        lines = []
        
        # 标题
        lines.append(f"剧名: {event.title}")
        
        # 购票链接
        if event.id:
            official_url = HLQ_OFFICIAL_URL_TEMPLATE.format(event_id=event.id)
            web_url = WEB_DETAIL_URL_TEMPLATE.format(base_url=WEB_BASE_URL, event_id=event.id)
            lines.append(f"购票链接：{official_url}")
            lines.append(f"网页详情：{web_url}")
        
        # 更新时间
        if event.update_time:
            lines.append(f"最后更新时间：{event.update_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append("剩余票务信息:")
        
        # 排序票务（按时间）
        sorted_tickets = sorted(event.tickets, key=lambda x: x.session_time or datetime.max)
        active_tickets = [t for t in sorted_tickets if t.status != "expired"]
        
        # 限制显示数量（除非 show_all）
        display_tickets = active_tickets if show_all else active_tickets[:20]
        
        for t in display_tickets:
            lines.append(HulaquanFormatter._format_ticket_line(t, show_title=True))
        
        if not show_all and len(active_tickets) > 20:
            lines.append(f"\n...等 {len(active_tickets)} 个场次")
            if event.id:
                official_url = HLQ_OFFICIAL_URL_TEMPLATE.format(event_id=event.id)
                lines.append(f"💡 使用 -all 查看全部，或直接购票：{official_url}")
        
        return "\n".join(lines)

    @staticmethod
    def format_date_events(date: datetime, tickets: List[TicketInfo], show_all: bool = False) -> str:
        """
        格式化某日演出列表（/date 命令）- 旧版格式（按城市和时间分组）
        """
        date_str = date.strftime("%Y-%m-%d")
        lines = [f"{date_str} 呼啦圈学生票场次："]
        
        if not tickets:
            lines.append("😴 暂无学生票演出安排")
            return "\n".join(lines)
        
        # 按城市分组
        by_city: Dict[str, List[TicketInfo]] = {}
        for t in tickets:
            city = t.city or "未知城市"
            by_city.setdefault(city, []).append(t)
        
        for city, city_tickets in by_city.items():
            lines.append(f"城市：{city}")
            
            # 按时间分组
            by_time: Dict[str, List[TicketInfo]] = {}
            for t in city_tickets:
                time_key = t.session_time.strftime("%H:%M") if t.session_time else "时间未知"
                by_time.setdefault(time_key, []).append(t)
            
            for time_key, time_tickets in sorted(by_time.items()):
                lines.append(f"⏲️时间：{time_key}")
                
                display_tickets = time_tickets if show_all else time_tickets[:15]
                for t in display_tickets:
                    lines.append(HulaquanFormatter._format_ticket_line(t, show_title=True))
                
                if not show_all and len(time_tickets) > 15:
                    lines.append(f"  ...等 {len(time_tickets)} 个场次")
        
        lines.append(f"\n数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not show_all:
            url = WEB_DATE_URL_TEMPLATE.format(base_url=WEB_BASE_URL, date_str=date_str)
            lines.append(f"💡 使用 -all 查看全部或访问: {url}")
        
        return "\n".join(lines)

    @staticmethod
    def format_updates_announcement(updates: List[TicketUpdate]) -> List[str]:
        """
        格式化通知消息（上新/补票/回流等）- 旧版格式
        """
        if not updates:
            return []
        
        # 按事件分组
        grouped: Dict[str, List[TicketUpdate]] = {}
        for u in updates:
            grouped.setdefault(u.event_id, []).append(u)
        
        messages = []
        
        for eid, event_updates in grouped.items():
            event_title = event_updates[0].event_title
            
            # 按类型分组
            by_type: Dict[str, List[TicketUpdate]] = {}
            for u in event_updates:
                by_type.setdefault(u.change_type, []).append(u)
            
            lines = []
            
            # 类型前缀映射
            type_prefix = {
                "new": "🆕上新提醒",
                "add": "🟢补票提醒",
                "restock": "♻️回流提醒",
                "back": "➕票增提醒",
                "decrease": "➖票减提醒",
                "sold_out": "❗售罄提醒",
                "stock_decrease": "➖票减提醒",
                "stock_increase": "➕票增提醒",
                "pending": "⏲️待开票提醒",
            }
            
            for change_type, type_updates in by_type.items():
                prefix = type_prefix.get(change_type, "📢动态")
                lines.append(f"{prefix}：")
                lines.append(f"剧名: {event_title}")
                
                # 购票链接
                if eid:
                    official_url = HLQ_OFFICIAL_URL_TEMPLATE.format(event_id=eid)
                    web_url = WEB_DETAIL_URL_TEMPLATE.format(base_url=WEB_BASE_URL, event_id=eid)
                    lines.append(f"购票链接：{official_url}")
                    lines.append(f"网页详情：{web_url}")
                
                lines.append(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("")
                lines.append(f"{prefix}：")
                
                for u in type_updates:
                    lines.append(u.message)
                
                lines.append("")
            
            messages.append("\n".join(lines))
        
        return messages

    @staticmethod
    def format_co_casts(results: List[Dict], limit: int = 10, show_link: Optional[str] = None) -> str:
        """格式化同场演员搜索结果"""
        if not results:
            return "👥 未找到同场演出信息。"
        
        lines = [f"👥 找到 {len(results)} 场同台演出:"]
        
        for i, item in enumerate(results[:limit]):
            date_str = item.get("date", "未知日期")
            title = item.get("title", "未知剧目")
            city = item.get("city", "")
            city_str = f"[{city}]" if city else ""
            casts = item.get("casts", [])
            cast_str = " ".join(casts[:5]) if casts else ""
            
            lines.append(f"{i+1}. {date_str} 《{title}》{city_str} {cast_str}")
        
        if len(results) > limit:
            lines.append(f"\n...等 {len(results)} 场 (仅显示前 {limit} 场)")
        
        if show_link:
            lines.append(f"\n🔗 网页快速筛选: {show_link}")
        
        return "\n".join(lines)

    @staticmethod
    def format_send_queue_payload(updates: List[Dict]) -> str:
        """
        从 SendQueue payload (List[Dict]) 重建旧版格式通知消息。
        
        格式参考:
        🆕上新提醒|🟢补票提醒：
        剧名: 《剧名》
        购票链接: ...
        
        🆕上新提醒：
        ✨01-17 19:30 ￥199 ...
        ...
        """
        if not updates:
            return ""
            
        # 1. Group by Event ID
        events = {} # event_id -> {title: str, updates: [dict]}
        for u in updates:
            eid = u.get("event_id", "unknown")
            if eid not in events:
                events[eid] = {
                    "title": u.get("event_title", "未知剧目"), 
                    "updates": []
                }
            events[eid]["updates"].append(u)
            
        final_messages = []
        
        type_prefix_map = {
            "new": "🆕上新",
            "add": "🟢补票",
            "restock": "♻️回流",
            "back": "➕票增",
            "decrease": "➖票减",
            "sold_out": "❗售罄",
            "stock_decrease": "➖票减",
            "stock_increase": "➕票增",
            "pending": "⏲️待开票",
        }
        
        for eid, event_data in events.items():
            event_title = event_data["title"]
            event_updates = event_data["updates"]
            
            # 2. Group by Change Type
            by_type = {}
            for u in event_updates:
                ctype = u.get("change_type", "other")
                if ctype not in by_type:
                    by_type[ctype] = []
                by_type[ctype].append(u)
            
            # 3. Build Header (Combined Prefixes)
            prefixes = []
            # Sort types by priority/logic
            type_order = ["new", "restock", "back", "decrease", "pending"]
            sorted_types = sorted(by_type.keys(), key=lambda k: type_order.index(k) if k in type_order else 99)
            
            for ctype in sorted_types:
                p = type_prefix_map.get(ctype, "📢动态")
                prefixes.append(f"{p}提醒")
            
            header_line = f"{'|'.join(prefixes)}："
            
            # 4. Build Event Info
            lines = [header_line]
            # Ensure title has brackets (prevent double brackets) and remove marketing text
            clean_title = event_title.strip()
            display_title = extract_text_in_brackets(clean_title, keep_brackets=True)
            lines.append(f"剧名: {display_title}")
            
            if eid and eid != "unknown":
                official_url = HLQ_OFFICIAL_URL_TEMPLATE.format(event_id=eid)
                web_url = WEB_DETAIL_URL_TEMPLATE.format(base_url=WEB_BASE_URL, event_id=eid)
                lines.append(f"购票链接：{official_url}")
                lines.append(f"网页详情：{web_url}")
            
            lines.append(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            
            # 5. Build Ticket Lines for each type
            for ctype in sorted_types:
                p = type_prefix_map.get(ctype, "📢动态")
                sub_header = f"{p}提醒："
                lines.append(sub_header)
                
                # Sort tickets by time
                u_list = by_type[ctype]
                # Helper to parse time safely
                def get_time(x):
                    ts = x.get("session_time")
                    if ts:
                        try:
                            return datetime.fromisoformat(ts) 
                        except: pass
                    return datetime.max
                
                u_list.sort(key=get_time)
                
                for u in u_list:
                    # Reconstruct TicketInfo-like line
                    # Format: DATE TIME PRICE TYPE STOCK CAST
                    parts = []
                    
                    # session time
                    st_str = ""
                    st_obj = None
                    if u.get("session_time"):
                        try:
                            st_obj = datetime.fromisoformat(u.get("session_time"))
                            st_str = st_obj.strftime("%m-%d %H:%M")
                        except: pass
                    
                    parts.append(st_str)
                    
                    # price
                    price = u.get("price", 0)
                    parts.append(f"￥{int(price)}")
                    
                    # type (always Student Ticket implies?)
                    # Legacy added "学生票" unless in title. We can just add it.
                    parts.append("学生票")
                    
                    # stock
                    stock = u.get("stock", 0)
                    total = u.get("total_ticket", "?")
                    parts.append(f"余票{stock}/{total}")
                    
                    # cast
                    casts = u.get("cast_names")
                    if casts:
                         if isinstance(casts, list):
                             parts.append(" ".join(casts))
                         else:
                             parts.append(str(casts))
                    
                    # Join
                    line_content = " ".join([p for p in parts if p])
                    
                    # Add icon based on stock/status
                    icon = "✨"
                    if ctype == "pending": icon = "⏲️"
                    elif stock == 0: icon = "❌"
                    
                    lines.append(f"{icon} {line_content}")
                
                lines.append("") # Empty line after each block
            
            final_messages.append("\n".join(lines).strip())
            
        return "\n\n".join(final_messages)
