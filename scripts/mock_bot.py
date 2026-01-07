
import asyncio
import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from services.hulaquan.service import HulaquanService
from services.bot.handlers import BotHandler
from services.db.init import init_db

async def main():
    print("🤖 MusicalBot Mock Runner (v1.0)")
    print("Initializing Database & Services...")
    
    # Init DB
    init_db()
    
    # Init Service
    hlq_service = HulaquanService()
    # Note: We are not calling sync_all_data, so we rely on existing DB data.
    
    # Init Handler
    handler = BotHandler(hlq_service)
    
    print("✅ Ready! Type a command to test (e.g. '查票 魅影'). Type 'exit' or 'quit' to stop.")
    print("-" * 50)
    
    while True:
        try:
            user_input = await asyncio.to_thread(input, "User(12345) > ")
            if user_input.lower() in ["exit", "quit", "q"]:
                break
                
            if not user_input.strip():
                continue
                
            print("Processing...")
            
            # Simulate Group Message (Group 88888, User 12345)
            response = await handler.handle_group_message(
                group_id=88888,
                user_id=12345,
                message=user_input
            )
            
            if response:
                print(f"Bot > {response}")
            else:
                print("Bot > [No Response]")
                
            print("-" * 50)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    print("Shutting down...")
    await hlq_service.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
