"""
BotHandler - QQ Bot 命令处理（旧版兼容）
"""
import logging
import asyncio
import os
import re
from typing import Optional, List, Dict, Tuple
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


def extract_args(message: str) -> Dict:
    """
    解析命令参数（兼容旧版格式）
    返回: {"command": str, "text_args": List[str], "mode_args": List[str]}
    """
    parts = [p for p in message.split() if p]
    if not parts:
        return {"command": "", "text_args": [], "mode_args": []}
    
    command = parts[0]
    mode_args = [p.lower() for p in parts[1:] if p.startswith("-")]
    text_args = [p for p in parts[1:] if not p.startswith("-")]
    
    return {"command": command, "text_args": text_args, "mode_args": mode_args}


class BotHandler:
    def __init__(self, service: HulaquanService):
        self.service = service
        self.saoju_service = SaojuService()

    async def get_user_mode(self, user_id: str) -> str:
        """Get user's preferred interaction mode from DB (default: legacy)."""
        try:
            with session_scope() as session:
                user = session.get(User, user_id)
                if user and user.bot_interaction_mode:
                    return user.bot_interaction_mode
        except Exception as e:
            log.warning(f"⚠️ [用户] 获取用户 {user_id} 交互模式失败: {e}")
        return "legacy"  # 默认旧版模式

    async def handle_message(self, message: str, user_id: str, nickname: str = "") -> Optional[str]:
        return await self.handle_group_message(0, int(user_id), message, nickname=nickname)

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member", nickname: str = "") -> Optional[str]:
        msg = message.strip()
        uid_str = str(user_id)
        
        log.info(f"💬 [消息] 收到来自 {user_id} 的消息: {msg}")
        
        # --- Help Command ---
        if msg.lower() in ["/help", "help", "帮助", "菜单", "/帮助"]:
            return self._get_help_text()
        
        # --- Auth / Login ---
        if msg in ["/web", "/登录", "/login"]:
            token = create_magic_link_token(uid_str, nickname)
            link = f"{WEB_BASE_URL}/auth/magic-link?token={token}"
            return (
                f"🔐 点击下方链接登录 Web 控制台（5分钟内有效）：\n\n"
                f"👉 {link}\n\n"
                f"✨ 登录后可查看完整演出信息、管理订阅等\n\n"
                f"💡 提示：如在 QQ 内打开遇到问题，请复制链接到外部浏览器"
            )

        # --- Parse Args ---
        args = extract_args(msg)
        mode_args = args["mode_args"]
        text_args = args["text_args"]
        show_all = "-all" in mode_args
        
        # --- /date Command ---
        if msg.startswith("/date"):
            date_str = text_args[0] if text_args else datetime.now().strftime("%Y-%m-%d")
            city = text_args[1] if len(text_args) > 1 else None
            return await self._handle_date(date_str, city, show_all)

        # --- /hlq Command ---
        if msg.startswith("/hlq ") or msg.startswith("查票 "):
            query = " ".join(text_args)
            if not query:
                return "请指定剧目名称，例如: /hlq 连璧"
            return await self._handle_hlq(query, show_all)

        # --- /同场演员 Command ---
        if msg.startswith("/同场演员 ") or msg.startswith("/cast "):
            actors = text_args
            if not actors:
                return "请指定演员，用空格分隔，例如: /同场演员 张三 李四"
            show_others = "-o" in mode_args
            use_hulaquan = "-h" in mode_args
            return await self._handle_cocast(actors, show_others, use_hulaquan)

        return None

    def _get_help_text(self) -> str:
        """返回帮助文档"""
        return (
            "🤖 MusicalBot 帮助菜单\n"
            "==================\n\n"
            "📅 【查询排期】\n"
            "  /date [日期] [城市] [-all]\n"
            "  例: /date 2026-01-20 上海\n\n"
            "🔍 【查询剧目学生票】\n"
            "  /hlq [剧名] [-all]\n"
            "  例: /hlq 连璧\n\n"
            "👥 【同场演员查询】\n"
            "  /同场演员 [演员1] [演员2] [-o] [-h]\n"
            "  -o: 显示同场其他演员\n"
            "  -h: 仅检索呼啦圈数据\n\n"
            "🔐 【Web 控制台】\n"
            "  /登录 或 /web\n\n"
            f"💡 更多功能请访问: {WEB_BASE_URL}"
        )

    # --- Command Implementations ---

    async def _handle_date(self, date_str: str, city: Optional[str], show_all: bool) -> str:
        """处理 /date 命令"""
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return "❌ 日期格式错误，请使用 YYYY-MM-DD，例如: /date 2026-01-20"
        
        results = await self.service.get_events_by_date(target_date, city)
        
        if not results:
            return f"📅 {date_str} 暂无收录的学生票演出信息。"
        
        return HulaquanFormatter.format_date_events(target_date, results, show_all=show_all)

    async def _handle_hlq(self, query: str, show_all: bool) -> str:
        """处理 /hlq 命令"""
        results = await self.service.search_events(query)
        
        if not results:
            return f"❌ 未找到包含 '{query}' 的剧目。"
        
        # 只返回第一个最匹配的结果
        event = results[0]
        return HulaquanFormatter.format_event_search_result(event, show_all=show_all)

    async def _handle_cocast(self, actors: List[str], show_others: bool, use_hulaquan: bool) -> str:
        """处理 /同场演员 命令"""
        start_date = datetime.now().strftime("%Y-%m-%d")
        actors_str = " ".join(actors)
        
        if use_hulaquan:
            # 使用呼啦圈本地数据
            try:
                results = await self.service.search_co_casts(actors)
                if not results:
                    return f"❌ 在呼啦圈系统中未找到 {actors_str} 的同场演出学生票"
                
                web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={','.join(actors)}"
                return HulaquanFormatter.format_co_casts(results, limit=30, show_link=web_link)
            except Exception as e:
                log.error(f"Hulaquan co-cast search failed: {e}")
                return "查询失败，请稍后重试。"
        else:
            # 使用扫剧系统
            try:
                results = await self.saoju_service.match_co_casts(
                    actors, show_others=show_others, start_date=start_date
                )
                
                if not results:
                    return f"👥 未找到 {actors_str} 在 {start_date} 之后的同台演出。"
                
                web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={','.join(actors)}"
                return HulaquanFormatter.format_co_casts(results, limit=30, show_link=web_link)
            except Exception as e:
                log.error(f"Saoju co-cast search failed: {e}")
                return "查询失败，扫剧系统可能暂时不可用。"
