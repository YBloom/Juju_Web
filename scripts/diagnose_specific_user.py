import sys
import os
sys.path.append(os.getcwd())

from sqlmodel import select
from services.db.connection import session_scope
from services.db.models import User, Subscription, SubscriptionTarget, UserAuthMethod

def diagnose(target_name_part):
    print(f"🔍 Searching for targets containing: '{target_name_part}'")
    with session_scope() as session:
        # Find all targets matching the name
        targets = session.exec(select(SubscriptionTarget).where(SubscriptionTarget.name.contains(target_name_part))).all()
        
        if not targets:
            print("❌ No targets found matching that name.")
            return

        print(f"✅ Found {len(targets)} matching targets:")
        for t in targets:
            sub = session.get(Subscription, t.subscription_id)
            user = session.get(User, sub.user_id) if sub else None
            
            print(f"\n--- Target ID: {t.id} ---")
            print(f"Name: {t.name}")
            print(f"SubscriptionContainer ID: {t.subscription_id}")
            
            if user:
                print(f"User ID: {user.user_id}")
                print(f"User Nickname: {user.nickname}")
                
                # Check Auth Methods (QQ, etc)
                auths = session.exec(select(UserAuthMethod).where(UserAuthMethod.user_id == user.user_id)).all()
                auth_info = ", ".join([f"{a.provider}:{a.provider_user_id}" for a in auths])
                print(f"Linked Auth: {auth_info}")
            else:
                print("⚠️  Orphaned Subscription (No User found)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_specific_user.py <name>")
    else:
        diagnose(sys.argv[1])
