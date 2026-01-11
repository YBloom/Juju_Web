#!/usr/bin/env python3
"""
Quick test to verify the service can load and API works
快速测试验证服务可以加载且API正常工作
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_service():
    print("🔍 Testing service import...")
    try:
        from services.hulaquan.service import HulaquanService
        from services.db.init import init_db
        print("✓ Service import successful")
    except Exception as e:
        print(f"✗ Service import failed: {e}")
        return False
    
    print("\n🔍 Initializing database...")
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Database init failed: {e}")
        return False
    
    print("\n🔍 Creating service instance...")
    try:
        service = HulaquanService()
        print("✓ Service instance created")
    except Exception as e:
        print(f"✗ Service creation failed: {e}")
        return False
    
    print("\n🔍 Testing get_recent_updates...")
    try:
        updates = await service.get_recent_updates(limit=5, change_types=["new", "restock"])
        print(f"✓ Got {len(updates)} recent updates")
        if updates:
            print(f"  First update: {updates[0].event_title} - {updates[0].change_type}")
    except Exception as e:
        print(f"✗ get_recent_updates failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    result = asyncio.run(test_service())
    sys.exit(0 if result else 1)
