
import asyncio
import os
import sys
sys.path.append(os.getcwd())

from services.saoju.service import SaojuService

async def test_match_co_casts():
    print("Testing match_co_casts role resolution...")
    service = SaojuService()
    await service._ensure_session()
    
    # 1. Ensure indexes are loaded (mock or fetch)
    # This might take a moment if not cached
    print("Ensuring indexes...")
    await service.ensure_musical_map()
    await service._ensure_artist_map()
    await service._ensure_artist_indexes()
    
    # 2. Pick a known artist
    artist_name = "郑棋元" # A very active actor
    print(f"Searching for {artist_name}...")
    
    results = await service.match_co_casts([artist_name])
    
    print(f"Found {len(results)} results.")
    
    found_role = False
    for r in results[:5]:
        print(f"Date: {r['date']}, Title: {r['title']}, Role: {r['role']}")
        if r['role'] and r['role'].strip() and r['role'] != "见详情":
            found_role = True
            
    if results and not found_role:
        print("⚠️ Warning: No roles resolved (all empty or '见详情'?). Could be data issue or logic.")
    elif results:
        print("✅ Success: Roles resolved!")
    else:
        print("Empty results, try another artist.")

    await service.close()

if __name__ == "__main__":
    asyncio.run(test_match_co_casts())
