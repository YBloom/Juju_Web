import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import select, col
from services.db.connection import session_scope
from services.hulaquan.tables import TicketUpdateLog

def diagnose_updates():
    print("--- Diagnosing Ticket Updates (Sync) ---")
    with session_scope() as session:
        # Count all
        stmt_count = select(TicketUpdateLog)
        updates = session.exec(stmt_count).all()
        print(f"Total Ticket Updates in DB: {len(updates)}")
        
        if len(updates) == 0:
            print("DB IS EMPTY. No ticket updates found.")
            return

        # Show latest 10
        print("\n--- Latest 10 Updates ---")
        stmt_latest = select(TicketUpdateLog).order_by(col(TicketUpdateLog.created_at).desc()).limit(10)
        latest = session.exec(stmt_latest).all()

        for u in latest:
            print(f"[{u.created_at}] Type: {u.change_type} | Event: {u.event_title} | Stock: {u.stock} | Price: {u.price}")

if __name__ == "__main__":
    diagnose_updates()
