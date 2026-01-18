
import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from services.db.connection import session_scope
from services.hulaquan.tables import TicketUpdateLog, HulaquanTicket, TicketStatus
from services.utils.timezone import now as timezone_now
from sqlmodel import select, or_, and_, col

async def main():
    print("--- Debugging Ticket Updates ---")
    
    with session_scope() as session:
        # 1. Check Total Logs count
        total_logs = session.exec(select(TicketUpdateLog)).all()
        print(f"Total TicketUpdateLog entries: {len(total_logs)}")
        
        if not total_logs:
            print("No logs found. Problem is upstream (scanner not finding updates).")
            return

        # 2. Check Logs that would be returned by current rigorous query
        now = timezone_now()
        print(f"Server Time (Shanghai): {now}")
        
        stmt = select(TicketUpdateLog).join(HulaquanTicket, TicketUpdateLog.ticket_id == HulaquanTicket.id)
        
        # Current Logic Filters
        # Filter 1: Real-time Status
        status_filter = or_(
            HulaquanTicket.status == TicketStatus.PENDING,
            and_(
                HulaquanTicket.status == TicketStatus.ACTIVE,
                HulaquanTicket.stock > 0
            )
        )
        stmt = stmt.where(status_filter)
        
        # Filter 2: Future Session
        time_filter = or_(
            HulaquanTicket.session_time >= now,
            HulaquanTicket.session_time == None
        )
        stmt = stmt.where(time_filter)
        
        stmt = stmt.order_by(col(TicketUpdateLog.created_at).desc()).limit(20)
        
        results = session.exec(stmt).all()
        print(f"Query returned {len(results)} results.")
        
        if len(results) == 0:
            print("\n--- Investigating why logs are filtered ---")
            # Let's look at the most recent 5 logs and see why they fail
            recent_logs = session.exec(select(TicketUpdateLog).order_by(col(TicketUpdateLog.created_at).desc()).limit(5)).all()
            
            for log in recent_logs:
                print(f"\nLog ID: {log.id} | Type: '{log.change_type}' | Created: {log.created_at}")
                print(f"Message: {log.message}")
                
                   # Check if type matches expected lowercase
                expected_types = ["new", "restock", "back", "pending"]
                if log.change_type not in expected_types:
                    print(f"  WARNING: Type '{log.change_type}' is NOT in expected list {expected_types}!")

                ticket = session.get(HulaquanTicket, log.ticket_id)
                if not ticket:
                    print(f"  -> Ticket {log.ticket_id} NOT FOUND in DB.")
                    continue
                
                print(f"  -> Ticket Status: {ticket.status}")
                print(f"  -> Ticket Stock: {ticket.stock}")
                print(f"  -> HulaquanTicket Session Time: {ticket.session_time}")
                print(f"  -> Log Session Time: {log.session_time}") # Check log's copy
                
                # Check Filters
                is_pending = ticket.status == TicketStatus.PENDING
                is_active_stock = (ticket.status == TicketStatus.ACTIVE and ticket.stock > 0)
                passes_status = is_pending or is_active_stock
                print(f"  -> Passes Status Filter (Pending OR (Active & Stock>0)): {passes_status}")
                
                if ticket.session_time:
                    # Handle naive/aware comparison for debug
                    t_time = ticket.session_time
                    if t_time.tzinfo is None:
                        print("     (Session time is naive, assuming Shanghai for check)")
                        from zoneinfo import ZoneInfo
                        t_time = t_time.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
                    
                    passes_time = t_time >= now
                    print(f"  -> Passes Time Filter (Future): {passes_time} (Diff: {(t_time - now).total_seconds()/3600:.2f}h)")
                else:
                    print("  -> Passes Time Filter (None): True")

if __name__ == "__main__":
    asyncio.run(main())
