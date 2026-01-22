
import asyncio
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from services.saoju.service import SaojuService
from services.db.connection import session_scope
from services.hulaquan.tables import HulaquanEvent, TicketCastAssociation, HulaquanTicket
from sqlmodel import select

async def main():
    print("Initialize SaojuService...")
    saoju = SaojuService()
    
    # 1. Ensure Indexes are loaded
    print("Loading Role Order Indexes...")
    indexes = await saoju._ensure_artist_indexes()
    role_orders = indexes.get("role_orders", {})
    
    if not role_orders:
        print("❌ Failed to load role_orders from Saoju data. Aborting.")
        await saoju.close()
        return

    print(f"✅ Loaded role orders for {len(role_orders)} musicals.")
    
    with session_scope() as session:
        # 2. Get all events with saoju_musical_id
        print("Scanning Hulaquan Events with linked Saoju ID...")
        stmt = select(HulaquanEvent).where(HulaquanEvent.saoju_musical_id.isnot(None))
        events = session.exec(stmt).all()
        
        print(f"Found {len(events)} linked events. Processing...")
        
        total_updated_assocs = 0
        events_touched = 0
        
        for event in events:
            mid = event.saoju_musical_id
            musical_roles = role_orders.get(str(mid), {})
            
            if not musical_roles:
                # No role order data for this musical
                continue
            
            # Get tickets first -> then CastAssociations
            # We can do a join to get relevant associations directly
            # Join Ticket table explicitly using foreign keys
            stmt_assoc = (
                select(TicketCastAssociation)
                .join(HulaquanTicket, TicketCastAssociation.ticket_id == HulaquanTicket.id)
                .where(HulaquanTicket.event_id == event.id)
            )
            
            associations = session.exec(stmt_assoc).all()
            
            event_has_changes = False
            for assoc in associations:
                role_name = assoc.role
                if not role_name: 
                    continue
                    
                correct_rank = musical_roles.get(role_name, 999)
                
                if assoc.rank != correct_rank:
                    assoc.rank = correct_rank
                    session.add(assoc)
                    total_updated_assocs += 1
                    event_has_changes = True
            
            if event_has_changes:
                events_touched += 1
                
        print(f"Committing changes to DB (Updated {total_updated_assocs} roles across {events_touched} events)...")
        session.commit()
        print("✅ Fix Complete.")

    await saoju.close()

if __name__ == "__main__":
    asyncio.run(main())
