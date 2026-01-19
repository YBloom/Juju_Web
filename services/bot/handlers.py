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

    async def _handle_subscription(self, user_id: str, nickname: str) -> str:
        """Handle /subscribe command"""
        token = create_magic_link_token(user_id, nickname)
        # Using URL fragment for detailed tab navigation if supported by frontend
        # The frontend router likely handles #user or similar. 
        # We pass redirect param to magic link. 
        # Note: If passing # in query param, it must be encoded? 
        # Ideally: /auth/magic-link?token=...&redirect=/#user
        # The browser will handle the redirect.
        link = f"{WEB_BASE_URL}/auth/magic-link?token={token}&redirect=/%23user"
        
        return (
            "🔔 <b>订阅管理</b>\n\n"
            "为了提供更丰富的功能（如静音时段、精确屏蔽、演员关注），我们将订阅管理迁移到了 Web 端。\n\n"
            f"👉 <a href='{link}'>点击此处管理我的订阅</a>\n\n"
            "在网页中，您可以：\n"
            "- 添加/删除剧目和演员订阅\n"
            "- 设置静音时段（如夜间不打扰）\n"
            "- 开启或关闭每日汇总日报"
        )

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

        # --- Subscribe Command ---
        if msg in ["/subscribe", "/订阅", "订阅"]:
            return await self._handle_subscription(uid_str, nickname)

        # --- Parse Args ---
        args = extract_args(msg)
        mode_args = args["mode_args"]
        text_args = args["text_args"]
        show_all = "-all" in mode_args
        
        # 价格筛选支持 (e.g. -219)
        price_filters = []
        for arg in mode_args:
            if arg == "-all": continue
            try:
                # 尝试解析 -数字
                p = float(arg.lstrip("-"))
                price_filters.append(p)
            except ValueError:
                continue
        
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
            return await self._handle_hlq(query, show_all, price_filters)

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
            f"📖 <b>剧剧 (YYJ) 帮助文档已升级！</b>\n\n"
            f"为了提供更好的阅读体验，我们将帮助文档迁移到了 Web 端。\n"
            f"请点击下方链接查看完整命令说明：\n\n"
            f"👉 {WEB_BASE_URL}/help\n\n"
            f"常用指令速查：\n"
            f"• 查排期: /date [日期]\n"
            f"• 查剧目: /hlq [剧名]\n"
            f"• 查同场: /cast [演员1] [演员2]\n"
            f"• 登录Web: /web"
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

    async def _handle_hlq(self, query: str, show_all: bool, price_filters: List[float] = None) -> str:
        """处理 /hlq 命令"""
        results = await self.service.search_events(query)
        
        if not results:
            return f"❌ 未找到包含 '{query}' 的剧目。"
        
        # 只返回第一个最匹配的结果
        event = results[0]
        
        # 应用价格筛选
        if price_filters:
            filtered_tickets = [t for t in event.tickets if t.price in price_filters]
            if not filtered_tickets:
                price_strs = ", ".join([f"￥{int(p)}" for p in price_filters])
                return f"🔍 在 《{event.title}》 中未找到价格为 {price_strs} 的学生票。"
            event.tickets = filtered_tickets

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
