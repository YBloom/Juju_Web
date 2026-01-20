
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from services.hulaquan.service import HulaquanService
from services.hulaquan.models import EventInfo

async def main():
    service = HulaquanService()
    query = "时光代理人 上海"
    print(f"Searching for '{query}'...")
    
    # We can use the async method directly if we are running in an event loop
    # But since we are inside a script, we need to handle the loop manually or just call the sync logic if possible
    # Service methods use run_in_executor, so we should await them in an async function.
    
    try:
        results = await service.search_events(query)
        print(f"Found {len(results)} results:")
        for i, event in enumerate(results):
            print(f"[{i}] ID: {event.id}")
            print(f"    Title: {event.title}")
            print(f"    City: {event.city}")
            print(f"    Location: {event.location}")
            print(f"    Schedule: {event.schedule_range}")
            print("-" * 20)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(main())
