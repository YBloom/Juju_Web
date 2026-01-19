import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from services.db.connection import session_scope
from services.db.models import User, Subscription, SubscriptionTarget, SubscriptionOption
from sqlmodel import select

# Mode Mapping: Legacy 1/2/3 -> New 2/3/5
MODE_MAPPING = {
    1: 2,  # 上新/补票
    2: 3,  # 上新/补票/回流
    3: 5,  # 全量 (包含余票增减)
}

JSON_PATH = "plugins_legacy/data_legacy_260118_final/data/data_manager/UsersManager.json"

def import_legacy_data():
    if not os.path.exists(JSON_PATH):
        print(f"❌ JSON file not found: {JSON_PATH}")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    users_data = data.get("users", {})
    
    with session_scope() as session:
        count_users = 0
        count_subs = 0
        
        for qq_id, u_info in users_data.items():
            subscribe = u_info.get("subscribe", {})
            
            # Check if has any active subscription
            events = subscribe.get("subscribe_events", [])
            actors = subscribe.get("subscribe_actors", [])
            tickets = subscribe.get("subscribe_tickets", [])
            
            if not events and not actors and not tickets:
                continue
                
            # 1. Ensure User exists
            user = session.get(User, qq_id)
            if not user:
                user = User(
                    user_id=qq_id,
                    nickname=f"QQ用户_{qq_id[-4:]}",
                    auth_provider="qq",
                    auth_id=qq_id,
                    active=True
                )
                session.add(user)
            
            # 2. Global notification level
            legacy_global = u_info.get("attention_to_hulaquan", 0)
            try:
                legacy_global = int(legacy_global)
            except:
                legacy_global = 0
            user.global_notification_level = MODE_MAPPING.get(legacy_global, 0)
            
            # 3. Create Subscription
            # Check if user already has a subscription to avoid duplicates
            existing_sub = session.exec(select(Subscription).where(Subscription.user_id == qq_id)).first()
            if existing_sub:
                sub = existing_sub
            else:
                sub = Subscription(user_id=qq_id)
                session.add(sub)
                session.flush() # Get ID
            
            max_mode = 2 # Default for sub
            
            # 4. Target: Events (Plays)
            for e in events:
                mode = MODE_MAPPING.get(e.get("mode", 1), 2)
                max_mode = max(max_mode, mode)
                
                # Check if target already exists
                existing_t = session.exec(select(SubscriptionTarget).where(
                    SubscriptionTarget.subscription_id == sub.id,
                    SubscriptionTarget.kind == "play",
                    SubscriptionTarget.target_id == str(e["id"])
                )).first()
                
                if not existing_t:
                    target = SubscriptionTarget(
                        subscription_id=sub.id,
                        kind="play",
                        target_id=str(e["id"]),
                        name=f"剧目_{e['id']}"
                    )
                    session.add(target)
                    count_subs += 1

            # 5. Target: Actors
            for a in actors:
                mode = MODE_MAPPING.get(a.get("mode", 1), 2)
                max_mode = max(max_mode, mode)
                
                existing_t = session.exec(select(SubscriptionTarget).where(
                    SubscriptionTarget.subscription_id == sub.id,
                    SubscriptionTarget.kind == "actor",
                    SubscriptionTarget.target_id == a["actor"]
                )).first()
                
                if not existing_t:
                    target = SubscriptionTarget(
                        subscription_id=sub.id,
                        kind="actor",
                        target_id=a["actor"],
                        name=a["actor"],
                        include_plays=a.get("include_events") # Whitelist
                    )
                    session.add(target)
                    count_subs += 1
            
            # 6. Target: Tickets (Sessions) -> Map to Plays
            for t in tickets:
                # We don't have a direct mapping for ticket_id to event_id here easily without querying DB
                # For speed, we'll store them as 'event' kind (session) as fallback
                mode = MODE_MAPPING.get(t.get("mode", 1), 2)
                max_mode = max(max_mode, mode)
                
                existing_t = session.exec(select(SubscriptionTarget).where(
                    SubscriptionTarget.subscription_id == sub.id,
                    SubscriptionTarget.kind == "event",
                    SubscriptionTarget.target_id == str(t["id"])
                )).first()
                
                if not existing_t:
                    target = SubscriptionTarget(
                        subscription_id=sub.id,
                        kind="event",
                        target_id=str(t["id"]),
                        name=f"场次_{t['id']}"
                    )
                    session.add(target)
                    count_subs += 1
            
            # 7. Subscription Option
            option = session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == sub.id)).first()
            if not option:
                option = SubscriptionOption(
                    subscription_id=sub.id,
                    notification_level=max_mode,
                    freq="realtime"
                )
                session.add(option)
            else:
                option.notification_level = max(option.notification_level, max_mode)
            
            count_users += 1
            
        session.commit()
        print(f"✅ Successfully imported {count_users} users and {count_subs} subscription targets.")

if __name__ == "__main__":
    import_legacy_data()
