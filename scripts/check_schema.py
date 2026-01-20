#!/usr/bin/env python3
"""
Database Schema Check Script
Checks for missing tables and columns in the database compared to SQLAlchemy models.
"""
import sys
import os
import inspect
from sqlalchemy import create_engine, inspect as inspect_db
from sqlalchemy.engine import reflection
from sqlmodel import SQLModel

# Add project root to path
sys.path.append(os.getcwd())

# Import all models to register them with SQLModel
# Import your models here. Adapting to project structure
try:
    # Direct imports to avoid circular dependency issues in __init__
    from services.db.models.user import User
    from services.db.models.user_auth_method import UserAuthMethod
    from services.db.models.session import UserSession
    from services.db.models.subscription import Subscription, SubscriptionTarget, SubscriptionOption
    from services.db.models.event import Event, TicketUpdate
    from services.db.models.feedback import Feedback
    # Conditional imports for models that might not exist or be needed for core check
    try:
        from services.db.models.task import CastInfo, Task
    except ImportError:
        pass
except ImportError as e:
    print(f"Error importing models: {e}")
    sys.exit(1)

from services.db.connection import DATABASE_URL

def check_schema():
    print(f"Checking database schema against models...")
    print(f"Database URL: {DATABASE_URL}")
    
    engine = create_engine(DATABASE_URL)
    inspector = inspect_db(engine)
    
    db_tables = set(inspector.get_table_names())
    model_tables = set()
    
    missing_tables = []
    missing_columns = []
    
    # Get all SQLModel classes
    for name, cls in SQLModel._decl_class_registry.items():
        if isinstance(cls, type) and issubclass(cls, SQLModel) and hasattr(cls, "__tablename__"):
            table_name = cls.__tablename__
            model_tables.add(table_name)
            
            if table_name not in db_tables:
                # Skip alernbic_version and sqlite specific tables if any
                missing_tables.append(table_name)
                continue
                
            # Check columns
            db_columns = {col['name']: col for col in inspector.get_columns(table_name)}
            
            # Use mapper to get model columns
            if hasattr(cls, "__mapper__"):
                for prop in cls.__mapper__.c:
                    col_name = prop.name
                    if col_name not in db_columns:
                         missing_columns.append(f"{table_name}.{col_name}")

    print("\n=== SCHEMA CHECK REPORT ===")
    
    if not missing_tables and not missing_columns:
        print("✅ Database schema is in sync with models.")
        return True
        
    if missing_tables:
        print("\n❌ MISSING TABLES:")
        for table in missing_tables:
            print(f"  - {table}")
            
    if missing_columns:
        print("\n❌ MISSING COLUMNS:")
        for col in missing_columns:
            print(f"  - {col}")
            
    return False

if __name__ == "__main__":
    check_schema()
