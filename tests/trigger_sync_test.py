import asyncio
import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from services.hulaquan.service import HulaquanService

async def main():
    print("🚀 Initializing HulaquanService...")
    service = HulaquanService()
    print("🔍 Starting sync_all_data...")
    try:
        # HulaquanService uses session_scope internally for sync
        updates = await service.sync_all_data()
        print(f"✅ Sync completed. Found {len(updates)} updates.")
        for u in updates:
            print(f"  - [{u.change_type}] {u.event_title}: {u.message}")
    except Exception as e:
        print(f"❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(main())
