
import asyncio
import logging
from ncatbot.core import BotClient, GroupMessage, PrivateMessage
from services.hulaquan.service import HulaquanService
from services.bot.handlers import BotHandler
from services.notification.engine import NotificationEngine

log = logging.getLogger(__name__)

class BotService:
    def __init__(self):
        self.client = BotClient()
        self.hlq_service = HulaquanService()
        self.handler = BotHandler(self.hlq_service)
        self.notifier = BotNotifier(self.client)
        
        # Notification Consumer (Decoupled from Web)
        # Bot service is responsible for sending queued messages
        self.notification_engine = NotificationEngine(bot_api=self.client.api)
        self.consumer_task = None
        
        self._setup_events()

    def _setup_events(self):
        @self.client.group_event()
        async def on_group_message(msg: GroupMessage):
            # Self Ignore
            # if msg.user_id == self.client.self_id: return
            
            response = await self.handler.handle_group_message(
                group_id=msg.group_id,
                user_id=msg.user_id,
                message=msg.raw_message, 
                sender_role=msg.sender.role # Assuming sender object exists
            )
            
            if response:
                await self.client.send_group_msg(group_id=msg.group_id, message=response)

        @self.client.private_event()
        async def on_private_message(msg: PrivateMessage):
             # Handle private commands if needed
             pass

    async def _run_consumer_loop(self):
        """Periodically consume SendQueue items and send notifications."""
        log.info("📧 [Bot服务] 通知消费任务已启动 (Interval: 120s)")
        while True:
            try:
                count = await self.notification_engine.consume_queue(limit=50)
                if count > 0:
                    log.info(f"📧 [Bot服务] 发送了 {count} 条通知")
            except Exception as e:
                log.error(f"⚠️ [Bot服务] 通知消费错误: {e}")
            
            await asyncio.sleep(120) # 2 minutes interval

    async def start(self, **kwargs):
        """Start the bot client."""
        log.info("🤖 [Bot服务] 正在启动 Bot 服务...")
        
        # Start Notifier (Old logic, maybe redundant if using queue? Keep for now)
        asyncio.create_task(self.notifier.start())
        
        # Start Queue Consumer
        self.consumer_task = asyncio.create_task(self._run_consumer_loop())
        
        # Start Bot Client
        await self.client.run() 

    async def stop(self):
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
                
        await self.notifier.stop()
        await self.hlq_service.close()
