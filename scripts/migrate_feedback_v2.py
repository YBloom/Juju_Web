#!/usr/bin/env python3
import sqlite3
import sys
from pathlib import Path

# Add project root to path to import services
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

try:
    from services.db.connection import DEFAULT_DB_PATH
except ImportError:
    # Fallback if import fails (though it shouldn't)
    print("Warning: Could not import DEFAULT_DB_PATH, using fallback.")
    DEFAULT_DB_PATH = project_root / "data" / "musicalbot.db"

def migrate():
    print(f"Migrating database at: {DEFAULT_DB_PATH}")
    
    if not DEFAULT_DB_PATH.exists():
        print("Error: Database file not found!")
        return

    conn = sqlite3.connect(DEFAULT_DB_PATH)
    c = conn.cursor()
    
    # 1. Check existing columns in feedback table
    try:
        c.execute("PRAGMA table_info(feedback)")
        columns_info = c.fetchall()
        existing_columns = [col[1] for col in columns_info]
        
        if not existing_columns:
            print("Table 'feedback' does not exist. It will be created by the app automatically.")
            return

        print(f"Existing columns: {existing_columns}")
        
        # 2. Add is_public
        if 'is_public' not in existing_columns:
            print("Adding 'is_public' column...")
            c.execute("ALTER TABLE feedback ADD COLUMN is_public BOOLEAN DEFAULT 0")
        else:
            print("'is_public' column already exists.")
            
        # 3. Add admin_reply
        if 'admin_reply' not in existing_columns:
            print("Adding 'admin_reply' column...")
            c.execute("ALTER TABLE feedback ADD COLUMN admin_reply VARCHAR")
        else:
            print("'admin_reply' column already exists.")
            
        # 4. Add reply_at
        if 'reply_at' not in existing_columns:
            print("Adding 'reply_at' column...")
            c.execute("ALTER TABLE feedback ADD COLUMN reply_at DATETIME")
        else:
            print("'reply_at' column already exists.")

        # 5. Add wish type support (Enum check is hard in SQLite, usually strictly checked by app code, so skipping constraint update)
        # However, checking if 'type' column exists is good (it should).
        
        conn.commit()
        print("Migration completed successfully.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
