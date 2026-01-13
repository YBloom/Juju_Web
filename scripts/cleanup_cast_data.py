
"""
Clean up corrupted HulaquanCast data.
This script removes or fixes cast entries that are actually role names (like 林贞, 陈潇)
or malformed entries containing multiple role/actor pairs.
"""
import sys
sys.path.insert(0, '.')

from services.db.connection import session_scope
from services.hulaquan.tables import HulaquanCast, TicketCastAssociation
from sqlmodel import select, col, delete

def cleanup_cast_data(dry_run=True):
    with session_scope() as session:
        # 1. Find and remove single role names mistakenly stored as actors
        single_role_names = ["林贞", "陈潇"]
        
        for name in single_role_names:
            stmt = select(HulaquanCast).where(HulaquanCast.name == name)
            cast = session.exec(stmt).first()
            if cast:
                print(f"{'[DRY RUN] ' if dry_run else ''}Deleting cast: {cast.name} (id={cast.id})")
                if not dry_run:
                    # First delete associations
                    session.exec(delete(TicketCastAssociation).where(TicketCastAssociation.cast_id == cast.id))
                    # Then delete the cast entry
                    session.delete(cast)
        
        # 2. Find and remove malformed entries (containing multiple colons or very long names)
        stmt = select(HulaquanCast).where(
            (col(HulaquanCast.name).contains(":")) | 
            (col(HulaquanCast.name).contains(" "))
        )
        malformed = session.exec(stmt).all()
        
        print(f"\nFound {len(malformed)} malformed entries:")
        for cast in malformed:
            print(f"  {'[DRY RUN] ' if dry_run else ''}Deleting: {cast.name[:50]}... (id={cast.id})")
            if not dry_run:
                session.exec(delete(TicketCastAssociation).where(TicketCastAssociation.cast_id == cast.id))
                session.delete(cast)
        
        if not dry_run:
            print("\n✓ Cleanup complete. Changes committed.")
        else:
            print("\n[DRY RUN] No changes made. Run with dry_run=False to apply changes.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    args = parser.parse_args()
    
    cleanup_cast_data(dry_run=not args.apply)
