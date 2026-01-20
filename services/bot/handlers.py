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

ROOT_ID = "3022402752"


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
    # 模式参数：以 - 开头且后面不是纯数字的 (如 -E, -A, -all)
    # 文本参数：不以 - 开头，或者是类似 -3 这样的负数形式（用于指定级别）
    mode_args = [p.lower() for p in parts[1:] if p.startswith("-") and not p[1:].isdigit()]
    text_args = [p for p in parts[1:] if not p.startswith("-") or p[1:].isdigit()]
    
    return {"command": command, "text_args": text_args, "mode_args": mode_args}


class BotHandler:
    def __init__(self, service: HulaquanService):
        self.service = service
        self.saoju_service = SaojuService()

    def _ensure_user_exists(self, user_id: str, nickname: str = ""):
        """确保用户在数据库中存在 (由于外键约束)"""
        from services.db.models import User
        try:
            with session_scope() as session:
                user = session.get(User, user_id)
                if not user:
                    user = User(user_id=user_id, nickname=nickname or user_id)
                    session.add(user)
                    session.commit()
                    log.info(f"👤 [用户] 已为 {user_id} 创建新用户记录")
        except Exception as e:
            log.error(f"❌ [用户] 确保用户 {user_id} 存在时出错: {e}")

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

    async def _handle_set_notify_level(self, user_id: str, level: Optional[int] = None) -> str:
        """处理 /呼啦圈通知 [0-5] 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionOption
        from sqlmodel import select
        
        if level is None:
            return (
                "🔔 呼啦圈通知设置\n\n"
                "用法: /呼啦圈通知 [0-5]\n\n"
                "级别说明:\n"
                "0: 关闭通知\n"
                "1: 仅上新\n"
                "2: 上新+补票 (推荐)\n"
                "3: 上新+补票+回流\n"
                "4: 上新+补票+回流+票减\n"
                "5: 全量 (上新+补票+回流+票增+票减)"
            )
        
        if not (0 <= level <= 5):
            return "❌ 级别必须在 0-5 之间"
        
        with session_scope() as session:
            # 查找或创建订阅
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                sub = Subscription(user_id=user_id)
                session.add(sub)
                session.flush()
            
            # 更新或创建SubscriptionOption
            stmt_opt = select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)
            opt = session.exec(stmt_opt).first()
            
            if opt:
                opt.notification_level = level
            else:
                opt = SubscriptionOption(
                    subscription_id=sub.id,
                    notification_level=level
                )
                session.add(opt)
            
            session.commit()
        
        level_names = ["关闭", "上新", "上新+补票", "上新+补票+回流", "上新+补票+回流+票减", "全量"]
        return f"✅ 全局通知级别已设置为: {level} ({level_names[level]})"
    
    async def _handle_subscribe(self, user_id: str, args: dict) -> str:
        """处理 /关注学生票 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionTarget
        from services.db.models.base import SubscriptionTargetKind
        from sqlmodel import select
        
        mode_args = args.get("mode_args", [])
        text_args = args.get("text_args", [])
        
        if not text_args:
            return (
                "💡 用法:\n"
                "/关注学生票 -E [剧名] [级别]  # 关注剧目\n"
                "/关注学生票 -A [演员] [级别]  # 关注演员\n"
                "\n示例:\n"
                "/关注学生票 -E 连璧 2"
            )
        
        # 解析参数
        kind = SubscriptionTargetKind.PLAY  # 默认剧目
        level = 2  # 默认级别2
        
        if "-A" in mode_args:
            kind = SubscriptionTargetKind.ACTOR
        elif "-E" in mode_args or not any(arg.startswith("-") for arg in mode_args):
            kind = SubscriptionTargetKind.PLAY
        
        # 尝试解析级别 (支持 3 或 -3)
        extracted_level = level
        remaining_text_args = []
        for arg in text_args:
            try:
                # 去掉可能的负号前缀，尝试转为数字
                val = int(arg.lstrip("-"))
                if 1 <= val <= 5:
                    extracted_level = val
                else:
                    remaining_text_args.append(arg)
            except ValueError:
                remaining_text_args.append(arg)
        
        text_args = remaining_text_args
        level = extracted_level
        
        target_name = " ".join(text_args) if text_args else ""
        if not target_name:
            return "❌ 请提供剧目或演员名称"
        
        # 尝试解析真实 ID (针对剧目)
        target_id = target_name
        if kind == SubscriptionTargetKind.PLAY:
            try:
                results = await self.service.search_events(target_name)
                if results:
                    # 获取最匹配的结果
                    event = results[0]
                    target_id = str(event.id)
                    target_name = event.title  # 使用清洗后的官方标题
                    log.info(f"🔍 [订阅] 已将 '{target_name}' 解析为 ID: {target_id}")
            except Exception as e:
                log.warning(f"⚠️ [订阅] 解析剧目 ID 失败: {e}")
        
        with session_scope() as session:
            # 查找或创建订阅
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                sub = Subscription(user_id=user_id)
                session.add(sub)
                session.flush()
            
            # 检查是否已存在
            stmt_target = select(SubscriptionTarget).where(
                SubscriptionTarget.subscription_id == sub.id,
                SubscriptionTarget.kind == kind,
               SubscriptionTarget.name == target_name
            )
            existing = session.exec(stmt_target).first()
            
            if existing:
                # 更新级别
                existing.flags = {"mode": level}
                session.add(existing)
                msg = f"✅ 已更新订阅: {target_name} (级别 {level})"
            else:
                # 创建新订阅
                target = SubscriptionTarget(
                    subscription_id=sub.id,
                    kind=kind,
                    target_id=target_name,  # 简化版,实际应查询ID
                    name=target_name,
                    flags={"mode": level}
                )
                session.add(target)
                kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
                msg = f"✅ 已成功关注{kind_name}: {target_name} (级别 {level})"
            
            session.commit()
        
        return msg
    
    async def _handle_unsubscribe(self, user_id: str, args: dict) -> str:
        """处理 /取消关注学生票 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionTarget
        from services.db.models.base import SubscriptionTargetKind
        from sqlmodel import select
        
        mode_args = args.get("mode_args", [])
        text_args = args.get("text_args", [])
        
        if not text_args:
            return (
                "💡 用法:\n"
                "/取消关注学生票 -E [剧名]  # 取消关注剧目\n"
                "/取消关注学生票 -A [演员]  # 取消关注演员"
            )
        
        kind = SubscriptionTargetKind.PLAY
        if "-A" in mode_args:
            kind = SubscriptionTargetKind.ACTOR
        
        target_name = " ".join(text_args)
        
        with session_scope() as session:
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                return "❌ 您还没有任何订阅"
            
            stmt_target = select(SubscriptionTarget).where(
                SubscriptionTarget.subscription_id == sub.id,
                SubscriptionTarget.kind == kind,
                SubscriptionTarget.name == target_name
            )
            target = session.exec(stmt_target).first()
            
            if not target:
                kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
                return f"❌ 未找到对{kind_name} {target_name} 的订阅"
            
            session.delete(target)
            session.commit()
        
        kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
        return f"✅ 已取消关注{kind_name}: {target_name}"
    
    async def _handle_list_subscriptions(self, user_id: str) -> str:
        """处理 /查看关注 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionOption, SubscriptionTarget, HulaquanEvent
        from services.db.models.base import SubscriptionTargetKind
        from sqlmodel import select
        
        with session_scope() as session:
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                return "您目前没有任何订阅。\n\n使用 /呼啦圈通知 2 开启全局通知"
            
            lines = ["📋 我的订阅\n"]
            
            # 显示全局设置
            stmt_opt = select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)
            opt = session.exec(stmt_opt).first()
            
            if opt:
                level_names = ["关闭", "上新", "上新+补票", "上新+补票+回流", "上新+补票+回流+票减", "全量"]
                lines.append(f"🔔 全局通知级别: {opt.notification_level} ({level_names[opt.notification_level]})")
                if opt.silent_hours:
                    lines.append(f"🌙 静音时段: {opt.silent_hours}")
            else:
                lines.append("🔔 全局通知: 未设置")
            
            # 获取所有订阅目标
            stmt_targets = select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)
            targets = session.exec(stmt_targets).all()
            
            if not targets:
                lines.append("\n暂无具体订阅项")
            else:
                # 按类型分组
                plays = [t for t in targets if t.kind in (SubscriptionTargetKind.PLAY, "EVENT")]
                actors = [t for t in targets if t.kind in (SubscriptionTargetKind.ACTOR, "ACTOR")]
                
                if plays:
                    lines.append("\n【关注的剧目】")
                    for i, t in enumerate(plays, 1):
                        display_name = t.name
                        if not display_name:
                            # 动态查找名称
                            try:
                                event = session.get(HulaquanEvent, t.target_id)
                                if event:
                                    display_name = event.title
                                else:
                                    display_name = f"未知剧目 (ID: {t.target_id})"
                            except Exception:
                                display_name = f"未知剧目 (ID: {t.target_id})"
                                
                        mode = t.flags.get("mode", 2) if t.flags else 2
                        lines.append(f"{i}. {display_name} (级别 {mode})")
                
                if actors:
                    lines.append("\n【关注的演员】")
                    for i, t in enumerate(actors, 1):
                        mode = t.flags.get("mode", 2) if t.flags else 2
                        lines.append(f"{i}. {t.name} (级别 {mode})")
            
            return "\n".join(lines)

    async def handle_message(self, message: str, user_id: str, nickname: str = "") -> Optional[str]:
        return await self.handle_group_message(0, int(user_id), message, nickname=nickname)

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member", nickname: str = "") -> Optional[str]:
        msg = message.strip()
        uid_str = str(user_id)
        
        log.info(f"💬 [消息] 收到来自 {user_id} 的消息: {msg}")
        
        # --- 提前解析参数，避免各分支重复解析及 UnboundLocalError ---
        args = extract_args(msg)
        mode_args = args["mode_args"]
        text_args = args["text_args"]
        
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

        # --- 权限与目标确定 ---
        is_root = str(user_id) == ROOT_ID
        if is_root and group_id != 0:
            effective_uid = f"group_{group_id}"
            target_desc = f"当前群组 ({group_id})"
            self._ensure_user_exists(effective_uid, nickname=f"群组 {group_id}")
        else:
            effective_uid = uid_str
            target_desc = "个人"
            self._ensure_user_exists(effective_uid, nickname=nickname)

        # --- 订阅管理命令 ---
        # /呼啦圈通知 [0-5]
        if msg.startswith("/呼啦圈通知"):
            level = None
            if text_args:
                try:
                    level = int(text_args[0])
                except ValueError:
                    pass
            response = await self._handle_set_notify_level(effective_uid, level)
            if effective_uid.startswith("group_"):
                response = response.replace("✅ ", f"✅ [群订阅] ")
            return response
        
        # /关注学生票
        if msg.startswith("/关注学生票"):
            response = await self._handle_subscribe(effective_uid, args)
            if effective_uid.startswith("group_"):
                response = response.replace("✅ ", f"✅ [群订阅] ")
            return response
        
        # /取消关注学生票
        if msg.startswith("/取消关注学生票"):
            response = await self._handle_unsubscribe(effective_uid, args)
            if effective_uid.startswith("group_"):
                response = response.replace("✅ ", f"✅ [群订阅] ")
            return response
        
        # /查看关注
        if msg in ["/查看关注", "/我的订阅", "/订阅列表"]:
            return await self._handle_list_subscriptions(effective_uid)

        # --- 其他查询命令 ---
        show_all = "-all" in mode_args
        
        # 价格筛选支持 (e.g. -219)
        price_filters = []
        for arg in mode_args:
            if arg == "-all": continue
            try:
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
            f"📖 剧剧 BOT 帮助文档已升级！\n\n"
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
        # 1. 尝试直接搜索
        results = await self.service.search_events(query)
        
        # 2. 如果没找到，尝试拆分搜索 (标题 + 城市/关键词)
        # 例如: "时光代理人 上海" -> title="时光代理人", filter="上海"
        filter_keyword = ""
        if not results and " " in query:
            parts = query.split(" ", 1)
            title_query = parts[0]
            filter_keyword = parts[1]
            if title_query:
                results = await self.service.search_events(title_query)
        
        # 3. 如果有筛选词，进行过滤
        if results and filter_keyword:
            filtered = []
            kw = filter_keyword.lower()
            for ignored_event in results:
                # 检查 城市、地点、标题
                search_text = f"{ignored_event.city} {ignored_event.location} {ignored_event.title}".lower()
                if kw in search_text:
                    filtered.append(ignored_event)
            
            if filtered:
                results = filtered
            else:
                # 筛选后无结果，提示用户
                return f"🔍 找到相关剧目，但未匹配到底点/关键词 '{filter_keyword}'，请尝试只搜索标题。"

        if not results:
            return f"❌ 未找到包含 '{query}' 的剧目。"
        
        # 4. 如果结果仍多于1个，且没有足够精确，提示用户
        if len(results) > 1:
            # 构建选择列表
            msg = [f"🔍 找到 {len(results)} 个相关剧目，请指定城市/地点：\n"]
            for i, event in enumerate(results, 1):
                city_str = f"[{event.city}] " if event.city else ""
                schedule = event.schedule_range or "待定"
                msg.append(f"{i}. {city_str}{event.title}")
                msg.append(f"   📅 {schedule} @ {event.location}")
            
            msg.append(f"\n💡 请重新输入带城市的指令，例如: /hlq {results[0].title.split()[0]} {results[0].city or '北京'}")
            return "\n".join(msg)
        
        # 5. 只有一个结果，返回详情
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
