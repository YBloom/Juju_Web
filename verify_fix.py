import asyncio
import logging
import sys
from unittest.mock import MagicMock, AsyncMock
import aiohttp

# Mocking modules before import to avoid full DB init if possible, 
# but HulaquanService imports many things. 
# Let's try to patch the class method AFTER import, assuming DB init is safe or we assume environment is okay.
# Actually, let's just mock the critical parts if we can't import easily.
# But we need to verify the ACTUAL code logic in sync_all_data.

# We will try to import. if DB fails, we handle it.
try:
    from services.hulaquan.service import HulaquanService
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Init failed (likely DB), but maybe we can still mock: {e}")
    # Continue if it's just DB connection error, we might mock objects
    pass

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

async def test_fail_fast():
    print("--- Testing Fail Fast ---")
    
    # 1. Instantiate Service (Mocking dependencies if needed)
    # logic involves self.venue_rules, self._saoju etc.
    # We can probably mock generic service if import worked.
    service = HulaquanService()
    
    # 2. Mock _fetch_json to raise ClientConnectorError
    # We need to simulate the exception that _fetch_json now re-raises.
    # Wait, I modified _fetch_json to raise. So I should mock the underlying session.get 
    # OR simply mock _fetch_json to raise, to test sync_all_data's handling.
    # Testing _fetch_json's own logic (raising) requires checking _fetch_json. 
    # Testing sync_all_data requires checking sync_all_data.
    
    # Let's test sync_all_data first.
    # Mock _fetch_json to raise ClientConnectorError
    error = aiohttp.ClientConnectorError(connection_key=None, os_error=OSError("Mock Connection Fail"))
    service._fetch_json = AsyncMock(side_effect=error)
    
    # 3. Run sync_all_data
    print("Calling sync_all_data...")
    updates = await service.sync_all_data()
    
    # 4. Verify
    print(f"Call count: {service._fetch_json.call_count}")
    if service._fetch_json.call_count == 1:
        print("PASS: Stopped after 1 attempt.")
    else:
        print(f"FAIL: Expected 1 attempt, got {service._fetch_json.call_count}")

    # Reset
    service._fetch_json.reset_mock()

async def test_fetch_json_raises():
    print("\n--- Testing _fetch_json raises ---")
    service = HulaquanService()
    # verify that _fetch_json re-raises exception
    
    # Mock session
    mock_session = MagicMock()
    mock_response = AsyncMock()
    # Mock get context manager
    mock_session.get.return_value.__aenter__.return_value = mock_response
    mock_session.get.side_effect = aiohttp.ClientConnectorError(connection_key=None, os_error=OSError("Mock Fail"))
    
    service._session = mock_session
    
    try:
        await service._fetch_json("http://test.com")
        print("FAIL: _fetch_json did not raise Exception")
    except aiohttp.ClientConnectorError:
        print("PASS: _fetch_json re-raised ClientConnectorError")
    except Exception as e:
        print(f"FAIL: Raised wrong exception: {type(e)}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(test_fail_fast())
    loop.run_until_complete(test_fetch_json_raises())
