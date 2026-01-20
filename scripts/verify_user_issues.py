import sys
import os
from sqlmodel import Session, select, func
from services.db.connection import get_engine
from services.db.models import User, Subscription, UserAuthMethod, SubscriptionTarget

def verify_data():
    engine = get_engine()
    with Session(engine) as session:
        print("=== Checking for Duplicate Subscriptions per User ===")
        # Find users with >1 subscription
        stmt = select(Subscription.user_id, func.count(Subscription.id)).group_by(Subscription.user_id).having(func.count(Subscription.id) > 1)
        duplicates = session.exec(stmt).all()
        
        if duplicates:
            print(f"❌ FOUND {len(duplicates)} users with multiple Subscription rows!")
            for user_id, count in duplicates:
                print(f"  - User {user_id}: {count} subscriptions")
                # Detail the subs
                subs = session.exec(select(Subscription).where(Subscription.user_id == user_id)).all()
                for sub in subs:
                    targets = session.exec(select(SubscriptionTarget).where(SubscriptionTarget.subscription_id == sub.id)).all()
                    print(f"    - Sub ID {sub.id} (Created: {sub.created_at}): {len(targets)} targets")
        else:
            print("✅ No duplicate subscriptions found.")

        print("\n=== Checking for User Split (QQ vs AuthMethod) ===")
        # Find auth methods
        auths = session.exec(select(UserAuthMethod).where(UserAuthMethod.provider == "qq")).all()
        for auth in auths:
            # Check if there is a User row with the QQ ID itself
            legacy_user = session.exec(select(User).where(User.user_id == auth.provider_user_id)).first()
            if legacy_user:
                print(f"⚠️ POTENTIAL SPLIT: User {auth.user_id} is linked to QQ {auth.provider_user_id}, BUT User {legacy_user.user_id} also exists separately!")
                
                # Check subs for both
                sub_linked = session.exec(select(Subscription).where(Subscription.user_id == auth.user_id)).first()
                sub_legacy = session.exec(select(Subscription).where(Subscription.user_id == legacy_user.user_id)).first()
                
                count_linked = 0
                if sub_linked:
                    count_linked = session.exec(select(func.count(SubscriptionTarget.id)).where(SubscriptionTarget.subscription_id == sub_linked.id)).one()
                
                count_legacy = 0
                if sub_legacy:
                    count_legacy = session.exec(select(func.count(SubscriptionTarget.id)).where(SubscriptionTarget.subscription_id == sub_legacy.id)).one()
                
                print(f"   - Linked User ({auth.user_id}): {count_linked} targets")
                print(f"   - Legacy User ({legacy_user.user_id}): {count_legacy} targets")

if __name__ == "__main__":
    verify_data()
