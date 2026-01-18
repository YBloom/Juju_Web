import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from services.db.connection import get_engine
from sqlalchemy import text

def fix_schema():
    engine = get_engine()
    with engine.connect() as conn:
        print("Starting schema fix...")
        
        # Check existing columns first to avoid errors if re-run
        current_cols = [row[1] for row in conn.execute(text('PRAGMA table_info(user)')).fetchall()]
        
        commands = [
            ("auth_provider", "ALTER TABLE user ADD COLUMN auth_provider VARCHAR(32) DEFAULT 'qq'"),
            ("auth_id", "ALTER TABLE user ADD COLUMN auth_id VARCHAR(128)"),
            ("email", "ALTER TABLE user ADD COLUMN email VARCHAR(255)"),
            ("avatar_url", "ALTER TABLE user ADD COLUMN avatar_url VARCHAR(512)"),
            ("bot_interaction_mode", "ALTER TABLE user ADD COLUMN bot_interaction_mode VARCHAR(20) DEFAULT 'hybrid'"),
        ]

        for col_name, sql in commands:
            if col_name not in current_cols:
                print(f"Adding column: {col_name}")
                conn.execute(text(sql))
            else:
                print(f"Column {col_name} already exists.")
        
        # Index creation (idempotent check is harder with SQL, usually CREATE INDEX IF NOT EXISTS works in newer SQLite)
        # But for safety, try/except
        try:
            print("Creating index ix_user_email...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_email ON user (email)"))
        except Exception as e:
            print(f"Index creation warning: {e}")

        conn.commit()
        print("Schema fix complete.")

if __name__ == "__main__":
    fix_schema()
