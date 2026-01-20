import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.notification.engine import NotificationEngine
from services.db.connection import session_scope
from services.db.models import Subscription, SubscriptionTarget, SendQueue, SendQueueStatus
from services.hulaquan.models import TicketUpdate

class MockBotAPI:
    async def post_group_msg(self, group_id, text):
        print(f"✅ [MOCK] Sending to Group {group_id}:\n{text}")
        return {"retcode": 0}

    async def post_private_msg(self, user_id, text):
        print(f"✅ [MOCK] Sending to Private {user_id}:\n{text}")
        return {"retcode": 0}

async def run_verification():
    print("🚀 Starting Group Notification Verification...")
    
    mock_group_id = 999999
    user_id = f"group_{mock_group_id}"
    
    # 1. Setup Mock Subscription
    from sqlmodel import select
    with session_scope() as session:
        # Cleanup previous test data
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        existing_sub = session.exec(stmt).first()
        
        if existing_sub:
            # Manually delete targets first to avoid IntegrityError if cascade is not set
            stmt_targets = select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == existing_sub.id)
            targets = session.exec(stmt_targets).all()
            for t in targets:
                session.delete(t)
            session.delete(existing_sub)
            session.commit()
        
        # Create Subscription
        sub = Subscription(user_id=user_id)
        session.add(sub)
        session.commit() # Commit to get ID
        
        # Create Target (Subscribe to 'Test Play')
        target = SubscriptionTarget(
            subscription_id=sub.id,
            kind="PLAY",
            target_id="123456",
            name="测试剧目",
            flags={"mode": 1}
        )
        session.add(target)
        session.commit()
        print(f"📋 Created mock subscription for {user_id}")

    # 2. Simulate Update
    updates = [
        TicketUpdate(
            event_id="123456",
            event_title="测试剧目",
            change_type="new",
            message="[Test] New tickets available!",
            ticket_id="TICKET_001",
            cast_names=[]
        )
    ]
    
    # 3. Process Updates
    engine = NotificationEngine(bot_api=MockBotAPI())
    
    print("\n⚙️ Processing updates...")
    count = await engine.process_updates(updates)
    print(f"📥 Enqueued {count} notifications")
    
    # 4. Consume Queue
    print("\n📨 Consuming queue...")
    sent = await engine.consume_queue()
    print(f"📤 Sent {sent} notifications")
    
    # 5. Cleanup
    with session_scope() as session:
        # Delete queue items
        qs = session.exec(select(SendQueue).where(SendQueue.user_id == user_id)).all()
        for q in qs:
            session.delete(q)
            
        # Delete subscription
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        sub = session.exec(stmt).first()
        if sub:
            # Delete targets first
            targets = session.exec(select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)).all()
            for t in targets:
                session.delete(t)
            session.delete(sub)
        session.commit()
        print("\n🧹 Cleanup complete")

if __name__ == "__main__":
    asyncio.run(run_verification())
