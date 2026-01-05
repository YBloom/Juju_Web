
import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, text

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Import default path from connection module
from services.db.connection import DEFAULT_DB_PATH

def migrate():
    print(f"Checking database at: {DEFAULT_DB_PATH}")
    if not DEFAULT_DB_PATH.exists():
        print("Database file not found!")
        return

    engine = create_engine(f"sqlite:///{DEFAULT_DB_PATH}")
    
    with engine.connect() as conn:
        # Check if column exists
        try:
            conn.execute(text("SELECT is_ignored FROM feedback LIMIT 1"))
            print("Column 'is_ignored' already exists.")
        except Exception:
            print("Column 'is_ignored' not found. Adding it...")
            try:
                # Add columns
                conn.execute(text("ALTER TABLE feedback ADD COLUMN is_ignored BOOLEAN DEFAULT 0"))
                conn.execute(text("ALTER TABLE feedback ADD COLUMN ignored_at DATETIME"))
                print("Columns added successfully.")
            except Exception as e:
                print(f"Error adding columns: {e}")
                
if __name__ == "__main__":
    migrate()
