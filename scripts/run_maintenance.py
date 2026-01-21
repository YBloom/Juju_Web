import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from services.hulaquan.service import HulaquanService

async def main():
    print("Running legacy data maintenance...")
    service = HulaquanService()
    await service.fix_legacy_data()
    await service.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())

