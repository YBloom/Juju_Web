import sys
import os
sys.path.append(os.getcwd())

from sqlmodel import Session, select, func
from services.db.models.user import User
from services.db.models.subscription import Subscription, SubscriptionTarget
from services.db.connection import get_engine

full_path = "/Users/yaobii/Developer/MY PROJECTS/MusicalBot/data/musicalbot.db"
# If running inside MusicalBot, use get_engine directly (which uses default path or from helper)
# But get_engine resolves path relative to FILE if not provided? 
# connection.py says: DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "musicalbot.db"
# PROJECT_ROOT is up 3 levels from connection.py (services/db).
# So it should be correct.

engine = get_engine()

def verify():
    with Session(engine) as session:
        user_count = session.exec(select(func.count(User.user_id))).one()
        sub_count = session.exec(select(func.count(Subscription.id))).one()
        target_count = session.exec(select(func.count(SubscriptionTarget.id))).one()
        
        print(f"Users: {user_count}")
        print(f"Subscriptions: {sub_count}")
        print(f"Targets: {target_count}")

if __name__ == "__main__":
    verify()
