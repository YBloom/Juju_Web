
import sys
import os
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from services.db.connection import session_scope

def fix_enum_case():
    print("Starting Enum case fix...")
    with session_scope() as session:
        # Check count of lowercase values
        count_query = text("SELECT count(*) FROM user WHERE notification_freq = 'realtime' OR notification_freq = 'hourly' OR notification_freq = 'daily'")
        count = session.execute(count_query).scalar()
        print(f"Found {count} rows with lowercase values.")

        if count > 0:
            print("Updating lowercase values to UPPERCASE...")
            # Update realtime -> REALTIME
            session.execute(text("UPDATE user SET notification_freq = 'REALTIME' WHERE notification_freq = 'realtime'"))
            # Update hourly -> HOURLY
            session.execute(text("UPDATE user SET notification_freq = 'HOURLY' WHERE notification_freq = 'hourly'"))
            # Update daily -> DAILY
            session.execute(text("UPDATE user SET notification_freq = 'DAILY' WHERE notification_freq = 'daily'"))
            
            session.commit()
            print("Update complete.")
        else:
            print("No updates needed.")
            
        # Verify
        verify_query = text("SELECT notification_freq, count(*) FROM user GROUP BY notification_freq")
        result = session.execute(verify_query)
        print("\nCurrent distribution:")
        for row in result:
            print(f"{row[0]}: {row[1]}")

if __name__ == "__main__":
    fix_enum_case()
