import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from services.db.connection import session_scope
from services.hulaquan.tables import HulaquanTicket, HulaquanEvent
from sqlmodel import select

def check_event(title_part):
    with session_scope() as session:
        statement = select(HulaquanEvent).where(HulaquanEvent.title.contains(title_part))
        events = session.exec(statement).all()
        for e in events:
            print(f"\n🎭 Event: {e.title} (ID: {e.id})")
            for t in e.tickets:
                print(f"  🎫 Ticket: {t.title}")
                print(f"     Status: {t.status}, Valid From: {t.valid_from}, Stock: {t.stock}")

if __name__ == "__main__":
    print("🔍 Checking '命运之上'...")
    check_event("命运之上")
    print("\n🔍 Checking '男巫客厅'...")
    check_event("男巫客厅")
