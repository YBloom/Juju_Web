#!/usr/bin/env python3
"""
Inspect SubscriptionTarget Kinds
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.db.connection import session_scope

def inspect_kinds():
    with session_scope() as session:
        # Check distinct kinds
        result = session.exec(text("SELECT kind, count(*) FROM subscriptiontarget GROUP BY kind")).all()
        print("📊 Distinct Kinds in DB:")
        for row in result:
            print(f"  - {row[0]}: {row[1]}")
            
        print("\n🔍 Sample records with empty names:")
        # Check sample empty names
        result_empty = session.exec(text("SELECT id, kind, target_id, name FROM subscriptiontarget WHERE name IS NULL OR name = '' LIMIT 5")).all()
        if not result_empty:
            print("  (No records with empty names found)")
        for row in result_empty:
            print(f"  - ID: {row[0]}, Kind: {row[1]}, TargetID: {row[2]}, Name: '{row[3]}'")

if __name__ == "__main__":
    inspect_kinds()
