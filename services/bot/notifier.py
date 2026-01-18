
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import List
from sqlmodel import select, col, and_, or_
from services.db.connection import session_scope
from services.hulaquan.tables import TicketUpdateLog, HulaquanSubscription, HulaquanTicket
from services.saoju.service import SaojuService

log = logging.getLogger(__name__)

class BotNotifier:
    def __init__(self, bot_client):
        self.bot = bot_client
        self.running = False
        self._last_check_time = datetime.now()

    async def start(self):
        self.running = True
        log.info("🔔 [通知服务] 通知推送服务已启动")
        while self.running:
            try:
                await self._check_and_push()
                await asyncio.sleep(10) # Check every 10 seconds
            except Exception as e:
                log.error(f"❌ [通知服务] 循环执行异常: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def stop(self):
        self.running = False
        log.info("🛑 [通知服务] 通知推送服务已停止")

    async def _check_and_push(self):
        # 1. Fetch new logs since last check
        # We assume logs are inserted with a slight delay, so we query carefully.
        # Ideally, we track the max ID processed, but time-based is easier for stateless retry.
        
        check_start = self._last_check_time
        now = datetime.now()
        
        updates = []
        with session_scope() as session:
            # Join Ticket to verify real-time status
            stmt = select(TicketUpdateLog).join(HulaquanTicket, TicketUpdateLog.ticket_id == HulaquanTicket.id)
            
            stmt = stmt.where(TicketUpdateLog.created_at > check_start)
            
            # Status Filter (Active/Pending AND (Pending OR Stock>0))
            stmt = stmt.where(
                or_(
                    HulaquanTicket.status == 'pending',
                    and_(
                        HulaquanTicket.status == 'active',
                        HulaquanTicket.stock > 0
                    )
                )
            )
            
            # Time Filter
            stmt = stmt.where(
                or_(
                    HulaquanTicket.session_time >= now,
                    HulaquanTicket.session_time == None
                )
            )
            
            stmt = stmt.order_by(TicketUpdateLog.created_at.asc())
            
            updates = session.exec(stmt).all()
            # Eager load data to avoid DetachedInstanceError after session close
            updates_data = []
            for u in updates:
                 updates_data.append({
                     "id": u.id,
                     "event_id": u.event_id,
                     "change_type": u.change_type,
                     "message": u.message,
                     "session_time": u.session_time,
                     "price": u.price,
                     "original": u # IDK if we need this, but let's store ID
                 })
        
        if not updates_data:
            self._last_check_time = now
            return

        log.info(f"📢 [通知服务] 发现 {len(updates_data)} 条新更新待推送")
        
        for update in updates_data:
            await self._process_update(update)
            
        self._last_check_time = now

    async def _process_update(self, update: dict):
        # 2. Find Subscribers
        
        subscribers = []
        with session_scope() as session:
            # TargetType: "event"
            stmt = select(HulaquanSubscription).where(
                HulaquanSubscription.target_type == "event",
                HulaquanSubscription.target_id == update["event_id"],
                HulaquanSubscription.mode > 0 # 1=On
            )
            subscribers = session.exec(stmt).all()
            # Eager load subs
            sub_ids = [s.user_id for s in subscribers]
            
        if not sub_ids:
            return

        # 3. Format Message
        msg_text = f"【{update['change_type'].upper()}】{update['message']}"
        if update['session_time']:
             msg_text += f"\n时间: {update['session_time'].strftime('%Y-%m-%d %H:%M')}"
        msg_text += f"\n价格: ¥{update['price']}"
        
        # Add link (Web)
        msg_text += f"\n查看: http://admin.yaobii.com/events/{update['event_id']}"

        # 4. Push
        for user_id_str in sub_ids:
            try:
                user_id = int(user_id_str)
                # Using send_private_msg
                log.info(f"📤 [推送] 正在推送更新 #{update['id']} 给用户 {user_id}")
                await self.bot.send_private_msg(user_id=user_id, message=msg_text)
            except Exception as e:
                log.error(f"❌ [推送] 推送给用户 {user_id} 失败: {e}")
