
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
    
    bot = BotClient()
    handler = BotHandler(HulaquanService())
    
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
    
    logging.info("Starting Bot...")
    bot.run(bt_uin="3132859862", enable_webui_interaction=False)

if __name__ == "__main__":
    main()
