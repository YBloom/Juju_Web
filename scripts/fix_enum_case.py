
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlmodel import Session, text
from services.db.connection import get_engine

def fix_enum_case():
    engine = get_engine()
    with Session(engine) as session:
        print("Checking for lowercase 'realtime'...")
        # Check count before
        result = session.exec(text("SELECT count(*) FROM user WHERE notification_freq = 'realtime'")).one()
        # Handle tuple/Row return
        count = result[0] if hasattr(result, '__getitem__') else result
        
        print(f"Found {count} records with notification_freq='realtime'")
        
        if count > 0:
            print("Fixing records to 'REALTIME'...")
            session.exec(text("UPDATE user SET notification_freq = 'REALTIME' WHERE notification_freq = 'realtime'"))
            session.commit()
            print("Fix applied successfully.")
        else:
            print("No records need fixing.")
            
        # Verify
        result_after = session.exec(text("SELECT count(*) FROM user WHERE notification_freq = 'realtime'")).one()
        count_after = result_after[0] if hasattr(result_after, '__getitem__') else result_after
        print(f"Remaining lowercase records: {count_after}")

if __name__ == "__main__":
    fix_enum_case()
