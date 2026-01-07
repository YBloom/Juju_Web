
import logging
import asyncio
import os
from typing import Optional, List, Dict
from services.hulaquan.service import HulaquanService
from services.hulaquan.models import TicketInfo

log = logging.getLogger(__name__)

# --- Magic Link Configuration (与 web_app.py 共享) ---
import jwt
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 5
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")


def create_magic_link_token(qq_id: str, nickname: str = "") -> str:
    """为 Bot 用户生成 Magic Link Token"""
    payload = {
        "qq_id": qq_id,
        "nickname": nickname,
        "exp": datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(ZoneInfo("Asia/Shanghai")),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class BotHandler:
    def __init__(self, service: HulaquanService):
        self.service = service

    async def handle_message(self, message: str, user_id: str, nickname: str = "") -> Optional[str]:
        """
        统一消息处理入口，供私聊和群聊共用。
        """
        return await self.handle_group_message(0, int(user_id), message, nickname=nickname)

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member", nickname: str = "") -> Optional[str]:
        """
        Handle group messages and return a response string or None.
        """
        msg = message.strip()
        
        # --- /web 命令: 生成 Magic Link 登录链接 ---
        if msg == "/web" or msg == "/登录":
            token = create_magic_link_token(str(user_id), nickname)
            link = f"{WEB_BASE_URL}/auth?token={token}"
            return f"🔐 点击下方链接登录 Web 控制台（5分钟内有效）：\n\n👉 {link}\n\n✨ 登录后可查看完整演出信息、管理订阅等"
        
        # --- /hlq 命令: 快速查票 (兼容旧指令) ---
        if msg.startswith("/hlq ") or msg.startswith("/hlq"):
            parts = msg.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                return "请指定剧目名称，例如: /hlq 剧院魅影"
            query = parts[1].strip()
            return await self._handle_search(query)
        
        # --- 查票 命令 (简化版) ---
        if msg.startswith("查票") or msg.startswith("查 "):
            parts = msg.split(" ", 1)
            if len(parts) < 2:
                return "请指定剧目名称，例如: 查票 剧院魅影"
            
            query = parts[1].strip()
            if not query:
                return "查询词不能为空"
                
            return await self._handle_search(query)

        # --- /同场演员 命令: 重定向到 Web ---
        if msg.startswith("/同场演员 ") or msg.startswith("/同场演员"):
            parts = msg.split(" ", 1)
            if len(parts) < 2 or not parts[1].strip():
                return "请指定演员名，例如: /同场演员 张三 李四"
            actors = parts[1].strip().replace(" ", ",")
            web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={actors}"
            return f"🔍 同场演员查询已升级至 Web 版！\n\n👉 点击查看: {web_link}"

        if msg == "订阅列表":
            return f"请前往 Web 控制台查看订阅:\n👉 {WEB_BASE_URL}"

        return None

    async def _handle_search(self, query: str) -> str:
        try:
            # 1. Search DB
            results = await self.service.search_events(query)
            
            if not results:
                return f"未找到包含 '{query}' 的剧目。"
            
            # 2. Format Result (限制前 3 个)
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
                response_lines.append(f"\n...以及其他 {len(results)-3} 个结果")
            
            # 添加 Web 引流
            response_lines.append(f"\n\n🌐 查看详情: {WEB_BASE_URL}")
                
            return "".join(response_lines)
            
        except Exception as e:
            log.error(f"Error searching events: {e}", exc_info=True)
            return "搜索时发生系统错误，请联系管理员。"
