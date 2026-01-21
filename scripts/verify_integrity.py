import multiprocessing
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from services.db.connection import get_engine, session_scope
from services.db.models import User, Subscription, SubscriptionTarget, SubscriptionOption, UserAuthMethod, InternalMetadata
from sqlmodel import SQLModel, select, delete

def init_db():
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    # Clear existing data for clean test
    with session_scope() as session:
        # Delete children first (OR let cascade handle it, but for a clean start we explicitly delete)
        session.exec(delete(UserAuthMethod))
        session.exec(delete(SubscriptionTarget))
        session.exec(delete(SubscriptionOption))
        session.exec(delete(Subscription))
        session.exec(delete(User))
        session.exec(delete(InternalMetadata))

def register_users(count, process_id):
    """Attempt concurrent registration."""
    user_ids = []
    for i in range(count):
        user_id = User.generate_next_id()
        user_ids.append(user_id)
        with session_scope() as session:
            user = User(user_id=user_id, nickname=f"User_{process_id}_{i}")
            session.add(user)
        # Small random sleep to increase race condition probability if present
        time.sleep(0.01)
    return user_ids

def test_concurrency():
    print("Testing ID Concurrency...")
    init_db()
    
    process_count = 4
    users_per_process = 10
    
    with multiprocessing.Pool(process_count) as pool:
        results = pool.starmap(register_users, [(users_per_process, i) for i in range(process_count)])
    
    all_ids = [uid for sublist in results for uid in sublist]
    unique_ids = set(all_ids)
    
    print(f"Total IDs generated: {len(all_ids)}")
    print(f"Unique IDs count: {len(unique_ids)}")
    
    if len(all_ids) == len(unique_ids):
        print("✅ SUCCESS: No ID collisions detected.")
    else:
        print("❌ FAILURE: ID collisions detected!")
        # Find duplicates
        seen = set()
        dupes = [x for x in all_ids if x in seen or seen.add(x)]
        print(f"Duplicates: {dupes}")

def test_cascade_delete():
    print("\nTesting Cascade Delete...")
    with session_scope() as session:
        # 1. Create User
        user_id = User.generate_next_id()
        user = User(user_id=user_id, nickname="CascadeTest")
        session.add(user)
        session.commit()
        
        # 2. Add Auth Method
        auth = UserAuthMethod(user_id=user_id, provider="qq", provider_user_id="123456")
        session.add(auth)
        
        # 3. Add Subscription
        sub = Subscription(user_id=user_id)
        session.add(sub)
        session.commit() # Get sub.id
        
        target = SubscriptionTarget(subscription_id=sub.id, kind="play", target_id="play123")
        option = SubscriptionOption(subscription_id=sub.id)
        session.add(target)
        session.add(option)
        session.commit()
        
        print(f"Created user {user_id} with auth, sub, target, and option.")
        
        # 4. Perform Hard Delete
        session.delete(user)
        session.commit()
        print(f"Deleted user {user_id}.")
        
        # 5. Verify orphans
        auth_exists = session.exec(select(UserAuthMethod).where(UserAuthMethod.user_id == user_id)).first()
        sub_exists = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
        
        if not auth_exists and not sub_exists:
            print("✅ SUCCESS: Cascade delete works for Auth and Subscription.")
        else:
            print(f"❌ FAILURE: Orphan data found! Auth: {auth_exists}, Sub: {sub_exists}")

if __name__ == "__main__":
    test_concurrency()
    test_cascade_delete()
