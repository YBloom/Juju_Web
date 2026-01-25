"""
BotHandler - QQ Bot 命令处理（旧版兼容）
"""
import logging
import asyncio
import os
import re
from typing import Optional, List, Dict, Tuple, Union
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


MODE_DESCRIPTIONS = {
    0: "无通知",
    1: "仅通知 上新",
    2: "上新 + 补票 (★推荐)",
    3: "上新 + 补票 + 回流",
    4: "3 + 票减",
    5: "3 + 票增/票减 (全部变动)"
}



from services.bot.commands import resolve_command

def extract_args(message: str) -> Dict:
    """
    解析命令参数（兼容旧版格式）
    返回: {"command": str, "text_args": List[str], "mode_args": List[str]}
    """
    parts = [p for p in message.split() if p]
    if not parts:
        return {"command": "", "text_args": [], "mode_args": []}
    
    raw_trigger = parts[0]
    # 尝试解析别名到标准指令
    canonical = resolve_command(raw_trigger)
    command = canonical if canonical else raw_trigger
    
    # 模式参数：以 - 开头且后面不是纯数字的 (如 -E, -A, -all)
    # 文本参数：不以 - 开头，或者是类似 -3 这样的负数形式（用于指定级别）
    mode_args = [p.lower() for p in parts[1:] if p.startswith("-") and not p[1:].isdigit()]
    text_args = [p for p in parts[1:] if not p.startswith("-") or p[1:].isdigit()]
    
    return {"command": command, "text_args": text_args, "mode_args": mode_args}


class BotHandler:
    def __init__(self, service: HulaquanService):
        self.service = service


    async def _ensure_user_exists(self, user_id: str, nickname: str = ""):
        """确保用户在数据库中存在 (由于外键约束)"""
        from services.db.models import User
        try:
            with session_scope() as session:
                user = session.get(User, user_id)
                if not user:
                    # 只有 group_ 这种自定义 ID 才会在这里创建
                    # 正常用户应该在 resolve_user_id 中创建
                    user = User(user_id=user_id, nickname=nickname or user_id)
                    session.add(user)
                    session.commit()
                    log.info(f"👤 [用户] 已为 {user_id} 创建新用户记录")
                elif nickname and user.nickname != nickname:
                    # 顺便更新一下昵称
                    user.nickname = nickname
                    session.add(user)
                    session.commit()
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

    # --- Help Messages (Synced with help.html) ---
    CMD_HELP_HLQ = (
        "🔍 1. 剧目余票查询\n"
        "用法: /hlq [剧名] [参数...]\n"
        "搜索呼啦圈平台上的学生票/折扣票信息，支持按城市、价格筛选。\n\n"
        "示例:\n"
        "• 基础查询：/hlq 连璧\n"
        "• 指定城市：/hlq 时光代理人 上海\n"
        "• 指定价格：/hlq 连璧 -199 (仅看199元票档)\n"
        "• 忽略售罄：/hlq 连璧 -i (仅看有票场次)\n"
        "• 查看全部：/hlq 连璧 -all (查看全部排期)\n"
        "• 组合使用：/hlq 连璧 上海 -219 -all"
    )

    CMD_HELP_DATE = (
        "📅 2. 日期排期查询\n"
        "用法: /date [日期] [城市] [-all]\n"
        "按日期查看全站（或指定城市）的学生票演出排期。\n\n"
        "示例:\n"
        "• 查今天：/date\n"
        "• 查指定日期：/date 2026-02-14\n"
        "• 查指定城市：/date 2026-01-20 上海"
    )
    
    CMD_HELP_CAST = (
        "👥 3. 同场卡司查询\n"
        "用法: /cast [演员1] [演员2] ... [参数]\n"
        "搜索一位或多位演员的未来同场演出排期。\n\n"
        "示例:\n"
        "• 双人同场：/cast 丁辰西 陈玉婷\n"
        "• 显示同场其它卡司：/cast 陈玉婷 -o\n"
        "• 仅查此演员在呼啦圈中的场次：/cast 丁辰西 -h"
    )

    CMD_HELP_BUG = (
        "🐛 故障反馈\n"
        "用法: /bug [描述]\n"
        "示例: /bug 查排期一直没反应"
    )

    CMD_HELP_SUGGEST = (
        "💡 功能建议\n"
        "用法: /suggest [建议]\n"
        "示例: /suggest 希望增加一个按剧场搜索的功能"
    )

    CMD_HELP_SUBSCRIBE = (
        "🔔 关注订阅帮助\n"
        "实时监控呼啦圈学生票的上新、补票、回流动向。\n\n"
        "用法: /关注学生票 [关键词] [模式等级]\n"
        "示例:\n"
        "• 关注剧目(默认模式2)：/关注学生票 时光代理人 上海\n"
        "• 关注剧目(指定模式3)：/关注学生票 时光代理人 广州 3\n"
        "• 防歧义匹配：/关注学生票 -E 时光代理人 上海\n"
        "• 关注演员：/关注学生票 -A 陈玉婷\n"
        "• 关注演员(指定模式1)：/关注学生票 -A 陈玉婷 1"
    )

    CMD_HELP_UNSUBSCRIBE = (
        "🔕 取消关注帮助\n"
        "查看列表或删除已有的订阅。\n\n"
        "用法: /查看关注 或 /取消关注学生票 [关键词] [参数]\n"
        "示例:\n"
        "• 查看列表：/查看关注\n"
        "• 取消剧目：/取消关注学生票 连璧\n"
        "• 取消演员：/取消关注学生票 -A XXX"
    )

    async def _handle_set_notify_level(self, user_id: str, level: Optional[int] = None) -> str:
        """处理 /呼啦圈通知 [0-5] 命令"""
        from services.db.connection import session_scope
        from services.db.models import User
        
        if level is None:
            return (
                "🔔 呼啦圈通知设置\n\n"
                "用法: /呼啦圈通知 [0-5]\n\n"
                "提示: 设置为 0 将关闭所有推送。推荐设置为 2。"
            )

        
        if not (0 <= level <= 5):
            return "❌ 模式必须在 0-5 之间"

        
        with session_scope() as session:
            user = session.get(User, user_id)
            if user:
                user.global_notification_level = level
                # Ensure we also initialize subscription if not exists, though now settings are on User
                # For compatibility, we might still want to ensure a Subscription record exists if logic elsewhere depends on it
                # But strict setting logic depends only on User now.
                session.add(user)
                session.commit()
                
                desc = MODE_DESCRIPTIONS.get(level, "未知")
                msg = f"✅ 全局通知已设置为: 模式{level}（{desc}）"
                
                if level > 0:
                    msg += "\n\n📢 提示: 您已开启全局推送，将收到全平台该等级及以上的变动通知。\n如仅需接收已关注剧目的通知，请回复 `/呼啦圈通知 0` 关闭全局推送。"
                else:
                    msg += "\n\n💡 提示: 全局推送已关闭。您现在仅会收到已关注剧目/演员的通知。"
                
                return msg

            else:
                return "❌ 用户不存在，请先尝试使用其他命令初始化。"
    
    async def _resolve_target(self, kind: str, query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        智能解析订阅目标 (剧目或演员)
        Returns: (target_id, target_name, error_message)
        """
        from services.db.models.base import SubscriptionTargetKind
        
        results = []
        if kind == SubscriptionTargetKind.ACTOR:
            # 演员搜索
            try:
                actors = await self.service.search_actors(query)
                # 去重
                seen = set()
                results = []
                for a in actors:
                    if a.name not in seen:
                        results.append({"id": a.name, "name": a.name, "desc": "演员"}) # Actor ID is name for now
                        seen.add(a.name)
            except Exception as e:
                log.warning(f"⚠️ [Bot] Actor search failed: {e}")
                return None, None, "查询演员失败，请稍后重试。"
                
        else:
            # 剧目搜索 - 使用智能搜索逻辑
            try:
                events = await self.service.search_events_smart(query)
                results = []
                for e in events:
                    city_str = f"【{e.city}】" if e.city else ""
                    # 避免重复前缀：如果标题已经以该城市开头
                    title_display = e.title
                    if e.city and (f"【{e.city}】" in e.title or f"[{e.city}]" in e.title):
                         desc = e.title
                    else:
                         desc = f"{city_str}{e.title}"
                         
                    results.append({
                        "id": str(e.id), 
                        "name": e.title, 
                        "city": e.city,
                        "desc": desc
                    })
            except Exception as e:
                log.warning(f"⚠️ [Bot] Event search failed: {e}")
                return None, None, "查询剧目失败，请稍后重试。"

        if not results:
            kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
            return None, None, f"❌ 未找到包含 '{query}' 的{kind_name}。"
        
        # 精确匹配（如果只有一个结果，或者有完全重名的）
        if len(results) == 1:
            return results[0]["id"], results[0]["name"], None
        
        # 尝试寻找完全一致的
        perfect_matches = [r for r in results if r["name"] == query]
        if len(perfect_matches) == 1:
            return perfect_matches[0]["id"], perfect_matches[0]["name"], None
            
        # 结果过多，返回歧义消除提示
        msg = [f"🔍 找到 {len(results)} 个相关目标，请指定更精确的关键词：\n"]
        limit = 10
        for i, r in enumerate(results[:limit], 1):
             msg.append(f"{i}. {r['desc']}")
        
        if len(results) > limit:
            msg.append(f"...等 {len(results)} 个")
            
        return None, None, "\n".join(msg)

    async def _handle_subscribe(self, user_id: str, args: dict) -> str:
        """处理 /关注学生票 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionTarget
        from services.db.models.base import SubscriptionTargetKind
        from sqlmodel import select
        
        mode_args = args.get("mode_args", [])
        text_args = args.get("text_args", [])
        
        if not text_args:
            return self.CMD_HELP_SUBSCRIBE

        
        # 解析参数
        kind = SubscriptionTargetKind.PLAY  # 默认剧目
        level = 2  # 默认模式2

        
        if "-a" in mode_args:
            kind = SubscriptionTargetKind.ACTOR
        elif "-e" in mode_args or not any(arg.startswith("-") for arg in mode_args):
            kind = SubscriptionTargetKind.PLAY
        
        # 尝试解析模式 (支持 3 或 -3)

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
        
        raw_query = " ".join(text_args) if text_args else ""
        if not raw_query:
            return "❌ 请提供剧目或演员名称"
        
        # --- 智能解析 ---
        target_id, target_name, error = await self._resolve_target(kind, raw_query)
        if error:
            # 针对存在歧义的情况，改写提示示例
            if "找到" in error and "目标" in error:
                # 尝试从原始消息中复现指令和参数，引导用户添加城市
                # 提取原始指令 (CMD_SUBSCRIBE 的触发词)
                triggered_cmd = args.get("command", "/关注学生票")
                # 拼接原有参数（除了查询词本身）
                flag_str = f" {' '.join(mode_args)}" if mode_args else ""
                level_str = ""
                # 如果 level 发生了变化（非默认2），或者原始 text_args 中包含数字，尝试保留它
                # 但更简单的是：直接在提示末尾加上当前的 level
                level_str = f" {level}"

                # 寻找第一个结果城市作为推荐（在 resolve_target 内部已经按顺序排好了）
                # 这里我们假设 error 中包含了列表。我们直接在 error 末尾添加示例提示。
                prompt = "\n\n💡 示例："
                # 尝试构建：/关注学生票 [剧名] [城市] [等级]
                # 这里的 raw_query 可能是 "阿波罗尼亚"
                example = f"{triggered_cmd} {raw_query} 上海{level_str}{flag_str}"
                return f"{error}{prompt}`{example}`"
            return error
        
        # 对于演员，target_id 暂时也就是名字
        if kind == SubscriptionTargetKind.ACTOR:
             target_id = target_name
        
        with session_scope() as session:
            # 查找或创建订阅
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                sub = Subscription(user_id=user_id)
                session.add(sub)
                session.flush()
            
            # 检查是否已存在
            # 注意：这里我们使用解析后的 target_name 来查找，避免重复
            # 对于剧目，我们更应该用 target_id (event_id) 来匹配吗？
            # 现在的 SubscriptionTarget 表结构：target_id 存的是 event_id (如果是剧目)，name 是标题
            # 但之前的代码里，subscription target_id 经常存的是 name (历史遗留问题)
            # 必须保持一致性。
            # 新逻辑：
            # Play: target_id = event_id, name = event_title
            # Actor: target_id = actor_name, name = actor_name
            
            stmt_target = select(SubscriptionTarget).where(
                SubscriptionTarget.subscription_id == sub.id,
                SubscriptionTarget.kind == kind,
                # 优先匹配 target_id，如果不行匹配 name
                (SubscriptionTarget.target_id == target_id) | (SubscriptionTarget.name == target_name)
            )
            existing = session.exec(stmt_target).first()
            
            if existing:
                # 更新模式
                existing.flags = {"mode": level}
                # 确保 ID 和 Name 是最新的标准值
                existing.target_id = target_id
                existing.name = target_name
                session.add(existing)
                desc = MODE_DESCRIPTIONS.get(level, "未知")
                msg = f"✅ 已更新订阅: {target_name} 模式{level}（{desc}）"

            else:
                # 创建新订阅
                target = SubscriptionTarget(
                    subscription_id=sub.id,
                    kind=kind,
                    target_id=target_id, 
                    name=target_name,
                    flags={"mode": level}
                )
                session.add(target)
                session.add(target)
                kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
                desc = MODE_DESCRIPTIONS.get(level, "未知")
                msg = f"✅ 已成功关注{kind_name}: {target_name} 模式{level}（{desc}）"

            
            session.commit()
        
        return msg
    
    async def _handle_unsubscribe(self, user_id: str, args: dict) -> str:
        """处理 /取消关注学生票 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionTarget
        from services.db.models.base import SubscriptionTargetKind
        from sqlmodel import select, or_
        
        mode_args = args.get("mode_args", [])
        text_args = args.get("text_args", [])
        
        if not text_args:
            return self.CMD_HELP_UNSUBSCRIBE
        
        kind = SubscriptionTargetKind.PLAY
        if "-a" in mode_args:
            kind = SubscriptionTargetKind.ACTOR
        
        raw_query = " ".join(text_args)
        
        # --- 智能解析 ---
        # 即使是取消关注，也先尝试解析出标准名称/ID，这样能匹配到当初订阅的标准记录
        target_id, target_name, error_msg = await self._resolve_target(kind, raw_query)
        
        # 如果解析失败（比如数据库里没这个剧了，或者模糊匹配不到），
        # 此时是否应该 fallback 到 raw_query？
        # 用户可能订阅了一个现在已经搜不到的剧（例如已下架/过期），这时候想取消关注。
        # 如果 _resolve_target 返回 error，我们尝试降级使用 raw_query 去数据库碰碰运气。
        
        fallback_query = False
        if error_msg:
             # 如果是“未找到”，则降级；如果是“找到多个”，则直接返回错误让用户重选
             if "未找到" in error_msg:
                 fallback_query = True
                 target_id = raw_query # 假定
                 target_name = raw_query
             else:
                 return error_msg

        with session_scope() as session:
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                return "❌ 您还没有任何订阅"
            
            # 构建查询条件
            conditions = [
                SubscriptionTarget.subscription_id == sub.id,
                SubscriptionTarget.kind == kind
            ]
            
            if not fallback_query:
                # 使用解析出的 ID 和 Name 匹配
                conditions.append(
                    or_(
                        SubscriptionTarget.target_id == target_id,
                        SubscriptionTarget.name == target_name
                    )
                )
            else:
                # 使用原始查询模糊匹配 (Name like query)
                # 因为用户可能输入 "魅影" 但数据库只有 "剧院魅影" 且 _resolve_target 没搜到（假设）
                # 但一般来说 _resolve_target 应该能搜到。
                # 如果 _resolve_target 没搜到，说明库里确实没有这个剧/演员。
                # 那剩下的可能性是：用户订阅了一个不存在于当前 Hulaquan 库的词条（历史数据）。
                # 这种情况下，直接用 name == raw_query 匹配
                conditions.append(SubscriptionTarget.name == raw_query)

            stmt_target = select(SubscriptionTarget).where(*conditions)
            target = session.exec(stmt_target).first()
            
            if not target:
                kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
                search_term = target_name if not fallback_query else raw_query
                return f"❌ 未找到对{kind_name} '{search_term}' 的订阅记录。"
            
            # 记录删除的名字用于反馈
            deleted_name = target.name or target.target_id
            session.delete(target)
            session.commit()
        
        kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
        return f"✅ 已取消关注{kind_name}: {deleted_name}"
    
    async def _handle_list_subscriptions(self, user_id: str) -> str:
        """处理 /查看关注 命令"""
        from services.db.connection import session_scope
        from services.db.models import Subscription, SubscriptionTarget, HulaquanEvent
        from services.db.models.base import SubscriptionTargetKind
        from sqlmodel import select
        
        with session_scope() as session:
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            # 加载用户信息用于读取配置
            user = session.get(User, user_id)
            if not user:
                 return "❌ 用户数据异常"

            if not sub and user.global_notification_level == 0:
                return "您目前没有任何订阅。\n\n使用 /呼啦圈通知 2 开启全局通知"

            lines = ["📋 我的订阅\n"]
            
            # 显示全局设置 (unified from User table)
            desc = MODE_DESCRIPTIONS.get(user.global_notification_level, "未知")
            lines.append(f"🔔 全局通知: 模式{user.global_notification_level}（{desc}）")

            
            if user.silent_hours:
                lines.append(f"🌙 静音时段: {user.silent_hours}")
            
            if user.is_muted:
                lines.append(f"🔇 已全局静音")
            
            # 获取所有订阅目标
            stmt_targets = select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)
            targets = session.exec(stmt_targets).all()
            
            if not targets:
                lines.append("\n暂无具体订阅项")
            else:
                # 按类型分组 (兼容多种大小写和枚举格式)
                plays = [t for t in targets if t.kind in (SubscriptionTargetKind.PLAY, "play", "PLAY", "EVENT", "event")]
                actors = [t for t in targets if t.kind in (SubscriptionTargetKind.ACTOR, "actor", "ACTOR")]
                
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
                        desc = MODE_DESCRIPTIONS.get(mode, "未知")
                        lines.append(f"{i}. {display_name} 模式{mode}（{desc}）")

                
                if actors:
                    lines.append("\n【关注的演员】")
                    for i, t in enumerate(actors, 1):
                        mode = t.flags.get("mode", 2) if t.flags else 2
                        desc = MODE_DESCRIPTIONS.get(mode, "未知")
                        lines.append(f"{i}. {t.name} 模式{mode}（{desc}）")

            
            return "\n".join(lines)

    async def resolve_user_id(self, qq_id: str, nickname: str = "") -> str:
        """
        解析 QQ ID 到标准化的 6 位 User ID。
        1. 检查 UserAuthMethod 是否已存在映射。
        2. 如果不存在，自动创建一个 6 位 User ID 并建立映射。
        3. 始终返回 6 位数字 ID。
        """
        from services.db.connection import session_scope
        from services.db.models import User, UserAuthMethod
        from sqlmodel import select
        
        # 如果已经是 6 位数字 ID 或 Group ID，直接返回
        if qq_id.startswith("group_") or (len(qq_id) == 6 and qq_id.isdigit() and qq_id.startswith("0")):
             return qq_id

        try:
            with session_scope() as session:
                # 1. 查找是否存在映射
                stmt = select(UserAuthMethod).where(
                    UserAuthMethod.provider == "qq",
                    UserAuthMethod.provider_user_id == qq_id
                )
                auth = session.exec(stmt).first()
                if auth:
                    # log.info(f"🔗 [Auth] Resolved QQ {qq_id} -> User {auth.user_id}")
                    return auth.user_id
                
                # 2. 不存在映射，自动创建 standardized user
                # 检查是否此前有人直接把 QQ 号当成了 user_id (兼容历史数据，直到后续迁移脚本完成)
                legacy_user = session.get(User, qq_id)
                
                new_user_id = User.generate_next_id(session)
                log.info(f"✨ [Auth] Auto-registering new standardization for QQ {qq_id} -> User {new_user_id}")
                
                new_user = User(user_id=new_user_id, nickname=nickname or f"QQ用户_{qq_id[-4:]}")
                session.add(new_user)
                
                new_auth = UserAuthMethod(
                    user_id=new_user_id,
                    provider="qq",
                    provider_user_id=qq_id,
                    is_primary=True
                )
                session.add(new_auth)
                session.commit()
                
                # 如果存在 legacy_user，可能需要在这里合并，但为了安全，我们后续用统一迁移脚本处理。
                # 目前先返回新分配的 ID。
                
                return new_user_id
                
        except Exception as e:
             log.error(f"❌ [Auth] Failed to resolve or create user for {qq_id}: {e}")
             # Fallback 保证系统不崩溃，但在标准化后，这里理论上不应该发生
             return qq_id

    async def handle_message(self, message: str, user_id: str, nickname: str = "") -> Optional[Union[str, List[str]]]:
        return await self.handle_group_message(0, int(user_id), message, nickname=nickname)

    async def handle_group_message(self, group_id: int, user_id: int, message: str, sender_role: str = "member", nickname: str = "") -> Optional[Union[str, List[str]]]:
        msg = message.strip()
        uid_str = str(user_id)
        
        log.info(f"💬 [消息] 收到来自 {user_id} 的消息: {msg}")
        
        # --- 提前解析参数，避免各分支重复解析及 UnboundLocalError ---
        args = extract_args(msg)
        mode_args = args["mode_args"]
        text_args = args["text_args"]
        
        command = args["command"]
        
        # --- Help Command ---
        if command == "/help":
            return self._get_help_text()
        
        # --- Auth / Login ---
        if command == "/web":
            # For login token, we act on the raw QQ ID to let them link it
            token = create_magic_link_token(uid_str, nickname)
            link = f"{WEB_BASE_URL}/auth/magic-link?token={token}"
            return [
                (
                    f"🔐 点击下方链接登录 Web 控制台（5分钟内有效）：\n\n"
                    f"✨ 登录后可查看完整演出信息、管理订阅等\n\n"
                    f"💡 提示：如在 QQ 内打开遇到问题，请复制链接到外部浏览器"
                ),
                link
            ]

        # --- 权限与目标确定 ---
        is_root = str(user_id) == ROOT_ID
        if is_root and group_id != 0:
            effective_uid = f"group_{group_id}"
            target_desc = f"当前群组 ({group_id})"
            await self._ensure_user_exists(effective_uid, nickname=f"群组 {group_id}")
        else:
            # Resolve to canonical User ID if linked, otherwise create
            effective_uid = await self.resolve_user_id(uid_str, nickname=nickname)
            target_desc = "个人"
            # resolve_user_id 已经确保了 user 存在，这里仅用于 group 或后续可能的更新
            if effective_uid.startswith("group_"):
                await self._ensure_user_exists(effective_uid, nickname=nickname)

        # --- 订阅管理命令 ---
        # /呼啦圈通知 [0-5]
        if command == "/呼啦圈通知":
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
        if command == "/关注学生票":
            response = await self._handle_subscribe(effective_uid, args)
            if effective_uid.startswith("group_"):
                response = response.replace("✅ ", f"✅ [群订阅] ")
            return response
        
        # /取消关注学生票
        if command == "/取消关注学生票":
            response = await self._handle_unsubscribe(effective_uid, args)
            if effective_uid.startswith("group_"):
                response = response.replace("✅ ", f"✅ [群订阅] ")
            return response
        
        # /查看关注
        if command == "/查看关注":
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
        if command == "/date":
            date_str = text_args[0] if text_args else datetime.now().strftime("%Y-%m-%d")
            city = text_args[1] if len(text_args) > 1 else None
            return await self._handle_date(date_str, city, show_all)

        # --- /hlq Command ---
        # --- /hlq Command ---
        if command == "/hlq":
            query = " ".join(text_args)
            if not query:
                return self.CMD_HELP_HLQ
            
            ignore_sold_out = "-i" in mode_args
            return await self._handle_hlq(query, show_all, price_filters, ignore_sold_out=ignore_sold_out)

        # --- /同场演员 Command ---
        if command == "/同场演员" or command == "/cast":
            actors = text_args
            if not actors:
                return self.CMD_HELP_CAST
            show_others = "-o" in mode_args
            use_hulaquan = "-h" in mode_args
            return await self._handle_cocast(actors, show_others, use_hulaquan)

        # --- /bug Command ---
        if command == "/bug":
            content = " ".join(text_args)
            if not content: return self.CMD_HELP_BUG
            return await self._handle_bug(user_id, nickname, content)

        # --- /suggest Command ---
        if command == "/suggest":
            content = " ".join(text_args)
            if not content: return self.CMD_HELP_SUGGEST
            return await self._handle_suggest(user_id, nickname, content)

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
            f"• 反馈Bug: /bug [问题描述]\n"
            f"• 提建议: /suggest [建议内容]\n"
            f"• 登录Web: /web"
        )

    # --- Command Implementations ---

    async def _handle_bug(self, user_id: int, nickname: str, content: str) -> str:
        """处理 /bug 命令"""
        if not content:
            return "❌ 请提供 Bug 描述，例如: /bug 查询排期时报错"
            
        from services.db.connection import session_scope
        from services.db.models import Feedback
        
        try:
            with session_scope() as session:
                feedback = Feedback(
                    contact=f"QQ:{user_id} ({nickname})",
                    type="bug",
                    content=content
                )
                session.add(feedback)
                session.commit()
                # 刷新以获取 ID
                session.refresh(feedback)
                return f"🐛 已收到您的 Bug 反馈。编号: #{feedback.id}\n我们会尽快排查，感谢您的支持！"
        except Exception as e:
            log.error(f"❌ Failed to save bug report: {e}")
            return "❌ 提交失败，请稍后重试。"

    async def _handle_suggest(self, user_id: int, nickname: str, content: str) -> str:
        """处理 /suggest 命令"""
        if not content:
            return "❌ 请提供建议内容，例如: /suggest 希望增加夜间模式"
            
        from services.db.connection import session_scope
        from services.db.models import Feedback
        
        try:
            with session_scope() as session:
                feedback = Feedback(
                    contact=f"QQ:{user_id} ({nickname})",
                    type="suggestion",
                    content=content
                )
                session.add(feedback)
                session.commit()
                session.refresh(feedback)
                return f"💡 已收到您的建议。编号: #{feedback.id}\n感谢您帮助我们改进！"
        except Exception as e:
            log.error(f"❌ Failed to save suggestion: {e}")
            return "❌ 提交失败，请稍后重试。"

    async def _handle_date(self, date_str: str, city: Optional[str], show_all: bool) -> str:
        """处理 /date 命令"""
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return self.CMD_HELP_DATE
        
        results = await self.service.get_events_by_date(target_date, city)
        
        if not results:
            return f"📅 {date_str} 暂无收录的学生票演出信息。"
        
        return HulaquanFormatter.format_date_events(target_date, results, show_all=show_all)

    async def _handle_hlq(self, query: str, show_all: bool, price_filters: List[float] = None, ignore_sold_out: bool = False) -> str:
        """处理 /hlq 命令"""
        # 1. 采用统一的智能搜索
        results = await self.service.search_events_smart(query)
        
        if not results:
            return f"❌ 未找到包含 '{query}' 的剧目。"
        
        # 2. 如果结果仍多于1个，且没有足够精确，提示用户（保持交互一致性）
        if len(results) > 1:
            # 如果存在完全一致的剧名，直接展示第一个详情（或者提示用户选择？）
            # 为了一致性，我们也返回选择列表
            msg = [f"🔍 找到 {len(results)} 个相关剧目，请通过城市进一步筛选：\n"]
            for i, event in enumerate(results, 1):
                city_str = f"【{event.city}】" if event.city else ""
                if event.city and (f"【{event.city}】" in event.title or f"[{event.city}]" in event.title):
                    display = event.title
                else:
                    display = f"{city_str}{event.title}"
                msg.append(f"{i}. {display}")
            
            # 提供示例引导
            first_city = results[0].city or "上海"
            msg.append(f"\n💡 示例：`/hlq {query} {first_city}`")
            return "\n".join(msg)
        
        # 3. 只有一个结果，返回详情
        event = results[0]
        
        # 应用忽略售罄筛选
        if ignore_sold_out:
            event.tickets = [t for t in event.tickets if t.stock > 0]
            if not event.tickets:
                return f"🔍 《{event.title}》 所有学生票场次均已售罄 (使用 -all 查看或去除 -i)"

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
                results = await self.service.saoju.match_co_casts(
                    actors, show_others=show_others, start_date=start_date
                )
                
                if not results:
                    return f"👥 未找到 {actors_str} 在 {start_date} 之后的同台演出。"
                
                web_link = f"{WEB_BASE_URL}/?tab=cocast&actors={','.join(actors)}"
                return HulaquanFormatter.format_co_casts(results, limit=30, show_link=web_link)
            except Exception as e:
                log.error(f"Saoju co-cast search failed: {e}")
                return "查询失败，扫剧系统可能暂时不可用。"
