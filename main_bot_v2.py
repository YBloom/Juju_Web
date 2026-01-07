
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
    
    # Force Config Global (Critical for validation check)
    from ncatbot.utils.config import ncatbot_config
    ncatbot_config.set_bot_uin("3132859862")
    ncatbot_config.set_ws_uri("ws://127.0.0.1:3001")
    ncatbot_config.set_ws_token("NcatBot") # Ensure this matches NapCat server
    ncatbot_config.set_webui_token("StrongPassword123!") # Strong Password to pass security check
    
    # Args for run()
    bot_uin = "3132859862"
    
    bot = BotService()
    
    try:
        # Start with specific parameters to avoid interactive mode
        await bot.start(
            bt_uin=bot_uin,
            active=True, # v4 argument? Check if needed. usually bt_uin is enough
            enable_webui_interaction=False # Critical for headless
        )
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
