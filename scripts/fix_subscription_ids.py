
import asyncio
import logging
import os
import sys

# Ensure services module is visible
sys.path.append(os.getcwd())

from sqlmodel import select
from services.db.connection import session_scope
from services.db.models import SubscriptionTarget
from services.db.models.base import SubscriptionTargetKind
from services.hulaquan.service import HulaquanService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger("fix_sub_ids")

async def fix_ids():
    log.info("Starting Subscription ID Fix...")
    service = HulaquanService()
    
    with session_scope() as session:
        # Find Play targets
        stmt = select(SubscriptionTarget).where(SubscriptionTarget.kind == SubscriptionTargetKind.PLAY)
        targets = session.exec(stmt).all()
        log.info(f"Found {len(targets)} play subscriptions to check.")
        
        counts = {"checked": 0, "fixed": 0, "failed": 0, "skipped_valid": 0}
        
        for t in targets:
            counts["checked"] += 1
            tid = t.target_id
            
            # Heuristic: Valid IDs are usually numeric (or at least digits), and typically short < 20.
            # Titles often contain non-ascii or are just words.
            # If it's pure decimal digits, assume it's valid ID (legacy IDs like 12345).
            # If it looks like UUID (hex 32 chars), assume valid.
            
            is_digit = tid.isdigit()
            is_uuid = len(tid) == 32 and all(c in "0123456789abcdef" for c in tid.lower())
            
            if is_digit or is_uuid:
                counts["skipped_valid"] += 1
                continue
                
            log.info(f"🔍 Checking suspicious target_id: '{tid}' (Name: {t.name}) user={t.subscription_id}")
            
            # It's likely a title stored as ID
            search_query = t.name or tid
            if not search_query:
                log.warning(f"⚠️ Skipping empty name/id target {t.id}")
                counts["failed"] += 1
                continue
                
            try:
                # Use smart search
                events = await service.search_events_smart(search_query)
                
                # Look for exact title match
                match = None
                # First pass: Exact match
                for e in events:
                    if e.title == search_query:
                        match = e
                        break
                
                # Second pass: If only one result, assume it's it
                if not match and len(events) == 1:
                    match = events[0]
                    log.info(f"  Single match found: {match.title}")

                if match:
                    old_id = t.target_id
                    t.target_id = match.id
                    t.name = match.title # Ensure name is correct
                    session.add(t)
                    log.info(f"✅ Fixed: '{old_id}' -> ID {match.id} ({match.title})")
                    counts["fixed"] += 1
                else:
                    log.warning(f"⚠️ Could not resolve unique ID for: '{search_query}'. Found {len(events)} matches.")
                    counts["failed"] += 1
                    
            except Exception as e:
                log.error(f"❌ Error resolving '{search_query}': {e}")
                counts["failed"] += 1
        
        session.commit()
        log.info(f"Fix complete. Summary: {counts}")

if __name__ == "__main__":
    try:
        asyncio.run(fix_ids())
    except KeyboardInterrupt:
        pass
