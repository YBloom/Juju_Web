
import logging
import asyncio
from typing import Optional, List, Dict
from services.hulaquan.service import HulaquanService
from services.hulaquan.models import TicketInfo

log = logging.getLogger(__name__)

class BotHandler:
    def __init__(self, service: HulaquanService):
        self.service = service

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member") -> Optional[str]:
        """
        Handle group messages and return a response string or None.
        """
        msg = message.strip()
        
        if msg.startswith("查票") or msg.startswith("查 "):
            parts = msg.split(" ", 1)
            if len(parts) < 2:
                return "请指定剧目名称，例如: 查票 剧院魅影"
            
            query = parts[1].strip()
            if not query:
                return "查询词不能为空"
                
            return await self._handle_search(query)

        if msg == "订阅列表":
            # TODO: Implement subscription list for user
            return "请前往 Web 控制台查看订阅: http://admin.yaobii.com"

        return None

    async def _handle_search(self, query: str) -> str:
        try:
            # 1. Search DB
            # Use the search_events method from HulaquanService
            results = await self.service.search_events(query)
            
            if not results:
                return f"未找到包含 '{query}' 的剧目。"
            
            # 2. Format Result
            # Limit to top 3
            top_results = results[:3]
            response_lines = [f"🔍 找到 {len(results)} 个结果 (显示前 {len(top_results)} 个):"]
            
            for event in top_results:
                line = f"\n🎭 {event.title}"
                if event.city:
                    line += f" [{event.city}]"
                
                # Available Tickets Summary
                tickets_available = [t for t in event.tickets if t.stock > 0 and t.status != "expired"]
                if not tickets_available:
                    line += "\n   (暂无余票)"
                else:
                    line += f"\n   🎫 余票: {sum(t.stock for t in tickets_available)} 张"
                    # Group by price
                    price_groups = {}
                    for t in tickets_available:
                        p = int(t.price) if t.price.is_integer() else t.price
                        price_groups[p] = price_groups.get(p, 0) + t.stock
                    
                    price_str = ", ".join([f"¥{p}x{c}" for p, c in sorted(price_groups.items())])
                    line += f"\n   💰 价位: {price_str}"
                    
                    # Show upcoming sessions
                    sessions = sorted(list(set(t.session_time for t in tickets_available if t.session_time)))
                    if sessions:
                        s_str = ", ".join([s.strftime("%m-%d") for s in sessions[:3]])
                        if len(sessions) > 3:
                            s_str += "..."
                        line += f"\n   📅 场次: {s_str}"
                
                response_lines.append(line)
                
            if len(results) > 3:
                response_lines.append(f"\n...以及其他 {len(results)-3} 个结果，请访问 Web 端查看详情。")
                
            return "".join(response_lines)
            
        except Exception as e:
            log.error(f"Error searching events: {e}", exc_info=True)
            return "搜索时发生系统错误，请联系管理员。"

