
import logging
import asyncio
import os
import re
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from services.hulaquan.service import HulaquanService
from services.saoju.service import SaojuService
from services.hulaquan.formatter import HulaquanFormatter
from services.hulaquan.models import TicketInfo
from services.db.connection import session_scope
from services.db.models import User
from sqlmodel import select

log = logging.getLogger(__name__)

# --- Magic Link Configuration ---
import jwt
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

JWT_SECRET = os.getenv("JWT_SECRET", "musicalbot-dev-secret-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 5
WEB_BASE_URL = os.getenv("WEB_BASE_URL", "https://yyj.yaobii.com")

def create_magic_link_token(qq_id: str, nickname: str = "") -> str:
    """Generate Magic Link Token for Bot User"""
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
        self.saoju_service = SaojuService()

    async def get_user_mode(self, user_id: str) -> str:
        """Get user's preferred interaction mode from DB (default: hybrid)."""
        # Optimized: Reading from simple cache or DB
        # For now, strict DB read (low concurrency expected for config)
        try:
            with session_scope() as session:
                user = session.get(User, user_id)
                if user and user.bot_interaction_mode:
                    return user.bot_interaction_mode
        except Exception as e:
            log.warning(f"⚠️ [用户] 获取用户 {user_id} 交互模式失败: {e}")
        return "hybrid"

    async def handle_message(self, message: str, user_id: str, nickname: str = "") -> Optional[str]:
        return await self.handle_group_message(0, int(user_id), message, nickname=nickname)

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member", nickname: str = "") -> Optional[str]:
        msg = message.strip()
        uid_str = str(user_id)
        
        # Debug Log
        log.info(f"💬 [消息] 收到来自 {user_id} 的消息: {msg}")
        
        # --- Help Command ---
        if msg.lower() in ["/help", "help", "帮助", "菜单"]:
            return (
                "🤖 MusicalBot 帮助菜单\n"
                "------------------\n"
                "📅 查询排期:\n"
                "  /date [日期] [城市]\n"
                "  例: /date 2026-01-01 上海\n\n"
                "🔍 查询剧目:\n"
                "  查票 [剧目名]\n"
                "  例: 查票 粉丝来信\n\n"
                "🔐 Web 控制台:\n"
                "  发送 /web 或 /登录 获取登录链接\n\n"
                "⚙️ 设置:\n"
                "  请在 Web 控制台中配置通知偏好"
            )
        
        # --- Auth / Login ---
        if msg == "/web" or msg == "/登录":
            token = create_magic_link_token(uid_str, nickname)
            link = f"{WEB_BASE_URL}/auth/magic-login?token={token}"
            return f"🔐 点击下方链接登录 Web 控制台（5分钟内有效）：\n\n👉 {link}\n\n✨ 登录后可查看完整演出信息、管理订阅等"

        # --- User Mode Check ---
        mode = await self.get_user_mode(uid_str)
        # Default modes configuration
        # You can override per command if needed, but generic "mode" applies generally.
        
        # --- /date Command ---
        if msg.startswith("/date"):
            # Format: /date 2026-01-01 [city]
            parts = msg.split()
            date_str = None
            city = None
            if len(parts) > 1:
                date_str = parts[1]
            else:
                date_str = datetime.now().strftime("%Y-%m-%d") # Default today
                
            if len(parts) > 2:
                city = parts[2]
            
            return await self._handle_date(date_str, city, mode)

        # --- /hlq Command (Search) ---
        if msg.startswith("/hlq "):
            query = msg[5:].strip()
            if not query: return "请指定剧目名称"
            return await self._handle_hlq(query, mode)
            
        if msg.startswith("查票 "): # Alias
            query = msg[3:].strip()
            if not query: return "请指定剧目名称"
            return await self._handle_hlq(query, mode)

        # --- /同场演员 (Co-Casts) ---
        if msg.startswith("/同场演员 ") or msg.startswith("/cast "):
            query = msg.split(" ", 1)[1].strip()
            if not query: return "请指定演员，用空格分隔"
            actors = [a.strip() for a in query.split() if a.strip()]
            return await self._handle_cocast(actors, mode)

        return None

    # --- Command Implementations ---

    async def _handle_date(self, date_str: str, city: Optional[str], mode: str) -> str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return "❌ 日期格式错误，请使用 YYYY-MM-DD，例如: /date 2026-01-20"
            
        # 1. Fetch Data
        results = await self.service.get_events_by_date(target_date, city)
        
        web_link = f"{WEB_BASE_URL}/?tab=calendar&date={date_str}"
        if city: web_link += f"&city={city}"

        # 2. Format based on Mode
        if mode == "lite":
            return f"📅 {date_str} 共找到 {len(results)} 场演出。\n🔗 点击查看: {web_link}"
            
        elif mode == "hybrid":
            # Show top 5
            if not results:
                return f"📅 {date_str} 暂无收录的演出信息。"
                
            summary = HulaquanFormatter.format_date_events(target_date, results[:5])
            if len(results) > 5:
                summary += f"\n...还有 {len(results)-5} 场"
            
            summary += f"\n🔗 完整排期: {web_link}"
            return summary
            
        else: # Legacy / Full
            if not results: return f"📅 {date_str} 暂无收录的演出信息。"
            # Legacy formatted everything
            # But let's limit safely to avoid excessive spam (e.g. 20 items max)
            limit = 20
            summary = HulaquanFormatter.format_date_events(target_date, results[:limit])
            if len(results) > limit:
                summary += f"\n...还有 {len(results)-limit} 场 (请使用 Web 查看全部)"
            return summary

    async def _handle_hlq(self, query: str, mode: str) -> str:
        results = await self.service.search_events(query)
        web_link = f"{WEB_BASE_URL}/?q={query}" # Assuming web has search param
        
        if not results:
            return f"❌ 未找到包含 '{query}' 的剧目。"

        if mode == "lite":
             return f"🔍 找到 {len(results)} 个结果。\n🔗 点击查看: {web_link}"
             
        elif mode == "hybrid":
            # Show top 3
            top = results[:3]
            txt = ""
            for e in top:
                txt += HulaquanFormatter.format_event_search_result(e) + "\n"
            
            if len(results) > 3:
                txt += f"\n...等 {len(results)} 个结果"
            txt += f"\n🔗 查看详情: {web_link}"
            return txt.strip()
            
        else: # Legacy (Full)
            # Legacy behavior often printed distinct messages or one long one
            # We stick to one long message but full detail for top N
            limit = 10
            top = results[:limit]
            txt = ""
            for e in top:
                txt += HulaquanFormatter.format_event_search_result(e) + "\n"
            if len(results) > limit:
                txt += f"\n...等 {len(results)} 个结果"
            return txt.strip()

    async def _handle_cocast(self, actors: List[str], mode: str) -> str:
        # Filter logic: Future only (User requirement)
        start_date = datetime.now().strftime("%Y-%m-%d")
        
        # Call Saoju Service
        results = await self.saoju_service.match_co_casts(
            actors, show_others=True, start_date=start_date
        )
        
        actors_str = ",".join(actors)
        web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={actors_str}"

        if not results:
             return f"👥 未找到 {actors_str} 在 {start_date} 之后的同台演出。"

        if mode == "lite":
            return f"👥 找到 {len(results)} 场同台。\n🔗 查看详情: {web_link}"
            
        elif mode == "hybrid":
            # Top 10
            return HulaquanFormatter.format_co_casts(results, limit=10, show_link=web_link)
            
        else: # Legacy
            # Legacy wants FULL list
            # But we must be careful of max length. 
            # "Legacy Text (Future Only) + Link" was the plan.
            # Let's show up to 30.
            return HulaquanFormatter.format_co_casts(results, limit=30, show_link=web_link)
