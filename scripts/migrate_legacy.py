import json
import logging
from pathlib import Path
from datetime import datetime
from sqlmodel import Session, select, create_engine
from sqlalchemy.orm import joinedload

# Adjust python path if needed or run as python -m scripts.migrate_legacy
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from services.db.models.user import User
from services.db.models.subscription import Subscription, SubscriptionTarget, SubscriptionOption, SubscriptionTargetKind, SubscriptionFrequency
from services.db.connection import get_engine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
LEGACY_DATA_DIR = Path("plugins_legacy/data_legacy_260118_final/data")
HULAQUAN_DATA_PATH = LEGACY_DATA_DIR / "data_manager/HulaquanDataManager.json"
USERS_DATA_PATH = LEGACY_DATA_DIR / "data_manager/UsersManager.json"

# Database connection
engine = get_engine()

def load_json(path: Path):
    if not path.exists():
        logger.error(f"File not found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def migrate():
    # Load Data
    logger.info("Loading legacy data...")
    hq_data = load_json(HULAQUAN_DATA_PATH)
    users_data = load_json(USERS_DATA_PATH)

    if not hq_data or not users_data:
        logger.error("Failed to load data.")
        return

    # Create event id -> title map
    event_titles = {}
    for eid, event in hq_data.get("events", {}).items():
        event_titles[str(eid)] = event.get("title", f"Unknown Event {eid}")

    with Session(engine) as session:
        users = users_data.get("users", {})
        total_users = len(users)
        processed_users = 0
        skipped_users = 0
        
        logger.info(f"Found {total_users} users in legacy data.")

        for user_id, user_info in users.items():
            # 1. Upsert User
            # Check if user exists
            db_user = session.exec(select(User).where(User.user_id == user_id)).first()
            if not db_user:
                db_user = User(user_id=user_id)
                db_user.created_at = datetime.now() # Fallback
            
            # Update fields
            # Parse create_time: "2025-07-27 15:29:27"
            try:
                if "create_time" in user_info:
                    db_user.created_at = datetime.strptime(user_info["create_time"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
            
            db_user.active = user_info.get("activate", True)
            # Default bot_interaction_mode is 'hybrid' via model default, no need to change unless we want to map logic.
            # We map 'attention_to_hulaquan' to active status? 
            # If attention_to_hulaquan is "0" (off), maybe we leave them as active but with no subscriptions?
            # Actually, `attention_to_hulaquan` seems to be a flag for receiving updates.
            # If 0, legacy bot would not push. In new bot, if they possess subscriptions but turn off global switch..
            # We don't have a global mute switch on User model, but we have SubscriptionOption.mute on Subscription.
            
            # Let's save.
            session.add(db_user)
            session.commit()
            session.refresh(db_user)

            # 2. Handle Subscriptions
            sub_info = user_info.get("subscribe", {})
            legacy_events = sub_info.get("subscribe_events", [])
            legacy_actors = sub_info.get("subscribe_actors", [])
            
            has_legacy_subs = legacy_events or legacy_actors
            
            if has_legacy_subs:
                # Ensure Subscription Group exists
                db_sub = session.exec(select(Subscription).where(Subscription.user_id == user_id)).first()
                if not db_sub:
                    db_sub = Subscription(user_id=user_id)
                    session.add(db_sub)
                    session.commit()
                    session.refresh(db_sub)
                
                # Check/Create SubscriptionOption
                db_opt = session.exec(select(SubscriptionOption).where(SubscriptionOption.subscription_id == db_sub.id)).first()
                if not db_opt:
                    db_opt = SubscriptionOption(subscription_id=db_sub.id)
                    # Use legacy 'attention_to_hulaquan' to decide mute status?
                    attention = str(user_info.get("attention_to_hulaquan", "1"))
                    if attention == "0":
                         db_opt.mute = True
                    session.add(db_opt)
                    session.commit()

                # Migrate Targets
                # Helper to add target
                def add_target(kind, tid, name):
                    # Check existing
                    existing_target = session.exec(
                        select(SubscriptionTarget).where(
                            SubscriptionTarget.subscription_id == db_sub.id,
                            SubscriptionTarget.kind == kind,
                            SubscriptionTarget.target_id == tid
                        )
                    ).first()
                    
                    if not existing_target:
                        target = SubscriptionTarget(
                            subscription_id=db_sub.id,
                            kind=kind,
                            target_id=tid,
                            name=name
                        )
                        session.add(target)
                        return True
                    return False

                # Migrate Events (Play)
                for item in legacy_events:
                    eid = str(item.get("id"))
                    title = event_titles.get(eid, f"Legacy Event {eid}")
                    # Clean title if possible? E.g. remove city prefix? 
                    # For now keep as is.
                    add_target(SubscriptionTargetKind.PLAY, eid, title)

                # Migrate Actors
                for item in legacy_actors:
                    actor_name = item.get("actor")
                    if actor_name:
                        add_target(SubscriptionTargetKind.ACTOR, actor_name, actor_name)
                
                session.commit()

            processed_users += 1
            if processed_users % 10 == 0:
                logger.info(f"Processed {processed_users}/{total_users} users...")

        logger.info(f"Migration completed. Processed {processed_users} users.")

if __name__ == "__main__":
    migrate()
