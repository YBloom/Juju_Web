import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import text
from services.db.connection import get_engine
from services.db.models import User

def update_schema():
    print(">>> Checking database schema...")
    engine = get_engine()
    
    with engine.connect() as conn:
        # Check if auth_provider column exists
        result = conn.execute(text("PRAGMA table_info(user)")).fetchall()
        columns = [row[1] for row in result]
        
        new_columns = {
            "auth_provider": "VARCHAR(32) DEFAULT 'qq'",
            "auth_id": "VARCHAR(128)",
            "email": "VARCHAR(255)",
            "avatar_url": "VARCHAR(512)",
            "bot_interaction_mode": "VARCHAR(20) DEFAULT 'hybrid'"
        }
        
        for col, definition in new_columns.items():
            if col not in columns:
                print(f">>> Adding missing column: {col}")
                try:
                    conn.execute(text(f"ALTER TABLE user ADD COLUMN {col} {definition}"))
                    conn.commit()  # Important for sqlite
                except Exception as e:
                    print(f"!!! Error adding column {col}: {e}")
            else:
                print(f">>> Column {col} already exists.")

    print(">>> Schema update complete.")

if __name__ == "__main__":
    update_schema()
