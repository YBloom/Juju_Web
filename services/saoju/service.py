import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

log = logging.getLogger(__name__)

class SaojuService:
    API_BASE = "https://y.saoju.net/yyj/api"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._day_cache: Dict[str, Dict] = {} # Key: date_str|city
        # 键: date_str|city

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _fetch_json(self, path: str, params: Optional[Dict] = None) -> Optional[Dict]:
        await self._ensure_session()
        url = f"{self.API_BASE}/{path.lstrip('/')}"
        try:
            async with self._session.get(url, params=params) as response:
                if response.status != 200:
                    log.error(f"Saoju API Error {response.status}: {url}")
                    return None
                return await response.json()
        except Exception as e:
            log.error(f"Error fetching Saoju {url}: {e}")
            return None

    async def search_for_musical_by_date(self, search_name: str, date_str: str, time_str: str, city: Optional[str] = None) -> Optional[Dict]:
        """
        Search for a musical show to get its cast.
        搜索音乐剧以获取其演员阵容。
        search_name: Musical title or keyword.
        search_name: 音乐剧标题或关键字。
        date_str: YYYY-MM-DD
        time_str: HH:MM
        """
        # Follow legacy logic: first search by date, then filter
        # 遵循旧有逻辑：先按日期搜索，然后过滤
        cache_key = f"{date_str}|{city or ''}"
        if cache_key in self._day_cache:
            data = self._day_cache[cache_key]
        else:
            params = {"date": date_str}
            if city:
                params["city"] = city
            
            data = await self._fetch_json("search_day/", params=params)
            if data:
                self._day_cache[cache_key] = data

        if not data or "show_list" not in data:
            return None
        
        # Match by name and time
        # 按名称和时间匹配
        for show in data["show_list"]:
            if time_str == show.get("time"):
                if search_name in show.get("musical", ""):
                    return show
        return None

    async def get_cast_for_show(self, search_name: str, show_time: datetime, city: Optional[str] = None) -> List[Dict]:
        """
        High-level helper to get cast list.
        获取演员列表的高级帮助程序。
        Returns [{'artist': '...', 'role': '...'}]
        返回 [{'artist': '...', 'role': '...'}]
        """
        date_str = show_time.strftime("%Y-%m-%d")
        time_str = show_time.strftime("%H:%M")
        show = await self.search_for_musical_by_date(search_name, date_str, time_str, city)
        if show:
            return show.get("cast", [])
        return []
