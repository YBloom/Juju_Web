from fastapi import APIRouter, Request
import logging
from web.dependencies import saoju_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
logger = logging.getLogger(__name__)

@router.get("/summary")
async def get_summary():
    """获取数据艺廊概览统计数据。"""
    try:
        total_shows = await saoju_service.get_total_shows_count()
        return {"total_shows": total_shows}
    except Exception as e:
        logger.error(f"Error fetching summary stats: {e}")
        return {"total_shows": 0, "error": str(e)}

@router.get("/heatmap")
async def get_heatmap(year: int = 2025):
    """获取指定年份的演出热力图数据。"""
    try:
        data = await saoju_service.get_heatmap_data(year)
        return data
    except Exception as e:
        logger.error(f"Error fetching heatmap data for year {year}: {e}")
        return {
            "total": 0,
            "peak": 0,
            "zero_days": 365,
            "data": [],
            "error": str(e)
        }
