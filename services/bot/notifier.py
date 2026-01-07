
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import List
from sqlmodel import select, col
from services.db.connection import session_scope
from services.hulaquan.tables import TicketUpdateLog, HulaquanSubscription
from services.saoju.service import SaojuService

log = logging.getLogger(__name__)

class BotNotifier:
    def __init__(self, bot_client):
        self.bot = bot_client
        self.running = False
        self._last_check_time = datetime.now()

    async def start(self):
        self.running = True
        log.info("Bot Notifier started.")
        while self.running:
            try:
                await self._check_and_push()
                await asyncio.sleep(10) # Check every 10 seconds
            except Exception as e:
                log.error(f"Notifier Loop Error: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def stop(self):
        self.running = False
        log.info("Bot Notifier stopped.")

    async def _check_and_push(self):
        # 1. Fetch new logs since last check
        # We assume logs are inserted with a slight delay, so we query carefully.
        # Ideally, we track the max ID processed, but time-based is easier for stateless retry.
        
        check_start = self._last_check_time
        now = datetime.now()
        
        updates = []
        with session_scope() as session:
            stmt = select(TicketUpdateLog).where(
                TicketUpdateLog.created_at > check_start
            ).order_by(TicketUpdateLog.created_at.asc())
            
            updates = session.exec(stmt).all()
        
        if not updates:
            self._last_check_time = now
            return

        log.info(f"Notifier: Found {len(updates)} new updates.")
        
        for update in updates:
            await self._process_update(update)
            
        self._last_check_time = now

    async def _process_update(self, update: TicketUpdateLog):
        # 2. Find Subscribers
        # Logic: 
        # - Match Event ID
        # - TODO: Match City? Price?
        
        # Current logic: Simple Event ID match
        # We need a method to get subscribers. 
        # Since HulaquanSubscription is in DB, we query it.
        
        subscribers = []
        with session_scope() as session:
            # TargetType: "event"
            stmt = select(HulaquanSubscription).where(
                HulaquanSubscription.target_type == "event",
                HulaquanSubscription.target_id == update.event_id,
                HulaquanSubscription.mode > 0 # 1=On
            )
            subscribers = session.exec(stmt).all()
            
        if not subscribers:
            return

        # 3. Format Message
        msg_text = f"【{update.change_type.upper()}】{update.message}"
        if update.session_time:
             msg_text += f"\n时间: {update.session_time.strftime('%Y-%m-%d %H:%M')}"
        msg_text += f"\n价格: ¥{update.price}"
        
        # Add link (Web)
        msg_text += f"\n查看: http://admin.yaobii.com/events/{update.event_id}"

        # 4. Push
        for sub in subscribers:
            try:
                user_id = int(sub.user_id)
                # Using send_private_msg or send_group_msg?
                # Subscription is usually private or group specific?
                # If user_id is huge, it might be group? standard QQ is uin.
                log.info(f"Pushing update {update.id} to user {user_id}")
                await self.bot.send_private_msg(user_id=user_id, message=msg_text)
            except Exception as e:
                log.error(f"Failed to push to {sub.user_id}: {e}")
