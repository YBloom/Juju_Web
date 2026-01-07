
import asyncio
import logging
import sys
from services.db.init import init_db
from services.bot.service import BotService

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

async def main():
    logging.info("Initializing Database...")
    init_db()
    
    logging.info("Initializing Bot Service...")
    
    # Force Config
    from ncatbot.utils.config import ncatbot_config
    ncatbot_config.set_bot_uin(3132859862)
    ncatbot_config.set_ws_uri("ws://127.0.0.1:3001")
    ncat_config = ncatbot_config # alias if needed or just use ncatbot_config
    ncat_config.set_ws_token("NcatBot")
    ncat_config.set_webui_token("StrongPassword123!")
    # Actually, NapCat docker default token is usually "NcatBot" if not set, or we set it?
    # Our docker run command didn't set WEBUI_TOKEN_ENABLE=true or similar?
    # Actually, NapCat Docker by mlikiowa usually has HTTP/WS enabled.
    # NcatBot checks security. setting webui_token prevents crash.
    
    bot = BotService()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logging.info("Stopping Bot Service...")
        await bot.stop()
    except Exception as e:
        logging.error(f"Bot Crashed: {e}", exc_info=True)
        await bot.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
