import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlmodel import select, func
from services.db.connection import session_scope
from services.db.models import User, Subscription, SubscriptionTarget

def merge_subscriptions():
    """
    Merge multiple Subscription records for the same user into one.
    """
    print("🚀 Starting subscription merge...")
    
    with session_scope() as session:
        # 1. Find users with multiple subscriptions
        # Group by user_id and count
        stmt = (
            select(Subscription.user_id)
            .group_by(Subscription.user_id)
            .having(func.count(Subscription.id) > 1)
        )
        user_ids = session.exec(stmt).all()
        
        if not user_ids:
            print("✅ No users with multiple subscriptions found.")
            return

        print(f"⚠️  Found {len(user_ids)} users with split subscriptions.")

        for user_id in user_ids:
            print(f"\nProcessing User: {user_id}")
            
            # Get all subscriptions for this user
            subs = session.exec(
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at) # Keep the oldest one as primary
            ).all()
            
            if len(subs) < 2:
                continue
                
            primary_sub = subs[0]
            duplicates = subs[1:]
            
            print(f"  - Primary Subscription ID: {primary_sub.id}")
            print(f"  - Found {len(duplicates)} duplicate containers.")
            
            targets_moved = 0
            
            for dup in duplicates:
                # Move targets from duplicate to primary
                dup_targets = session.exec(
                    select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == dup.id)
                ).all()
                
                for target in dup_targets:
                    # Check for collision in primary
                    existing = session.exec(
                        select(SubscriptionTarget).where(
                            SubscriptionTarget.subscription_id == primary_sub.id,
                            SubscriptionTarget.kind == target.kind,
                            SubscriptionTarget.target_id == target.target_id
                        )
                    ).first()
                    
                    if existing:
                        print(f"    - Target {target.name} (ID: {target.target_id}) already exists in primary. Deleting duplicate.")
                        session.delete(target)
                    else:
                        print(f"    - Moving target {target.name} to primary.")
                        target.subscription_id = primary_sub.id
                        session.add(target)
                        targets_moved += 1
                
                # Check for SubscriptionOption and delete it (User settings are now on User table anyway, or we keep primary)
                from services.db.models import SubscriptionOption
                dup_options = session.exec(
                    select(SubscriptionOption).where(SubscriptionOption.subscription_id == dup.id)
                ).all()
                for opt in dup_options:
                     print(f"    - Deleting duplicate SubscriptionOption {opt.id}")
                     session.delete(opt)

                # Delete the empty duplicate subscription
                print(f"  - Deleting empty subscription container {dup.id}")
                session.delete(dup)
            
            print(f"  ✅ Merged {targets_moved} targets to primary.")

        try:
            session.commit()
            print("\n🎉 Merge complete!")
        except Exception as e:
            session.rollback()
            print(f"\n❌ Merge failed: {e}")


if __name__ == "__main__":
    merge_subscriptions()
