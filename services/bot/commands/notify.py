import logging
from typing import List, Union, Optional, Tuple
from sqlmodel import select, or_

from services.bot.commands.base import CommandHandler, CommandContext
from services.bot.commands.registry import register_command
from services.db.models import Subscription, SubscriptionTarget, User, HulaquanEvent
from services.db.models.base import SubscriptionTargetKind
from services.notification.config import MODE_DESCRIPTIONS

log = logging.getLogger(__name__)

async def resolve_target(ctx: CommandContext, kind: str, query: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    智能解析订阅目标 (剧目或演员)
    Returns: (target_id, target_name, error_message)
    """
    # Note: Import SubscriptionTargetKind inside function if circular import, 
    # but here we are in notify.py, depends on models. Should be fine if models don't import notify.
    
    results = []
    if kind == SubscriptionTargetKind.ACTOR:
        # 演员搜索
        try:
            actors = await ctx.service.search_actors(query)
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
            events = await ctx.service.search_events_smart(query)
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

@register_command
class SubscribeCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/关注学生票", "/关注", "/sub", "关注", "订阅"]

    @property
    def help_text(self) -> str:
        return (
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

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        mode_args = ctx.mode_args
        text_args = ctx.text_args
        
        if not text_args:
            return self.help_text

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
        target_id, target_name, error = await resolve_target(ctx, kind, raw_query)
        if error:
            # 针对存在歧义的情况，改写提示示例
            if "找到" in error and "目标" in error:
                # 尝试构建完整指令提示
                triggered_cmd = ctx.command
                flag_str = f" {' '.join(mode_args)}" if mode_args else ""
                level_str = f" {level}"
                prompt = "\n\n💡 示例："
                example = f"{triggered_cmd} {raw_query} 上海{level_str}{flag_str}"
                return f"{error}{prompt}`{example}`"
            return error
        
        # 对于演员，target_id 暂时也就是名字
        if kind == SubscriptionTargetKind.ACTOR:
             target_id = target_name
        
        with ctx.session_maker() as session:
            # 查找或创建订阅
            stmt = select(Subscription).where(Subscription.user_id == ctx.user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                sub = Subscription(user_id=ctx.user_id)
                session.add(sub)
                session.flush()
            
            # 检查是否已存在
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
                kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
                desc = MODE_DESCRIPTIONS.get(level, "未知")
                msg = f"✅ 已成功关注{kind_name}: {target_name} 模式{level}（{desc}）"

            session.commit()
        
        return msg

@register_command
class UnsubscribeCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/取消关注学生票", "/取消关注", "/unsub", "取消关注", "退订"]

    @property
    def help_text(self) -> str:
        return (
            "🔕 取消关注帮助\n"
            "查看列表或删除已有的订阅。\n\n"
            "用法: /查看关注 或 /取消关注学生票 [关键词] [参数]\n"
            "示例:\n"
            "• 查看列表：/查看关注\n"
            "• 取消剧目：/取消关注学生票 连璧\n"
            "• 取消演员：/取消关注学生票 -A XXX"
        )

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        mode_args = ctx.mode_args
        text_args = ctx.text_args
        
        if not text_args:
            return self.help_text
        
        kind = SubscriptionTargetKind.PLAY
        if "-a" in mode_args:
            kind = SubscriptionTargetKind.ACTOR
        
        raw_query = " ".join(text_args)
        
        # --- 智能解析 ---
        target_id, target_name, error_msg = await resolve_target(ctx, kind, raw_query)
        
        fallback_query = False
        if error_msg:
             if "未找到" in error_msg:
                 fallback_query = True
                 target_id = raw_query # 假定
                 target_name = raw_query
             else:
                 return error_msg

        with ctx.session_maker() as session:
            stmt = select(Subscription).where(Subscription.user_id == ctx.user_id)
            sub = session.exec(stmt).first()
            
            if not sub:
                return "❌ 您还没有任何订阅"
            
            # 构建查询条件
            conditions = [
                SubscriptionTarget.subscription_id == sub.id,
                SubscriptionTarget.kind == kind
            ]
            
            if not fallback_query:
                conditions.append(
                    or_(
                        SubscriptionTarget.target_id == target_id,
                        SubscriptionTarget.name == target_name
                    )
                )
            else:
                conditions.append(SubscriptionTarget.name == raw_query)

            stmt_target = select(SubscriptionTarget).where(*conditions)
            target = session.exec(stmt_target).first()
            
            if not target:
                kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
                search_term = target_name if not fallback_query else raw_query
                return f"❌ 未找到对{kind_name} '{search_term}' 的订阅记录。"
            
            deleted_name = target.name or target.target_id
            session.delete(target)
            session.commit()
        
        kind_name = "演员" if kind == SubscriptionTargetKind.ACTOR else "剧目"
        return f"✅ 已取消关注{kind_name}: {deleted_name}"

@register_command
class ListSubscriptionsCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/查看关注", "/list", "/我的订阅", "/订阅列表", "我的订阅", "查看关注"]

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        user_id = ctx.user_id
        with ctx.session_maker() as session:
            stmt = select(Subscription).where(Subscription.user_id == user_id)
            sub = session.exec(stmt).first()
            
            user = session.get(User, user_id)
            if not user:
                 return "❌ 用户数据异常"

            if not sub and user.global_notification_level == 0:
                return "您目前没有任何订阅。\n\n使用 /呼啦圈通知 2 开启全局通知"

            lines = ["📋 我的订阅\n"]
            
            desc = MODE_DESCRIPTIONS.get(user.global_notification_level, "未知")
            lines.append(f"🔔 全局通知: 模式{user.global_notification_level}（{desc}）")

            if user.silent_hours:
                lines.append(f"🌙 静音时段: {user.silent_hours}")
            
            if user.is_muted:
                lines.append(f"🔇 已全局静音")
            
            if not sub:
                lines.append("\n暂无具体订阅项")
            else:
                stmt_targets = select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)
                targets = session.exec(stmt_targets).all()
                
                if not targets:
                    lines.append("\n暂无具体订阅项")
                else:
                    plays = [t for t in targets if t.kind in (SubscriptionTargetKind.PLAY, "play", "PLAY", "EVENT", "event")]
                    actors = [t for t in targets if t.kind in (SubscriptionTargetKind.ACTOR, "actor", "ACTOR")]
                    
                    if plays:
                        lines.append("\n【关注的剧目】")
                        for i, t in enumerate(plays, 1):
                            display_name = t.name
                            if not display_name:
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


@register_command
class GlobalNotifyLevelCommand(CommandHandler):
    @property
    def triggers(self) -> List[str]:
        return ["/呼啦圈通知", "/notify", "设置通知", "通知设置"]

    async def handle(self, ctx: CommandContext) -> Union[str, List[str]]:
        level = None
        if ctx.text_args:
            try:
                level = int(ctx.text_args[0])
            except ValueError:
                pass

        if level is None:
            return (
                "🔔 呼啦圈通知设置\n\n"
                "用法: /呼啦圈通知 [0-5]\n\n"
                "提示: 设置为 0 将关闭所有推送。推荐设置为 2。"
            )

        if not (0 <= level <= 5):
            return "❌ 模式必须在 0-5 之间"

        with ctx.session_maker() as session:
            user = session.get(User, ctx.user_id)
            if user:
                user.global_notification_level = level
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
