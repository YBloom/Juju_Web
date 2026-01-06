import asyncio
import logging
from datetime import datetime
from services.db.connection import session_scope
from services.hulaquan.tables import SaojuShow
from services.saoju.service import SaojuService

# Configure Logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def test_strict_db_lookup():
    """
    Verify that get_cast_for_hulaquan_session works by reading from DB.
    """
    saoju = SaojuService()
    
    # 1. Prepare Mock Data
    mock_date = datetime(2099, 1, 1, 19, 30) # Future date
    mock_title = "TestMusical_DB_ONLY"
    mock_city = "TestCity"
    mock_cast_str = "RoleA:ActorA / RoleB:ActorB"
    
    log.info(f"--- Setting up Mock Data in DB ---")
    log.info(f"Show: {mock_title} at {mock_date} in {mock_city}")
    log.info(f"Cast: {mock_cast_str}")
    
    with session_scope() as session:
        # Cleanup first
        existing = session.get(SaojuShow, (mock_date, mock_title))
        if existing:
            session.delete(existing)
            session.commit()
            
        # Insert
        show = SaojuShow(
            date=mock_date,
            musical_name=mock_title,
            city=mock_city,
            cast_str=mock_cast_str,
            source="manual_test"
        )
        session.add(show)
        session.commit() # Ensure written
        
    log.info("Mock data inserted.")
    
    # 2. Test Lookup
    log.info("--- Testing Lookup ---")
    
    # Successful Case
    log.info("Test 1: Exact Match Context")
    results = await saoju.get_cast_for_hulaquan_session(
        search_name=mock_title,
        session_time=mock_date,
        city=mock_city
    )
    
    if results:
        log.info(f"✅ Hit! Results: {results}")
        assert len(results) == 2
        assert results[0]['artist'] == 'ActorA'
    else:
        log.error("❌ Miss! Expected results but got None.")

    # Failed Case (Wrong City)
    log.info("Test 2: Wrong City (Should fail if city provided)")
    results_fail = await saoju.get_cast_for_hulaquan_session(
        search_name=mock_title,
        session_time=mock_date,
        city="WrongCity"
    )
    if not results_fail:
        log.info("✅ Correctly returned empty for wrong city.")
    else:
        log.error(f"❌ Unexpectedly found results for wrong city: {results_fail}")
        
    # Failed Case (No DB Record)
    log.info("Test 3: Non-existent Show (Should fail without API call)")
    # Since we can't easily assert "no network call" without mocking aiohttp, 
    # we rely on the fact that we deleted the API fallback code.
    # If this tries to call API, it might fail or return nothing if 2099 date is invalid for API.
    # But essentially we just want empty list.
    results_empty = await saoju.get_cast_for_hulaquan_session(
        search_name="NonExistentShow",
        session_time=mock_date,
        city=mock_city
    )
    
    if not results_empty:
         log.info("✅ Correctly returned empty for non-existent show.")
    else:
         log.error(f"❌ Unexpectedly found results: {results_empty}")

    # Cleanup
    with session_scope() as session:
        existing = session.get(SaojuShow, (mock_date, mock_title))
        if existing:
            session.delete(existing)
            session.commit()
    log.info("Cleaned up mock data.")

if __name__ == "__main__":
    asyncio.run(test_strict_db_lookup())
