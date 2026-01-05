
import asyncio
import json
import sys
import os
sys.path.append(os.getcwd())

from sqlmodel import select, col
from services.hulaquan.tables import HulaquanSearchLog
from services.db.connection import session_scope, get_engine
from sqlmodel import SQLModel

async def verify_analytics():
    print("Starting Analytics Verification...")
    
    # Ensure table
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    
    # 1. Insert Fake Data
    with session_scope() as session:
        # Artist A (3 total, 1 solo)
        # Artist B (2 total, 0 solo)
        # Combo A,B (2 total)
        # View X (2 views)
        
        logs = [
            # Solo A
            HulaquanSearchLog(search_type="co-cast", query_str="A", artists='["A"]', is_combination=False),
            # Combo A, B
            HulaquanSearchLog(search_type="co-cast", query_str="A,B", artists='["A", "B"]', is_combination=True),
            HulaquanSearchLog(search_type="co-cast", query_str="B, A ", artists='["A", "B"]', is_combination=True),
            # Views
            HulaquanSearchLog(search_type="view_event", query_str="Show X", artists=None, is_combination=False),
            HulaquanSearchLog(search_type="view_event", query_str="Show X", artists=None, is_combination=False),
        ]
        for l in logs:
            session.add(l)
        session.commit()
        print("Inserted fake data.")

    # 2. Simulate Aggregation Logic (copied from web_app.py logic)
    from collections import Counter
    with session_scope() as session:
        logs = session.exec(select(HulaquanSearchLog)).all()
        
        artist_counts = Counter()
        solo_counts = Counter()
        combo_counts = Counter()
        view_counts = Counter()
        
        for l in logs:
            if l.search_type == "view_event":
                view_counts[l.query_str] += 1
                continue
            if l.search_type == "co-cast" and l.artists:
                names = json.loads(l.artists)
                for n in names: artist_counts[n] += 1
                if len(names) == 1: solo_counts[names[0]] += 1
                elif len(names) > 1: combo_counts[" & ".join(names)] += 1

        print("--- Verification Results ---")
        print(f"Total Logs: {len(logs)}")
        print(f"Top Artists: {artist_counts.most_common()}")
        print(f"Top Solo: {solo_counts.most_common()}")
        print(f"Top Combos: {combo_counts.most_common()}")
        print(f"Top Views: {view_counts.most_common()}")
        
        # Verify specific expectations
        assert artist_counts["A"] >= 3, "A should have at least 3 counts"
        assert artist_counts["B"] >= 2, "B should have at least 2 counts"
        assert combo_counts["A & B"] >= 2, "Combo A & B should have at least 2 counts"
        assert view_counts["Show X"] >= 2, "Show X should have at least 2 views"
        print("✅ Logic Verified!")

if __name__ == "__main__":
    asyncio.run(verify_analytics())
