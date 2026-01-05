import asyncio
import logging
import sys
import os

# We need to setup path to import services
sys.path.append(os.getcwd())

from services.hulaquan.service import HulaquanService
from services.hulaquan.tables import Feedback, HulaquanEvent, HulaquanTicket
from services.db.connection import session_scope

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("test")

async def mock_saoju_delay():
    """Simulate slow Saoju API"""
    await asyncio.sleep(2)
    return {"city": "MockCity", "casts": [{"artist": "TestArtist", "role": "TestRole"}]}

async def test_concurrency_fix():
    print("--- Testing DB Concurrency Fix ---")
    service = HulaquanService()
    
    # Mock _fetch_json to return dummy data fast
    async def mock_fetch(url):
        log.info(f"Mock fetching {url}")
        return {
            "basic_info": {"id": "test_e1", "title": "Test Event 1 [Musical]", "start_time": "2026-05-01", "end_time": "2026-05-01"},
            "ticket_details": [
                {"id": "test_t1", "title": "Test Ticket", "ticket_price": 100, "total_ticket": 100, "left_ticket_count": 50, "start_time": "2026-05-01 19:30"}
            ]
        }
    service._fetch_json = mock_fetch

    # Spy on _enrich_ticket_data_async to ensure it's doing "slow" work outside DB
    # We will inject a delay in _enrich_ticket_data_async by wrapping it
    original_enrich = service._enrich_ticket_data_async
    async def fast_enrich(event_id, data, ctx):
        log.info("Enriching (Simulating 3s network delay)...")
        await asyncio.sleep(3)
        # Call original logic or return dummy
        # To avoid actual network calls, return dummy
        return {
            "saoju_musical_id": "123",
            "tickets": {"test_t1": {"city": "Delayed City", "casts": [{"artist": "Delayed Artist", "role": "Lead"}]}}
        }
    service._enrich_ticket_data_async = fast_enrich

    # Background task: Sync
    async def background_sync():
        log.info("Starting background sync details...")
        await service._sync_event_details("test_e1")
        log.info("Background sync finished.")

    # Foreground task: Write feedback
    async def foreground_write():
        # Wait 1s so sync is definitely in "Network Phase" (sleeping 3s)
        await asyncio.sleep(1)
        log.info("Attempting foreground DB write (Feedback)...")
        start = asyncio.get_running_loop().time()
        
        try:
            # Run in thread as real app does
            await asyncio.to_thread(write_feedback_sync)
            duration = asyncio.get_running_loop().time() - start
            log.info(f"Foreground write success! Duration: {duration:.3f}s")
            if duration > 1.0:
                 log.error("FAIL: Write blocked for too long!")
            else:
                 log.info("PASS: Write happened fast during sync delay.")
        except Exception as e:
            log.error(f"Foreground write failed: {e}")

    def write_feedback_sync():
        with session_scope() as session:
            fb = Feedback(type="test", content="Concurrency Test")
            session.add(fb)
            session.commit()

    # Run both
    await asyncio.gather(background_sync(), foreground_write())

if __name__ == "__main__":
    asyncio.run(test_concurrency_fix())
