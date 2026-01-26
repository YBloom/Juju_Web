import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Set

from sqlmodel import Session, select, col

from services.db.connection import get_engine, session_scope
from services.db.models import (
    SendQueue,
    SendQueueStatus,
    Subscription,
    SubscriptionOption,
    SubscriptionTarget,
    User,
    UserAuthMethod,
)
from services.db.models.base import SubscriptionTargetKind
from services.hulaquan.tables import TicketUpdateLog, HulaquanCast, TicketCastAssociation
from services.hulaquan.models import TicketUpdate
from services.notification.config import CHANGE_TYPE_LEVEL_MAP

log = logging.getLogger(__name__)

# Constants
MAX_RETRY_COUNT = 3
BACKFILL_HOURS = 24  #补发时限




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
        from services.hulaquan.formatter import HulaquanFormatter
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
        """同步版本的处理逻辑 (Optimized with Reverse Index)."""
        enqueued = 0
        
        # 1. Prepare Match Criteria
        # 1. 准备匹配标准
        # Filter updates that actually need notification
        valid_updates = [u for u in updates if u.change_type in CHANGE_TYPE_LEVEL_MAP]
        if not valid_updates:
            return 0
            
        with session_scope() as session:
            # 2. Get Candidate Users (Inverted Index Lookup)
            # 2. 获取候选用户（反向索引查找）
            # Instead of iterating all users, we find users who MIGHT be interested
            # 取代遍历所有用户，我们查找可能感兴趣的用户
            candidate_users = self._get_candidate_users(session, valid_updates)
            
            log.info(f"NotificationEngine: identified {len(candidate_users)} candidate users for {len(valid_updates)} updates")
            
            # 3. Process Only Candidates
            # 3. 仅处理候选人
            for user in candidate_users:
                # --- User Level Global Filter ---
                if user.is_muted:
                    continue
                
                if user.silent_hours and self._is_silent_hour(user.silent_hours):
                    continue
                
                # Collect targets (Eager loaded)
                all_targets = []
                for s in user.subscriptions:
                    all_targets.extend(s.targets)
                
                # Match
                # Note: We reuse the robust per-update match logic to ensure precise filtering
                # (e.g., checking specific levels, flags, regex etc.)
                user_updates = []
                for u in valid_updates:
                    if self._match_update(u, all_targets, global_level=user.global_notification_level):
                        user_updates.append(u)
                
                if user_updates:
                    enqueued += self._enqueue_notification(session, user.user_id, user_updates)
            
            session.commit()

        log.info(f"NotificationEngine: enqueued {enqueued} notifications")
        return enqueued

    def _get_candidate_users(self, session: Session, updates: List[TicketUpdate]) -> List[User]:
        """
        Efficiently find users who are interested in the given updates.
        Returns a list of User objects with subscriptions eager loaded.
        """
        from sqlalchemy import or_, and_, distinct
        from sqlalchemy.orm import joinedload
        from services.db.models import Subscription, User
        
        # Criteria Extraction
        event_ids = {str(u.event_id) for u in updates if u.event_id}
        # Cast names: flattening list of lists
        actor_names = set()
        for u in updates:
            if u.cast_names:
                actor_names.update(u.cast_names)
        
        # Min level required for ANY update in this batch
        # If a user has global_level >= min_level, they are a candidate regarding global sub
        # BUT: Use caution. If batch has "new" (level 1) and "sold_out"(level 99),
        # min is 1. We fetch all users with level >= 1.
        # This is correct because if they have level 1, they *might* want the "new" update.
        levels = [CHANGE_TYPE_LEVEL_MAP.get(u.change_type, 99) for u in updates]
        min_level = min(levels) if levels else 99
        
        # 1. Global Subscribers Condition
        # Users who want *some* notifications globally
        # global_notification_level >= min_level required by batch
        # Optim: Only if min_level is reasonable. If min_level is 99 (e.g. only sold_out), few users match.
        cond_global = (User.global_notification_level >= min_level)
        
        # 2. Targeted Subscribers Condition
        # Users who have a subscription matching event_id or actor_name
        # Note: We join User -> Subscription -> SubscriptionTarget
        
        cond_targets = []
        
        # Play ID Match
        if event_ids:
            cond_targets.append(
                and_(
                    SubscriptionTarget.kind == SubscriptionTargetKind.PLAY,
                    SubscriptionTarget.target_id.in_(event_ids)
                )
            )
            
        # Actor Name Match
        if actor_names:
            cond_targets.append(
                and_(
                    SubscriptionTarget.kind == SubscriptionTargetKind.ACTOR,
                    SubscriptionTarget.name.in_(actor_names)
                )
            )
            
        # Keyword Match (Optional / Harder to reverse index purely)
        # If we have keywords, we might skip optimizing them in SQL OR assume keywords are rare enough
        # OR fetch users with *any* keyword subscription?
        # For safety/completeness: Include users with ANY keyword subscription?
        # Or better: check keyword logic.
        # Let's assume for high performance valid_updates usually trigger Play/Actor.
        # Adding "OR has keyword subscription" might select many users. 
        # But let's add it if we want 100% correctness for keywords.
        # Compromise: Users with keyword subscriptions are candidates, we filter in memory.
        cond_targets.append(SubscriptionTarget.kind == SubscriptionTargetKind.KEYWORD)

        
        # Construct Query
        # We need users meeting cond_global OR (having subscription meeting cond_targets)
        
        # SQLModel/SQLAlchemy construction
        # Select User where (cond_global) OR (User.id IN (Select user_id from sub JOIN target where cond_target))
        
        stmt = (
            select(User)
            .where(User.active == True) # Basic filter
            .outerjoin(User.subscriptions)
            .outerjoin(Subscription.targets)
            .options(
                joinedload(User.subscriptions).joinedload(Subscription.targets)
            )
            .where(
                or_(
                    cond_global,
                    or_(*cond_targets) if cond_targets else False
                )
            )
            .distinct()
        )

        return session.exec(stmt).unique().all()
    
    def _match_update(
        self, 
        update: TicketUpdate, 
        targets: List[SubscriptionTarget],
        global_level: int = 0
    ) -> bool:
        """检查 update 是否匹配。逻辑：(全局达标) OR (特定关注匹配且关注等级达标)。"""
        required_mode = CHANGE_TYPE_LEVEL_MAP.get(update.change_type, 99)
        
        # 1. 检查全局基准 (Global Baseline)
        if global_level >= required_mode:
            return True
            
        # 2. 如果全局不达标，检查是否有特定的“高等级订阅”覆盖
        for target in targets:
            # 确定当前 target 的有效等级覆盖 (Override)
            target_mode = target.flags.get("mode", 1) if target.flags else 1
            if target_mode < required_mode:
                continue
            
            # 按类型匹配
            if target.kind == SubscriptionTargetKind.PLAY:
                # ID 匹配或名称匹配
                if target.target_id == str(update.event_id):
                    return True
                search_term = target.target_id or target.name
                if search_term and update.event_title and search_term in update.event_title:
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
        messages = []
        for u in updates:
            # [Refactor] 使用 Pydantic model_dump 确保 schema 一致性，禁止手写 Dict
            # 排除 None 值可能有助于减少 payload 大小，但为了前端/消费者能获取明确的 null，这里保留 defaults
            # mode='json' 会自动处理 datetime 序列化
            messages.append(u.model_dump(mode='json'))
        
        # 检查是否已存在相同 ref_id (防瞬时故障刷屏)
        # 修正：去重因子加入 change_type，且不再使用小时级限制，改为分钟级
        # 如果是极高频变动，允许消息下发
        ref_id = f"{user_id}_{updates[0].ticket_id}_{updates[0].change_type}_{datetime.now().strftime('%Y%m%d%H%M')}"
        
        stmt = select(SendQueue).where(
            SendQueue.user_id == user_id,
            SendQueue.ref_id == ref_id,
            SendQueue.status.in_([SendQueueStatus.PENDING, SendQueueStatus.SENT])
        )
        if session.exec(stmt).first():
            log.debug(f"Skipping redundant notification for user {user_id}, ref {ref_id}")
            return 0
        
        # Determine channel
        channel = "qq_group" if user_id.startswith("group_") else "qq_private"

        queue_item = SendQueue(
            user_id=user_id,
            channel=channel,
            scope="ticket_update",
            payload={"updates": messages},
            status=SendQueueStatus.PENDING,
            ref_id=ref_id,
        )
        session.add(queue_item)
        return 1
    
    async def consume_queue(self, limit: int = 50) -> int:
        """
        消费发送队列,发送待发送的通知。
        
        Returns:
            Number of messages sent
        """
        if not self.bot_api:
            log.warning("Bot API not configured, skipping queue consumption")
            return 0
        
        # --- Safety: Test Whitelist ---
        whitelist_str = os.getenv("TEST_USER_WHITELIST", "")
        whitelist = set(whitelist_str.split(",")) if whitelist_str else set()
        
        loop = asyncio.get_running_loop()
        pending_items = await loop.run_in_executor(None, self._get_pending_items, limit)
        
        sent_count = 0
        for item in pending_items:
            try:
                target_id = None
                is_group = item.channel == "qq_group"
                
                if is_group:
                    target_id = item.user_id.replace("group_", "")
                else:
                    # 通过UserAuthMethod查询QQ号
                    qq_id = await loop.run_in_executor(None, self._get_qq_number, item.user_id)
                    
                    if not qq_id:
                        log.warning(f"User {item.user_id} has no QQ binding, skipping notification")
                        await loop.run_in_executor(None, self._mark_sent, item.id)
                        continue
                    
                    # Check whitelist
                    if whitelist and str(qq_id) not in whitelist:
                        log.info(f"SAFE MODE: Skipping notification for non-whitelisted QQ {qq_id}")
                        await loop.run_in_executor(None, self._mark_sent, item.id)
                        continue
                    target_id = qq_id

                # 格式化消息
                payload = item.payload or {}
                updates_data = payload.get("updates", [])
                
                if not updates_data:
                    await loop.run_in_executor(None, self._mark_sent, item.id)
                    continue
                
                # 生成消息文本 (使用旧版富文本格式)
                text = self.formatter.format_send_queue_payload(updates_data)
                
                # 如果格式化失败或为空（理论上不应发生），回退到简单格式
                if not text:
                    lines = [f"📢 票务动态 ({len(updates_data)} 条)"]
                    for u in updates_data[:5]:
                        lines.append(f"• {u.get('message', '')}")
                    text = "\n".join(lines)
                
                # 发送
                if is_group:
                    await self.bot_api.post_group_msg(group_id=int(target_id), text=text)
                else:
                    await self.bot_api.post_private_msg(int(target_id), text=text)
                    
                await loop.run_in_executor(None, self._mark_sent, item.id)
                sent_count += 1
                
            except Exception as e:
                log.error(f"Failed to send notification to {item.user_id}: {e}")
                await loop.run_in_executor(None, self._mark_failed, item.id, str(e))
        
        return sent_count
    
    def _get_pending_items(self, limit: int) -> List[SendQueue]:
        """获取待发送的队列项。"""
        with session_scope() as db:
            stmt = (
                select(SendQueue)
                .where(
                    SendQueue.status == SendQueueStatus.PENDING,
                    (SendQueue.next_retry_at.is_(None)) | (SendQueue.next_retry_at <= datetime.now()),
                )
                .order_by(SendQueue.created_at)
                .limit(limit)
            )
            results = list(db.exec(stmt).all())
            for item in results:
                db.expunge(item)
            return results
    
    def _get_qq_number(self, user_id: str) -> Optional[str]:
        """通过UserAuthMethod查询用户的QQ号。
        
        Args:
            user_id: 用户的数字ID (如 "000001")
            
        Returns:
            QQ号字符串,如果未绑定QQ则返回None
        """
        with session_scope() as db:
            stmt = select(UserAuthMethod).where(
                UserAuthMethod.user_id == user_id,
                UserAuthMethod.provider == "qq"
            )
            auth_method = db.exec(stmt).first()
            return auth_method.provider_user_id if auth_method else None
    
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
