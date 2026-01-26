
import asyncio
import sys
import os
import logging
import argparse
from datetime import datetime, timedelta
from sqlalchemy import text

# Add project root to path
sys.path.append(os.getcwd())

from services.hulaquan.service import HulaquanService
from services.saoju.service import SaojuService
from services.db.connection import get_engine
from sqlmodel import Session, select
from services.hulaquan.tables import HulaquanTicket, TicketCastAssociation, HulaquanEvent, SaojuShow

# Reuse migration logic
from scripts.migrate_saoju_show import migrate as run_schema_migration

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

def ask_confirmation(prompt: str) -> bool:
    """Ask user for confirmation."""
    if os.environ.get("FORCE_RUN"):
        return True
    response = input(f"{prompt} [y/N]: ").lower().strip()
    return response == 'y'

async def perform_reset(dry_run: bool = False):
    log.info("Starting Global Data Reset & Sync...")
    if dry_run:
        log.info("[DRY RUN] No changes will be committed to DB.")

    # 1. Schema Migration & Truncate
    # This acts as the "Truncate" step since it drops and recreates the table
    if not dry_run:
        log.info("Step 1: Resetting SaojuShow Table (Drop & Create)...")
        try:
            run_schema_migration()
        except Exception as e:
            log.error(f"Migration/Reset failed: {e}")
            return
    else:
        log.info("Step 1: [DRY RUN] Would Drop & Recreate SaojuShow table.")

    # Initialize Services
    saoju = SaojuService()
    hulaquan = HulaquanService()

    try:
        async with saoju, hulaquan:
            # 2. Global Sync (Future 180 Days + Past 30 Days)
            # Past 30 days to fix recent history, Future 180 for upcoming
            start_history = -30
            end_future = 180
            
            log.info(f"Step 2: Syncing Saoju Data (Range: T{start_history} to T+{end_future})...")
            if not dry_run:
                # Sync logic is idempotent but we just wiped the table, so it's a full fetch
                # Sync Past
                await saoju.sync_future_days(start_days=start_history, end_days=-1)
                # Sync Future
                await saoju.sync_future_days(start_days=0, end_days=end_future)
            else:
                log.info(f"Step 2: [DRY RUN] Would sync days from {start_history} to {end_future}.")

            # 3. Ticket Refresh
            log.info("Step 3: Refreshing Tickets (Clear Casts & Re-sync)...")
            
            engine = get_engine()
            with Session(engine) as session:
                # Get all active or pending events
                # We want to refresh everything that is currently relevant
                stmt = select(HulaquanEvent).where(
                    (HulaquanEvent.tickets.any(HulaquanTicket.status == "active")) | 
                    (HulaquanEvent.tickets.any(HulaquanTicket.status == "pending"))
                )
                # Or just all events? Better all active events to be safe.
                # Let's target events with actual tickets.
                events = session.exec(stmt).unique().all()
                log.info(f"Found {len(events)} events to refresh.")
                
                for event in events:
                    log.info(f"Processing Event: {event.title} (ID: {event.id})")
                    
                    if not dry_run:
                        # Clear Cast Associations for this event's tickets
                        # We do this one by one or batch?
                        # Let's find tickets first
                        t_stmt = select(HulaquanTicket).where(HulaquanTicket.event_id == event.id)
                        tickets = session.exec(t_stmt).all()
                        
                        for t in tickets:
                            # Reset city to None to force re-discovery/update from Hulaquan API if possible
                            # OR trust Hulaquan API to update it.
                            # If we set to None, we assume the sync logic updates it.
                            # Based on HulaquanService.sync_event_details, it updates attributes from API.
                            # So clearing it is safe if API provides it.
                            # But if API fails, we lose data.
                            # Safe bet: Don't clear city blindly, but let sync overwrite it.
                            # However, to fix "stuck" wrong cities, we rely on the generic sync logic.
                            pass

                        # Clear associations
                        # session.exec(delete(TicketCastAssociation)...)
                        # SQLAlchemy delete with join is complex in SQLModel, loop is safer
                        for t in tickets:
                            # Prune existing cast
                            for link in t.cast_members:
                                # We can't remove from list easily in loop without session delete on association
                                # Find association
                                assocs = session.exec(select(TicketCastAssociation).where(TicketCastAssociation.ticket_id == t.id)).all()
                                for a in assocs:
                                    session.delete(a)
                        
                        session.commit()
                        
                        # Trigger Sync
                        # Note: sync_event_details is async and makes network requests
                        # We need to call it outside the blocking session usage usually?
                        # No, hulaquan service manages its own session/db usage.
                        # We should commit our clears first.
                    else:
                        log.info(f"  [DRY RUN] Would clear casts for Event {event.id}")

                    if not dry_run:
                        try:
                            updates = await hulaquan._sync_event_details(event.id)
                            if updates:
                                log.info(f"  > Refreshed {len(updates)} tickets.")
                        except Exception as e:
                            log.error(f"  > Failed to sync event {event.id}: {e}")
                            
            log.info("Global Reset Completed.")

    except Exception as e:
        log.error(f"Reset failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description="Global Data Reset & Sync")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without changes")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    args = parser.parse_args()

    if not args.dry_run and not args.force:
        if not ask_confirmation("WARNING: This will DROP the SaojuShow table and re-sync ALL data. Are you sure?"):
            print("Aborted.")
            sys.exit(0)

    asyncio.run(perform_reset(dry_run=args.dry_run))

if __name__ == "__main__":
    main()
