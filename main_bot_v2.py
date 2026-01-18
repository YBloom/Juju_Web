
import asyncio
"""
MusicalBot QQ Bot Entry Point (v2)
使用 ncatbot v4，同步启动方式
"""
import logging
from services.db.init import init_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

log = logging.getLogger(__name__)

def main():
    logging.info("Initializing Database...")
    init_db()
    
    # Force Config
    from ncatbot.utils.config import ncatbot_config
    ncatbot_config.set_bot_uin("3132859862")
    ncatbot_config.set_ws_uri("ws://127.0.0.1:3001")
    
    # Import and run (同步方式，ncatbot 内部处理 asyncio)
    from ncatbot.core import BotClient, GroupMessage, PrivateMessage
    from services.bot.handlers import BotHandler
    from services.hulaquan.service import HulaquanService
    from services.notification import NotificationEngine
    
    bot = BotClient()
    hlq_service = HulaquanService()
    handler = BotHandler(hlq_service)
    notification_engine = NotificationEngine(bot_api=None)  # Will set api after bot starts
    
    # Scheduled task state
    _scheduled_task_running = False
    
    async def scheduled_sync_task():
        """定时同步任务 - 每 5 分钟执行一次"""
        nonlocal _scheduled_task_running
        if _scheduled_task_running:
            return
        _scheduled_task_running = True
        
        # Set bot api for notification engine
        notification_engine.bot_api = bot.api
        
        log.info("Starting scheduled sync task...")
        while True:
            try:
                # 1. Sync data and detect updates
                async with hlq_service as service:
                    updates = await service.sync_all_data()
                
                # 2. Process updates through notification engine
                if updates:
                    enqueued = await notification_engine.process_updates(updates)
                    log.info(f"Enqueued {enqueued} notifications from {len(updates)} updates")
                
                # 3. Consume send queue
                sent = await notification_engine.consume_queue()
                if sent > 0:
                    log.info(f"Sent {sent} notifications")
                    
            except Exception as e:
                log.error(f"Scheduled sync task error: {e}")
            
            # Wait 5 minutes
            await asyncio.sleep(300)
    
    @bot.group_event()
    async def on_group_message(msg: GroupMessage):
        response = await handler.handle_message(msg.raw_message, str(msg.user_id))
        if response:
            await bot.api.post_group_msg(msg.group_id, text=response)
    
    @bot.private_event()
    async def on_private_message(msg: PrivateMessage):
        response = await handler.handle_message(msg.raw_message, str(msg.user_id))
        if response:
            await bot.api.post_private_msg(msg.user_id, text=response)
        
        # Start scheduled task on first message (ensures bot.api is ready)
        if not _scheduled_task_running:
            asyncio.create_task(scheduled_sync_task())
    
    logging.info("Starting Bot...")
    bot.run(bt_uin="3132859862", enable_webui_interaction=False)

if __name__ == "__main__":
    main()
