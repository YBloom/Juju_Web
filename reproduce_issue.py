import aiohttp
import asyncio
import ssl

async def test_connection():
    url = "https://clubz.cloudsation.com/site/getevent.html?filter=recommendation&access_token=&limit=95&page=0"
    print(f"Testing connection to: {url}")
    
    # Matching the code in service.py
    connector = aiohttp.TCPConnector(ssl=False)
    timeout = aiohttp.ClientTimeout(total=60, connect=15)
    
    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url) as response:
                print(f"Status: {response.status}")
                content = await response.read()
                print(f"Content length: {len(content)}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
