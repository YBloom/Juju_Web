
import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from services.bot.handlers import BotHandler
from services.db.connection import session_scope
from services.db.models import User, UserAuthMethod
from services.hulaquan.service import HulaquanService

async def verify_user_resolution():
    print("🚀 Starting User Resolution Verification...")
    
    # Setup test data
    test_user_id = "999999"
    test_qq_id = "test_qq_123"
    unknown_qq_id = "unknown_qq_456"
    
    with session_scope() as session:
        # Check if test user exists, delete if so to start fresh
        existing_user = session.get(User, test_user_id)
        if existing_user:
            session.delete(existing_user)
            session.commit()
            print(f"🧹 Cleaned up existing test user {test_user_id}")
            
        # Create test user
        user = User(user_id=test_user_id, nickname="Test User")
        session.add(user)
        
        # Create auth method linking QQ to User
        auth = UserAuthMethod(
            user_id=test_user_id,
            provider="qq",
            provider_user_id=test_qq_id,
            is_primary=True
        )
        session.add(auth)
        session.commit()
        print(f"✅ Created test user {test_user_id} linked to QQ {test_qq_id}")

    # Initialize BotHandler (mocking service as we don't need it for this test)
    handler = BotHandler(service=None) # type: ignore
    
    # Test valid link
    resolved_id = await handler.resolve_user_id(test_qq_id)
    print(f"🔍 Resolved {test_qq_id} -> {resolved_id}")
    
    if resolved_id == test_user_id:
        print("✅ SUCCESS: Correctly resolved linked user ID.")
    else:
        print(f"❌ FAILURE: Expected {test_user_id}, got {resolved_id}")
        
    # Test unknown QQ
    resolved_unknown = await handler.resolve_user_id(unknown_qq_id)
    print(f"🔍 Resolved {unknown_qq_id} -> {resolved_unknown}")
    
    if resolved_unknown == unknown_qq_id:
        print("✅ SUCCESS: Correctly returned raw QQ ID for unlinked user.")
    else:
        print(f"❌ FAILURE: Expected {unknown_qq_id}, got {resolved_unknown}")
        
    # Cleanup
    with session_scope() as session:
        user = session.get(User, test_user_id)
        if user:
            session.delete(user)
            session.commit()
            print("🧹 Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(verify_user_resolution())
