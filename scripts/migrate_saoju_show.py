
import sys
import os
import logging
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from services.db.connection import get_engine
from sqlmodel import SQLModel, Session

# Import models to ensure they are registered in metadata
from services.hulaquan.tables import SaojuShow

def migrate():
    print("Starting SaojuShow Migration...")
    engine = get_engine()
    
    with Session(engine) as session:
        # 1. Drop old table
        print("Dropping table saojushow...")
        # Using raw SQL to be sure, or SQLModel metadata drop
        # Note: saoju_show table name might be 'saojushow' (lowercase default in SQLModel)
        # Check table name in definition? Defaults to class name lowercase.
        try:
            session.exec(text("DROP TABLE IF EXISTS saojushow"))
            session.commit()
            print("Table dropped.")
        except Exception as e:
            print(f"Error dropping table: {e}")
            
    # 2. Recreate table
    print("Recreating table saojushow with new schema...")
    # This will create all tables in metadata that don't exist
    SQLModel.metadata.create_all(engine)
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
