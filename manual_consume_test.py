
import asyncio
import logging
import sys
import os

# Create a mock Bot Client that just logs instead of sending, 
# OR actually try to import the real one if we can run it headless.
# But ncatbot client relies on WS.
# We will Mock the API to verify the "logic" of consume_queue (DB -> Logic -> call API)
# If logic passes, then the issue is the Loop or WS connection.

sys.path.append(os.getcwd())
try:
    from dotenv import load_dotenv
    load_dotenv()
except: pass

from services.notification import NotificationEngine

# Mock API
class MockApi:
    async def post_group_msg(self, group_id, text):
        print(f"✅ [MOCK API] Group {group_id} Message: {text[:50]}...")
        return {"status": "ok"}
    
    async def post_private_msg(self, user_id, text):
        print(f"✅ [MOCK API] Private {user_id} Message: {text[:50]}...")
        return {"status": "ok"}

async def main():
    print("--- Starting Manual Consumption Test ---")
    mock_api = MockApi()
    engine = NotificationEngine(bot_api=mock_api)
    
    print("Consuming queue (limit 5)...")
    sent = await engine.consume_queue(limit=5)
    print(f"Sent: {sent}")
    
    if sent == 0:
        print("No items were sent. Possible reasons:")
        print("1. Queue is empty (Checked: Logic says 15 pending)")
        print("2. User ID has no QQ binding? (Check logs)")
        print("3. Whitelist active? (Check logs)")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
