
import os
"""
MusicalBot QQ Bot Entry Point (v2)
使用 ncatbot v4，同步启动方式
"""
import logging
import asyncio
from services.db.init import init_db
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s %(name)s \'%(filename)s:%(lineno)d\' | %(message)s',
    datefmt='%m/%d %H:%M:%S',
    force=True
)

log = logging.getLogger(__name__)

def main():
    logging.info("🚀 [启动] 正在初始化数据库...")
    init_db()
    
    # Force Config
    from ncatbot.utils.config import ncatbot_config
    bot_uin = os.getenv("BOT_UIN", "3044829389")
    ncatbot_config.set_bot_uin(bot_uin)
    ncatbot_config.set_root("3022402752")     # TODO: Move rigid Admin ID to config
    ncatbot_config.set_ws_uri("ws://127.0.0.1:3001")
    
    # Import components
    from ncatbot.core import BotClient, GroupMessage, PrivateMessage, RequestEvent
    from services.bot.handlers import BotHandler
    from services.hulaquan.service import HulaquanService
    from services.notification import NotificationEngine
    import traceback

    ADMIN_QQ = "3022402752"
    
    bot = BotClient()
    hlq_service = HulaquanService()
    handler = BotHandler(hlq_service)
    notification_engine = NotificationEngine(bot_api=None)
    
    # Scheduled task state
    _scheduled_task_running = False
    
    async def scheduled_consume_task():
        """通知分发任务 - 每 30 秒扫描一次发送队列"""
        nonlocal _scheduled_task_running
        if _scheduled_task_running:
            return
        _scheduled_task_running = True
        
        log.info("⏰ [定时任务] 通知分发任务已启动 (轮询间隔: 30s)")
        
        # Wait a bit for bot to be fully ready
        await asyncio.sleep(5)
        
        while True:
            try:
                # Set/Update bot api
                if not notification_engine.bot_api:
                    notification_engine.bot_api = bot.api
                
                # Consume send queue (Producer is now solely the Web service or independent crawler)
                if notification_engine.bot_api:
                    sent = await notification_engine.consume_queue(limit=100)
                    if sent > 0:
                        log.info(f"✅ [通知] 已成功下发 {sent} 条通知")
                else:
                    log.warning("⏳ [通知] 等待 Bot API 就绪...")
                    
            except Exception as e:
                log.error(f"❌ [错误] 通知分发任务异常: {e}")
                try:
                    msg_text = f"❌ [Bot Task Error] {e}\n{traceback.format_exc()}"[:500]
                    await bot.api.post_private_msg(user_id=ADMIN_QQ, text=msg_text)
                except: pass
            
            await asyncio.sleep(5)
    
    @bot.on_group_message()
    async def on_group_message(msg: GroupMessage):
        try:
            response = await handler.handle_group_message(msg.group_id, int(msg.user_id), msg.raw_message, nickname=getattr(msg.sender, 'nickname', ''))
            if response:
                if isinstance(response, list):
                    for r in response:
                        await bot.api.post_group_msg(group_id=msg.group_id, text=r)
                else:
                    await bot.api.post_group_msg(group_id=msg.group_id, text=response)
        except Exception as e:
            log.error(f"❌ [错误] 处理群消息失败: {e} | Msg: {msg.raw_message}")
            try:
                msg_text = f"❌ [Bot Group Error] {e}\n{traceback.format_exc()}"[:500]
                await bot.api.post_private_msg(user_id=ADMIN_QQ, text=msg_text)
            except: pass

    @bot.on_private_message()
    async def on_private_message(msg: PrivateMessage):
        try:
            response = await handler.handle_message(msg.raw_message, str(msg.user_id), nickname=getattr(msg.sender, 'nickname', ''))
            if response:
                if isinstance(response, list):
                    for r in response:
                        await bot.api.post_private_msg(user_id=msg.user_id, text=r)
                else:
                    await bot.api.post_private_msg(user_id=msg.user_id, text=response)
        except Exception as e:
            log.error(f"❌ [错误] 处理私聊消息失败: {e} | Msg: {msg.raw_message}")
            try:
                msg_text = f"❌ [Bot Private Error] {e}\n{traceback.format_exc()}"[:500]
                await bot.api.post_private_msg(user_id=ADMIN_QQ, text=msg_text)
            except: pass
    
    # NEW: Start the task using ncatbot's startup hook
    @bot.on_startup
    async def startup_handler():
        log.info("🚀 [Startup] Bot started, launching background tasks...")
        asyncio.create_task(scheduled_consume_task())
    
    @bot.on_request()
    async def on_request(event: RequestEvent):
        """自动批准所有 好友/加群 请求"""
        req_type = event.request_type
        uid = event.user_id
        gid = event.group_id
        comment = event.comment
        
        log.info(f"🔔 [请求] 收到 {req_type} 请求 | User: {uid} | Group: {gid} | Comment: {comment}")
        
        if req_type == "friend":
            await event.approve(approve=True)
            log.info(f"✅ [自动批准] 已通过好友请求: {uid}")
            
        elif req_type == "group":
            # 自动通过加群/邀请进群
            await event.approve(approve=True)
            log.info(f"✅ [自动批准] 已通过加群请求: Group {gid} | User {uid}")
    
    logging.info(f"🤖 [启动] Bot ({bot_uin}) 正在启动...")
    # TODO: Refactor to use config value
    bot.run(bt_uin=bot_uin, enable_webui_interaction=False)

if __name__ == "__main__":
    main()
