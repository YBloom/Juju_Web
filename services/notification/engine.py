import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Set

from sqlmodel import Session, select, col

from services.db.connection import get_engine, session_scope
from services.db.models import (
    User, Subscription, SubscriptionTarget, SubscriptionOption,
    SendQueue, SendQueueStatus, SubscriptionTargetKind
)
from services.hulaquan.tables import TicketUpdateLog, HulaquanCast, TicketCastAssociation
from services.hulaquan.formatter import HulaquanFormatter
from services.hulaquan.models import TicketUpdate

log = logging.getLogger(__name__)

# Constants
MAX_RETRY_COUNT = 3
BACKFILL_HOURS = 24  #补发时限

# MODE 映射 (复用旧版逻辑)
MODE_MAP = {
    "new": 1,
    "restock": 1,
    "pending": 2,
    "back": 3,
    "sold_out": 3,
}


class NotificationEngine:
    """
    通知引擎 - 将 TicketUpdate 匹配订阅并入队发送。
    
    用法:
        engine = NotificationEngine()
        await engine.process_updates(updates)
    """
    
    def __init__(self, bot_api=None):
        """
        Args:
            bot_api: ncatbot BotClient.api instance for sending messages
        """
        self.bot_api = bot_api
        self.formatter = HulaquanFormatter
    
    async def process_updates(self, updates: List[TicketUpdate]) -> int:
        """
        处理 sync_all_data 返回的更新，匹配订阅并入队。
        
        Args:
            updates: List of TicketUpdate from sync_all_data
            
        Returns:
            Number of notifications enqueued
        """
        if not updates:
            return 0
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._process_updates_sync, updates)
    
    def _process_updates_sync(self, updates: List[TicketUpdate]) -> int:
        """同步版本的处理逻辑。"""
        enqueued = 0
        
        with session_scope() as session:
            # 1. 收集涉及的 event_ids 和 actor 名
            event_ids: Set[str] = set()
            actor_names: Set[str] = set()
            
            for u in updates:
                if u.event_id:
                    event_ids.add(str(u.event_id))
                if u.cast_names:
                    actor_names.update(u.cast_names)
            
            # 2. 查询所有有订阅的用户
            stmt = select(Subscription.user_id).distinct()
            user_ids = session.exec(stmt).all()
            
            for user_id in user_ids:
                # 获取用户订阅
                stmt_sub = select(Subscription).where(Subscription.user_id == user_id)
                subs = session.exec(stmt_sub).all()
                
                if not subs:
                    continue
                
                # 获取第一个订阅的 options
                sub = subs[0]
                stmt_opt = select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)
                option = session.exec(stmt_opt).first()
                
                # 检查静音
                if option and option.mute:
                    continue
                
                # 检查静默时段
                if option and option.silent_hours and self._is_silent_hour(option.silent_hours):
                    continue
                
                # 获取所有 targets
                all_targets = []
                for s in subs:
                    stmt_t = select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == s.id)
                    all_targets.extend(session.exec(stmt_t).all())
                
                # 匹配更新
                user_updates = []
                for u in updates:
                    if self._match_update(u, all_targets, event_ids, actor_names):
                        user_updates.append(u)
                
                if user_updates:
                    # 入队
                    enqueued += self._enqueue_notification(session, user_id, user_updates)
            
            session.commit()
        
        log.info(f"NotificationEngine: enqueued {enqueued} notifications for {len(updates)} updates")
        return enqueued
    
    def _match_update(
        self, 
        update: TicketUpdate, 
        targets: List[SubscriptionTarget],
        event_ids: Set[str],
        actor_names: Set[str]
    ) -> bool:
        """检查 update 是否匹配用户的任一订阅 target。"""
        required_mode = MODE_MAP.get(update.change_type, 99)
        
        for target in targets:
            # 从 flags 中获取 mode，默认为 1
            mode = 1
            if target.flags and "mode" in target.flags:
                mode = target.flags["mode"]
            
            if mode < required_mode:
                continue
            
            # 按类型匹配
            if target.kind == SubscriptionTargetKind.PLAY:
                if target.target_id == str(update.event_id):
                    return True
            elif target.kind == SubscriptionTargetKind.ACTOR:
                if update.cast_names and target.name in update.cast_names:
                    return True
            elif target.kind == SubscriptionTargetKind.KEYWORD:
                if target.name and update.event_title and target.name in update.event_title:
                    return True
        
        return False
    
    def _is_silent_hour(self, silent_hours: str) -> bool:
        """检查当前是否在静默时段内。格式: '23:00-08:00'"""
        try:
            parts = silent_hours.split("-")
            if len(parts) != 2:
                return False
            
            now = datetime.now()
            start_h, start_m = map(int, parts[0].split(":"))
            end_h, end_m = map(int, parts[1].split(":"))
            
            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            
            if start_minutes <= end_minutes:
                # Same day range (e.g., 09:00-17:00)
                return start_minutes <= current_minutes <= end_minutes
            else:
                # Overnight range (e.g., 23:00-08:00)
                return current_minutes >= start_minutes or current_minutes <= end_minutes
        except Exception:
            return False
    
    def _enqueue_notification(self, session: Session, user_id: str, updates: List[TicketUpdate]) -> int:
        """将通知入队到 SendQueue。"""
        # 格式化消息
        # 使用 Hybrid 模式生成精简消息
        messages = []
        for u in updates:
            messages.append({
                "event_id": u.event_id,
                "event_title": u.event_title,
                "change_type": u.change_type,
                "message": u.message,
                "ticket_id": u.ticket_id,
            })
        
        # 检查是否已存在相同 ref_id (防重复)
        # 使用第一个 update 的 ticket_id 作为 ref
        ref_id = f"batch_{updates[0].ticket_id}_{datetime.now().strftime('%Y%m%d%H')}"
        
        stmt = select(SendQueue).where(
            SendQueue.user_id == user_id,
            SendQueue.ref_id == ref_id,
            SendQueue.status.in_([SendQueueStatus.PENDING, SendQueueStatus.SENT])
        )
        if session.exec(stmt).first():
            log.debug(f"Skipping duplicate notification for user {user_id}, ref {ref_id}")
            return 0
        
        queue_item = SendQueue(
            user_id=user_id,
            channel="qq_private",
            scope="ticket_update",
            payload={"updates": messages},
            status=SendQueueStatus.PENDING,
            ref_id=ref_id,
        )
        session.add(queue_item)
        return 1
    
    async def consume_queue(self, limit: int = 50) -> int:
        """
        消费发送队列，发送待发送的通知。
        
        Returns:
            Number of messages sent
        """
        if not self.bot_api:
            log.warning("Bot API not configured, skipping queue consumption")
            return 0
        
        # --- Safety: Test Whitelist ---
        # If TEST_USER_WHITELIST is set (comma-separated IDs), only send to these users.
        whitelist_str = os.getenv("TEST_USER_WHITELIST", "")
        whitelist = set(whitelist_str.split(",")) if whitelist_str else set()
        
        loop = asyncio.get_running_loop()
        pending_items = await loop.run_in_executor(None, self._get_pending_items, limit)
        
        sent_count = 0
        for item in pending_items:
            try:
                # Check whitelist
                if whitelist and str(item.user_id) not in whitelist:
                    log.info(f"SAFE MODE: Skipping notification for non-whitelisted user {item.user_id}")
                    # Mark as sent to remove from queue without actually sending
                    await loop.run_in_executor(None, self._mark_sent, item.id)
                    continue

                # 格式化消息
                payload = item.payload or {}
                updates_data = payload.get("updates", [])
                
                if not updates_data:
                    await loop.run_in_executor(None, self._mark_sent, item.id)
                    continue
                
                # 生成消息文本
                lines = [f"📢 票务动态 ({len(updates_data)} 条)"]
                for u in updates_data[:5]:  # 最多显示 5 条
                    lines.append(f"• {u.get('message', '')}")
                if len(updates_data) > 5:
                    lines.append(f"... 还有 {len(updates_data) - 5} 条")
                
                text = "\n".join(lines)
                
                # 发送
                await self.bot_api.post_private_msg(int(item.user_id), text=text)
                await loop.run_in_executor(None, self._mark_sent, item.id)
                sent_count += 1
                
            except Exception as e:
                log.error(f"Failed to send notification to {item.user_id}: {e}")
                await loop.run_in_executor(None, self._mark_failed, item.id, str(e))
        
        return sent_count
    
    def _get_pending_items(self, limit: int) -> List[SendQueue]:
        """获取待发送的队列项。"""
        from sqlmodel import or_
        with session_scope() as session:
            now = datetime.now()
            stmt = select(SendQueue).where(
                SendQueue.status.in_([SendQueueStatus.PENDING, SendQueueStatus.RETRYING]),
                or_(
                    SendQueue.next_retry_at == None,
                    col(SendQueue.next_retry_at) <= now
                ),
                SendQueue.retry_count < MAX_RETRY_COUNT,
            ).order_by(SendQueue.created_at).limit(limit)
            
            items = session.exec(stmt).all()
            # Detach from session
            return [SendQueue.model_validate(item) for item in items]
    
    def _mark_sent(self, item_id: int):
        """标记为已发送。"""
        with session_scope() as session:
            item = session.get(SendQueue, item_id)
            if item:
                item.status = SendQueueStatus.SENT
                item.sent_at = datetime.now()
                session.add(item)
                session.commit()
    
    def _mark_failed(self, item_id: int, error: str):
        """标记为失败，设置重试。"""
        with session_scope() as session:
            item = session.get(SendQueue, item_id)
            if item:
                item.retry_count += 1
                item.error_message = error[:500] if error else None
                
                if item.retry_count >= MAX_RETRY_COUNT:
                    item.status = SendQueueStatus.FAILED
                else:
                    item.status = SendQueueStatus.RETRYING
                    # 指数退避: 1min, 5min, 15min
                    delay_minutes = [1, 5, 15][min(item.retry_count - 1, 2)]
                    item.next_retry_at = datetime.now() + timedelta(minutes=delay_minutes)
                
                session.add(item)
                session.commit()
