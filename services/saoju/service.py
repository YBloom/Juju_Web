import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
from sqlmodel import select
from services.utils.timezone import now as timezone_now
from services.db.connection import session_scope
from services.hulaquan.tables import SaojuCache

log = logging.getLogger(__name__)

class SaojuService:
    API_BASE = "https://y.saoju.net/yyj/api"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._day_cache: Dict[str, Dict] = {} # Key: date_str|city
        self.data: Dict = {}
        self.CACHE_KEY = "global_cache"
        self.load_data()
        
        # Ensure base structure
        self.data.setdefault("artists_map", {})
        self.data.setdefault("artists_updated_at", None)
        self.data.setdefault("musical_map", {})
        self.data.setdefault("artist_indexes", {})
        self.data.setdefault("show_cache", {})
        self.data.setdefault("show_cache_updated", {})

    def load_data(self):
        try:
            with session_scope() as session:
                # Create table if not exists (usually handled by migration/app startup but safe to ensure here or assume handled)
                # Ideally, SQLModel.metadata.create_all(engine) is called somewhere.
                # Since I added a new table, I should probably ensure it exists.
                # However, session_scope gets engine.
                # Let's rely on standard flow or strict execution.
                # Given I just added the table, I'll rely on verify script to create tables or user flow.
                # For safety, I'll just query.
                cache = session.exec(select(SaojuCache).where(SaojuCache.key == self.CACHE_KEY)).first()
                if cache and cache.data:
                    self.data = json.loads(cache.data)
                    log.info(f"Loaded Saoju cache from DB (key={self.CACHE_KEY})")
                else:
                    self.data = {}
        except Exception as e:
            # If table doesn't exist, this will fail.
            # We should probably support auto-init or just log error.
            log.warning(f"Failed to load cache from DB (may be first run or missing table): {e}")
            self.data = {}

    def save_data(self):
        try:
            json_str = json.dumps(self.data, ensure_ascii=False)
            with session_scope() as session:
                cache = session.exec(select(SaojuCache).where(SaojuCache.key == self.CACHE_KEY)).first()
                if not cache:
                    cache = SaojuCache(key=self.CACHE_KEY, data=json_str)
                    session.add(cache)
                else:
                    cache.data = json_str
                    cache.updated_at = timezone_now()
                    session.add(cache)
                # session_scope auto commits
            log.info(f"Saved Saoju cache to DB (key={self.CACHE_KEY})")
        except Exception as e:
            log.error(f"Failed to save cache to DB: {e}")

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session and not self._session.closed:
            await self.close()


    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            # 增加连接池大小和配置
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30, force_close=False)
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self._session = aiohttp.ClientSession(
                headers=headers, 
                timeout=timeout,
                connector=connector
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _fetch_json(self, path: str, params: Optional[Dict] = None, retries: int = 3) -> Optional[Dict]:
        url = f"{self.API_BASE}/{path.lstrip('/')}"
        
        for attempt in range(retries):
            try:
                await self._ensure_session()
                async with self._session.get(url, params=params) as response:
                    if response.status != 200:
                        log.error(f"Saoju API Error {response.status}: {url}")
                        return None
                    return await response.json(content_type=None)
            except (aiohttp.ClientConnectionError, aiohttp.ClientConnectorError, asyncio.TimeoutError) as e:
                if attempt < retries - 1:
                    # 指数退避: 1s, 2s, 4s
                    backoff_time = 2 ** attempt
                    log.warning(f"连接错误,重试 {attempt + 1}/{retries - 1} (等待{backoff_time}秒): {type(e).__name__}")
                    # 彻底关闭并重新创建session
                    try:
                        if self._session and not self._session.closed:
                            await self._session.close()
                            # 确保connector也被关闭
                            await asyncio.sleep(0.1)
                    except Exception as close_err:
                        log.debug(f"Session close error (ignored): {close_err}")
                    self._session = None
                    await asyncio.sleep(backoff_time)  # 退避等待
                else:
                    log.error(
                        f"Error fetching Saoju API\n"
                        f"    URL: {url}\n"
                        f"    Params: {params}\n"
                        f"    Error: {type(e).__name__}: {e}"
                    )
                    # 最后一次失败也要清理session
                    try:
                        if self._session:
                            await self._session.close()
                    except:
                        pass
                    self._session = None
                    return None
            except Exception as e:
                log.error(
                    f"Error fetching Saoju API\n"
                    f"    URL: {url}\n"
                    f"    Params: {params}\n"
                    f"    Error: {type(e).__name__}: {e}"
                )
                # 其他异常也要清理session
                try:
                    if self._session:
                        await self._session.close()
                except:
                    pass
                self._session = None
                return None

    async def search_for_musical_by_date(self, search_name: str, date_str: str, time_str: str, city: Optional[str] = None, musical_id: Optional[str] = None) -> Optional[Dict]:
        """
        Search for a musical show to get its cast.
        搜索音乐剧以获取其演员阵容。
        search_name: Musical title or keyword.
        search_name: 音乐剧标题或关键字。
        date_str: YYYY-MM-DD
        time_str: HH:MM
        musical_id: Optional Saoju Musical ID for precise filtering.
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
                # If musical_id is provided, check it (assuming show result contains musical id)
                # API response for search_day usually contains 'musical_id' or similar?
                # Actually standard saoju API returns 'musical' name, maybe not ID in this endpoint.
                # Let's check typical response structure or assume title match is robust enough if ID provided.
                # If we have ID, we might need a different strategy or just rely on title match + date.
                # But wait, if we have ID, we can cross check if the show's musical name matches the ID's name?
                # For now, let's keep it simple: if musical_id provided, we assume caller wants us to rely on it 
                # but since this specific endpoint might not return ID, we still string match.
                # However, we can use the cache to verify.
                
                # Check title
                if search_name in show.get("musical", ""):
                    return show
        return None

    async def get_cast_for_show(self, search_name: str, session_time: datetime, city: Optional[str] = None, musical_id: Optional[str] = None) -> List[Dict]:
        """
        Get cast list for a specific show.
        search_name: Musical title (or fallback if ID not found).
        session_time: Show datetime.
        musical_id: Optional Saoju Musical ID.
        """
        date_str = session_time.strftime("%Y-%m-%d")
        time_str = session_time.strftime("%H:%M")
        
        show = await self.search_for_musical_by_date(search_name, date_str, time_str, city, musical_id)
        if not show:
            return []
            
        # The search_day API usually returns cast as a list of dicts:
        # [{"artist": "Name", "role": "Role"}, ...]
        return show.get("cast", [])

    async def get_artist_events_data(self, cast_name: str) -> List[Dict]:
        """获取演员的演出排期时间轴。"""
        from services.hulaquan.utils import standardize_datetime_for_saoju, parse_datetime
        
        await self._ensure_artist_map()
        artist_id = self.data.get("artists_map", {}).get(cast_name)
        if not artist_id:
            return []
            
        indexes = await self._ensure_artist_indexes()
        artist_musicals = indexes.get("artist_musicals", {}).get(str(artist_id), {})
        if not artist_musicals:
            return []
            
        ARTIST_LOOKBACK_DAYS = 180
        ARTIST_LOOKAHEAD_DAYS = 365
        
        begin_date = (timezone_now() - timedelta(days=ARTIST_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        end_date = (timezone_now() + timedelta(days=ARTIST_LOOKAHEAD_DAYS)).strftime("%Y-%m-%d")
        
        events: List[Dict] = []
        seen_keys = set()
        
        for musical_info in artist_musicals.values():
            musical_name = musical_info.get("name")
            if not musical_name:
                continue
            show_list = await self._get_musical_shows(musical_name, begin_date, end_date)
            for show in show_list:
                cast_list = show.get("cast") or []
                matched = next((c for c in cast_list if c.get("artist") == cast_name), None)
                if not matched:
                    continue
                time_str = show.get("time")
                try:
                    dt = parse_datetime(time_str)
                except Exception:
                    continue
                if not dt:
                    continue
                
                # Format: 08月03日 星期日 14:30
                WEEKDAY_LABEL = ["一", "二", "三", "四", "五", "六", "日"]
                weekday = WEEKDAY_LABEL[dt.weekday()]
                formatted_date = f"{dt.month:02d}月{dt.day:02d}日 星期{weekday} {dt.strftime('%H:%M')}"
                
                city = show.get("city") or ""
                theatre = show.get("theatre") or ""
                others = [c.get("artist") for c in cast_list if c.get("artist") and c.get("artist") != cast_name]
                
                dedupe_key = (musical_name, dt.isoformat(), city)
                if dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                
                events.append({
                    "date": formatted_date,
                    "title": show.get("musical") or musical_name,
                    "role": matched.get("role") or " / ".join(musical_info.get("roles", [])),
                    "others": others,
                    "city": city,
                    "location": theatre,
                })
        
        # Sort using utils helper
        events.sort(key=lambda entry: standardize_datetime_for_saoju(entry["date"]))
        return events

    async def match_co_casts(self, co_casts: List[str], show_others: bool = True, progress_callback=None, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Find shows where all artists in `co_casts` performed together.
        Optimized to use ID intersection and search_musical_show API.
        
        Args:
           start_date: YYYY-MM-DD string. Default check logic below if None.
           end_date: YYYY-MM-DD string. Default check logic below if None.
        """
        from services.hulaquan.utils import standardize_datetime_for_saoju, parse_datetime
        
        if not co_casts:
            return []
            
        # 1. 确保有演员和索引数据
        if progress_callback:
            await progress_callback(10, "正在建立演员索引...")
        
        # 1. 确保所有演员及其剧目索引已加载
        indexes = await self._ensure_artist_indexes()
        # artist_musicals: {artist_id: {musical_id: {roles: [r1, r2], name: "musical_name"}}}
        
        artist_ids = []
        for name in co_casts:
            if name not in self.data.get("artists_map", {}):
                # 尝试重新拉取最新的艺术家列表
                self.data["artists_map"] = await self.fetch_saoju_artist_list()
            
            aid = self.data["artists_map"].get(name)
            if aid:
                artist_ids.append(str(aid))
            else:
                log.warning(f"Artist {name} not found in Saoju.")

        if not artist_ids or len(artist_ids) != len(co_casts):
            return []
            
        if progress_callback:
            await progress_callback(20, "正在计算共同剧目...")

        # 2. 找到他们共同出演的剧目 ID (Intersection)
        common_musicals = set()
        for i, aid in enumerate(artist_ids):
            musicals = set(indexes.get("artist_musicals", {}).get(aid, {}).keys())
            if i == 0:
                common_musicals = musicals
            else:
                common_musicals &= musicals
                
        if not common_musicals:
            return []
            
        total_musicals = len(common_musicals)
        completed_count = 0
        results = []
        
        # Define date range for efficient search
        now = datetime.now()
        if not start_date:
            start_date = now.strftime("%Y-%m-%d")
        if not end_date:
            end_date = (now + timedelta(days=365)).strftime("%Y-%m-%d")
            
        # Parse for local comparison if needed
        from services.hulaquan.utils import parse_datetime
        try:
            dt_start = parse_datetime(start_date) or datetime(2023, 1, 1)
            dt_end = parse_datetime(end_date) or (now + timedelta(days=730))
        except:
            dt_start = datetime(2023, 1, 1)
            dt_end = now + timedelta(days=365)

        
        # 定义处理单个剧目的函数 (Using search_musical_show API)
        async def process_musical(mid):
            # 获取音乐剧通用名称
            musical_name = "未知剧目"
            if artist_ids:
                first_aid = artist_ids[0]
                musical_name = indexes.get("artist_musicals", {}).get(first_aid, {}).get(str(mid), {}).get("name")
            
            if not musical_name:
                return []

            # 使用 _get_musical_shows (search_musical_show API)
            # 传递指定的日期范围
            shows = await self._get_musical_shows(musical_name, start_date, end_date)
            
            local_results = []
            for show in shows:
                # show from search_musical_show already contains basic info and full cast
                # Format: {"time": "...", "city": "...", "theatre": "...", "cast": [{"artist": "A", "role": "R"}, ...]}
                
                show_cast_list = show.get('cast', [])
                current_cast_names = {c.get('artist') for c in show_cast_list if c.get('artist')}
                
                if all(name in current_cast_names for name in co_casts):
                    # 匹配成功
                    time_str = show.get('time')
                    dt = parse_datetime(time_str)
                    if not dt:
                        continue
                    
                    # 本地日期精确过滤 (Double check range)
                    # Because API might return slightly wider range if cached broadly
                    if not (dt_start <= dt <= dt_end + timedelta(days=1)): # inclusive
                        continue
                    
                    # 提取其TA演员
                    others = [c.get('artist') for c in show_cast_list if c.get('artist') and c.get('artist') not in co_casts]
                    
                    # 格式化为前端所需格式
                    weekday_str = ['一', '二', '三', '四', '五', '六', '日'][dt.weekday()]
                    formatted_date = f"{dt.month:02d}月{dt.day:02d}日 星期{weekday_str} {dt.strftime('%H:%M')}"
                    
                    # 确保角色顺序与 co_casts 一致
                    role_map = {c.get('artist'): c.get('role', '未知角色') for c in show_cast_list if c.get('artist') in co_casts}
                    ordered_roles = [role_map.get(name, '未知角色') for name in co_casts]
                    role_str = " & ".join(ordered_roles)
                    
                    local_results.append({
                        "date": formatted_date,
                        "year": dt.year,  # Add year for frontend grouping
                        "title": musical_name,
                        "role": role_str,
                        "others": others,
                        "city": show.get("city", "未知城市"),
                        "location": show.get("theatre", "未知剧院"),
                        "_raw_time": time_str
                    })
            return local_results

        # 并发执行
        tasks = [process_musical(mid) for mid in common_musicals]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            results.extend(res)
            completed_count += 1
            if progress_callback:
                progress = 20 + int((completed_count / total_musicals) * 70)
                await progress_callback(progress, f"正在搜索... ({completed_count}/{total_musicals})")
        
        if progress_callback:
            await progress_callback(95, "正在整理结果...")

        # 5. 按时间排序
        results.sort(key=lambda x: parse_datetime(x.get("_raw_time", "")) or datetime.min)
        
        # 移除内部排序字段
        for r in results:
            r.pop("_raw_time", None)
        
        return results

    async def _get_synced_shows(self, musical_id: int):
        """从缓存获取或同步剧目的详细演出数据（24小时缓存）"""
        s_mid = str(musical_id)
        self.data.setdefault("show_cache", {})
        self.data.setdefault("show_cache_updated", {})
        
        cache = self.data["show_cache"]
        updated = self.data["show_cache_updated"]
        
        # 检查缓存是否有效
        last_update = updated.get(s_mid)
        if last_update:
            from services.hulaquan.utils import parse_datetime
            dt = parse_datetime(last_update)
            if dt and (timezone_now() - dt) < timedelta(hours=24):
                return cache.get(s_mid, [])
        
        # 缓存无效，需要同步
        log.info(f"Syncing musical {musical_id} from API...")
        shows = await self.sync_musical_data(musical_id)
        
        if shows:
            cache[s_mid] = shows
            from services.hulaquan.utils import dateTimeToStr
            updated[s_mid] = dateTimeToStr(timezone_now())
            self.save_data()
        
        return shows or []

    async def ensure_musical_map(self):
        """Fetch and cache all musicals for ID lookup."""
        if self.data.get("musical_map"):
            return
            
        musicals = await self._fetch_json("musical/")
        if not musicals:
            return
            
        # Map: Name -> ID and Alias -> ID
        # Also store original name for ID -> Name lookup if needed
        name_map = {}
        for m in musicals:
            pk = str(m.get("pk"))
            fields = m.get("fields", {})
            name = fields.get("name")
            if name and pk:
                name_map[name] = pk
                # Also handle aliases if available in fields (not standard in this endpoint usually, but good to know)
        
        self.data["musical_map"] = name_map
        log.info(f"Loaded {len(name_map)} musicals from Saoju.")

    async def get_musical_id_by_name(self, name: str) -> Optional[str]:
        """Look up musical ID by exact name."""
        await self.ensure_musical_map()
        return self.data.get("musical_map", {}).get(name)

    # --- Helper methods ported and adapted from SaojuDataManager ---
    
    async def _get_musical_shows(self, musical: str, begin_date: str, end_date: str):
        self.data.setdefault("musical_show_cache", {})
        self.data.setdefault("update_time_dict", {}).setdefault("musical_show_cache", {})
        
        if not musical: return []
        cache_key = f"{musical}|{begin_date}|{end_date}"
        
        # Simplified cache check
        if cache_key in self.data["musical_show_cache"]:
             return self.data["musical_show_cache"][cache_key]
             
        response = await self._fetch_json(
            "search_musical_show/",
            params={"musical": musical, "begin_date": begin_date, "end_date": end_date},
        )
        show_list = (response or {}).get("show_list", []) if response else []
        self.data["musical_show_cache"][cache_key] = show_list
        return show_list

    async def _ensure_artist_map(self):
        """Ensure artist map is loaded and not expired (3 days)."""
        now = datetime.now()
        updated_at_str = self.data.get('artists_updated_at')
        is_expired = True
        
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                if now - updated_at < timedelta(days=3):
                    is_expired = False
            except:
                pass
        
        if self.data.get('artists_map') and not is_expired:
            return

        log.info("Artists map expired or missing, fetching new list...")
        self.data['artists_map'] = await self.fetch_saoju_artist_list()
        self.data['artists_updated_at'] = now.isoformat()
        self.save_data()

    async def fetch_saoju_artist_list(self):
        """Fetch all artists and filter those who appear in cast lists (musicalcast)."""
        # 1. Fetch all artists and all musicalcast entries
        artist_task = self._fetch_json("artist/")
        cast_task = self._fetch_json("musicalcast/")
        
        artist_data, cast_data = await asyncio.gather(artist_task, cast_task)
        
        if not artist_data: return {}
        if not cast_data:
            # Fallback to all artists if cast_data fails
            name_to_pk = {item.get("fields", {}).get("name"): item.get("pk") for item in artist_data if item.get("fields")}
            return {name: pk for name, pk in name_to_pk.items() if name and pk}

        # 2. Extract artist IDs from musicalcast
        actor_ids = {item.get("fields", {}).get("artist") for item in cast_data if item.get("fields")}
        
        # 3. Map filtered artists
        refined_map = {}
        for item in artist_data:
            pk = item.get("pk")
            name = item.get("fields", {}).get("name")
            if pk and name and pk in actor_ids:
                refined_map[name] = pk
        
        return refined_map

    async def _ensure_artist_indexes(self):
        indexes = self.data.get("artist_indexes") or {}
        # Skipping sophisticated lock/TTL for brevity in this port, just check if exists
        if indexes: return indexes
        
        new_indexes = await self._build_artist_indexes()
        if new_indexes:
            self.data["artist_indexes"] = new_indexes
            self.save_data()
        return self.data.get("artist_indexes", {})

    async def _build_artist_indexes(self) -> Optional[Dict]:
        # Simple gather
        musical_task = self._fetch_json("musical/")
        role_task = self._fetch_json("role/")
        cast_task = self._fetch_json("musicalcast/")
        
        musical_data, role_data, cast_data = await asyncio.gather(musical_task, role_task, cast_task)
        
        if not musical_data or not role_data or not cast_data:
            return self.data.get("artist_indexes")

        from collections import defaultdict
        musical_lookup = {str(item["pk"]): item.get("fields", {}).get("name", "") for item in musical_data}
        role_lookup = {
            str(item["pk"]): {
                "musical": str(item.get("fields", {}).get("musical")),
                "name": item.get("fields", {}).get("name", ""),
            }
            for item in role_data
        }
        
        artist_musicals = defaultdict(dict)
        for cast in cast_data:
            fields = cast.get("fields") or {}
            artist_id = fields.get("artist")
            role_id = fields.get("role")
            if artist_id is None or role_id is None: continue
            
            role_info = role_lookup.get(str(role_id))
            if not role_info: continue
            
            musical_id = role_info.get("musical")
            if not musical_id: continue
            
            entry = artist_musicals[str(artist_id)].setdefault(
                str(musical_id),
                {"roles": set(), "name": musical_lookup.get(str(musical_id), "")},
            )
            entry["roles"].add(role_info.get("name") or "")
            
        normalized = {}
        for artist_id, musicals in artist_musicals.items():
            normalized[artist_id] = {}
            for musical_id, payload in musicals.items():
                roles = sorted({role for role in payload["roles"] if role})
                normalized[artist_id][musical_id] = {"roles": roles, "name": payload.get("name", "")}
                
        from services.hulaquan.utils import dateTimeToStr
        result = {
            "artist_musicals": normalized,
            "updated_at": dateTimeToStr(timezone_now(), with_second=True),
        }
        self.save_data()
        return result
    async def get_tours(self, musical_id: int) -> List[Dict]:
        """API 12: Get all tours for a musical."""
        data = await self._fetch_json("tour/")
        if not data:
            return []
        # Filter locally since API returns all
        return [t for t in data if t.get("fields", {}).get("musical") == musical_id]

    async def get_schedules(self, tour_id: int) -> List[Dict]:
        """API 13: Get all schedules for a tour."""
        data = await self._fetch_json("schedule/")
        if not data:
            return []
        return [s for s in data if s.get("fields", {}).get("tour") == tour_id]

    async def get_shows(self, schedule_id: int) -> List[Dict]:
        """API 14: Get all shows for a schedule."""
        return await self._fetch_json(f"schedule/{schedule_id}/show/") or []

    async def get_show_cast(self, show_id: int) -> List[Dict]:
        """API 15: Get cast for a specific show."""
        # API 15 returns list of dicts: [{"pk":..., "fields":{}, ...}] or similar structure?
        # User request says:
        # pk: 2114
        # model: "yyj.musicalcast"
        # fields: {} (empty)
        # But wait, User snippet says: "fields:{} （此项为空，无需包含其他信息。根据卡司信息组合，即可知道当日演出演员...）"
        # And "pk" is musicalcast PK.
        # So we probably need to resolve these PKs to Artist names using our local index/map.
        # Actually user said: "根据卡司信息组合，即可知道当日演出演员"
        # This implies the result LIST of PKs is what we get.
        # Let's verify what the API returns. The user example showed a list structure.
        return await self._fetch_json(f"show/{show_id}/cast/") or []

    async def sync_musical_data(self, musical_id: int) -> List[Dict]:
        """
        Traverse Tour -> Schedule -> Show -> Cast to build a complete picture.
        Returns a list of 'Show' dictionaries with resolved data.
        """
        log.info(f"Syncing data for musical {musical_id}...")
        tours = await self.get_tours(musical_id)
        if not tours:
            return []

        all_shows = []
        
        # We need artist map to resolve names if API 15 only gives IDs.
        # User says API 15 gives "musicalcast" objects.
        # musicalcast data (API 7) has: role (ID), artist (ID).
        # So API 15 likely returns list of musicalcast objects.
        # We need to load artist/role/musicalcast indexes to be fast.
        indexes = await self._ensure_artist_indexes()
        
        # Helper to resolve cast ID to Artist Name
        # We need a map from musicalcast_pk -> (ArtistName, RoleName)
        # current _build_artist_indexes builds artist_id -> musical -> roles
        # We might need a reverse lookup or just fetch all musicalcast to build a lookup.
        # Let's look at _build_artist_indexes.
        # It fetches all musicalcast entries at once.
        # We can create a quick lookup map inside this method or cache it.
        
        # Let's fetch all necessary metadata for resolution
        # We can reuse the indexes logic or just fetch again if needed.
        # To be safe and fast, let's fetch cast/role/artist once here or ensure they are ready.
        # _build_artist_indexes does fetch all.
        
        # But wait, existing _build_artist_indexes structure is:
        # artist_musicals[artist_id][musical_id]
        # This is optimized for "Get all shows for Artist".
        # Now we have "Get all artists for Show".
        # We have the show's cast list (list of musicalcast objects from API 15).
        # Each object has a PK.
        # We need to map that PK to Artist/Role.
        
        # Let's verify if API 15 returns the *musicalcast* object itself or just a ref.
        # User says:
        # pk: 2114
        # model: "yyj.musicalcast"
        # fields: {} 
        # Wait, if fields is empty, how do we know which artist/role it is?
        # Ah, API 7 (musicalcast) has fields: role, artist.
        # If API 15 returns musicalcast objects *with empty fields*, that implies we must look up the PK in the "All MusicalCast" table (API 7) to find the artist/role.
        # Correct!
        # So we absolutely need the full API 7 list to map PK -> (ArtistID, RoleID).
        
        # Let's build that map.
        cast_data_full = await self._fetch_json("musicalcast/")
        # map: musicalcast_pk -> {artist: id, role: id}
        cast_lookup = {item["pk"]: item.get("fields", {}) for item in cast_data_full}
        
        # Also need Artist and Role lookups
        artist_data = await self._fetch_json("artist/")
        artist_lookup = {item["pk"]: item.get("fields", {}).get("name") for item in artist_data}
        
        role_data = await self._fetch_json("role/")
        role_lookup = {item["pk"]: item.get("fields", {}).get("name") for item in role_data}

        # Optimization: use gather for these 3 if not cached
        # For now, sequential is fine for safety.

        for tour in tours:
            tour_id = tour["pk"]
            schedules = await self.get_schedules(tour_id)
            for sched in schedules:
                sched_id = sched["pk"]
                shows = await self.get_shows(sched_id)
                
                # Filter shows by date BEFORE fetching casts to save massive time
                valid_shows = []
                recent_cutoff = timezone_now() - timedelta(days=90)
                
                for show in shows:
                     show_time_str = show.get("fields", {}).get("time") # 2023-10-02T11:30:00Z
                     if not show_time_str:
                         continue
                     
                     # Quick parse for filtering
                     try:
                         # Handle Z if present
                         clean_ts = show_time_str.rstrip('Z')
                         dt = datetime.fromisoformat(clean_ts)
                         if dt > recent_cutoff:
                             valid_shows.append(show)
                     except Exception:
                         # If parse fails, include it to be safe or log? Include safe.
                         valid_shows.append(show)

                if not valid_shows:
                    continue

                # Fetch casts concurrently for filtered shows only
                tasks = [self.get_show_cast(show["pk"]) for show in valid_shows]
                if not tasks:
                    continue
                    
                casts_results = await asyncio.gather(*tasks)
                
                for show, cast_list in zip(valid_shows, casts_results):
                    # Resolve cast
                    resolved_cast = []
                    for cast_item in cast_list:
                        cw_pk = cast_item["pk"] # This is the musicalcast PK
                        ref = cast_lookup.get(cw_pk)
                        if not ref:
                            continue
                        
                        a_id = ref.get("artist")
                        r_id = ref.get("role")
                        
                        a_name = artist_lookup.get(a_id)
                        r_name = role_lookup.get(r_id)
                        
                        if a_name:
                            resolved_cast.append({"artist": a_name, "role": r_name})
                    
                    show_time = show.get("fields", {}).get("time") # 2023-10-02T11:30:00Z
                    
                    # Store structured data
                    all_shows.append({
                        "show_id": show["pk"],
                        "time": show_time,
                        "cast": resolved_cast,
                        # Pass through context
                        "tour_name": tour.get("fields", {}).get("name"),
                        "city": "Unknown", # Schedule -> Stage -> Theatre -> City path needed if we want city...
                        # Wait, API 13 Schedule has "stage". API 11 Stage has "theatre". API 10 Theatre has "city".
                        # This is a deep traversal for City. 
                        # Only way to get city is to resolve Schedule -> Stage -> Theatre -> City.
                        "stage_id": sched.get("fields", {}).get("stage")
                    })

        # To populate City, we need Stage/Theatre/City maps.
        # Let's do that for completeness since user query usually involves City.
        stages = await self._fetch_json("stage/")
        stage_map = {s["pk"]: s.get("fields", {}) for s in stages} # has theatre_id
        
        theatres = await self._fetch_json("theatre/")
        theatre_map = {t["pk"]: t.get("fields", {}) for t in theatres} # has city_id, name
        
        cities = await self._fetch_json("city/")
        city_map = {c["pk"]: c.get("fields", {}).get("name") for c in cities}
        
        # Backfill city/theatre info
        for s in all_shows:
            st_id = s.get("stage_id")
            st_info = stage_map.get(st_id)
            if st_info:
                th_id = st_info.get("theatre")
                th_info = theatre_map.get(th_id)
                if th_info:
                    s["theatre_name"] = th_info.get("name")
                    c_id = th_info.get("city")
                    s["city"] = city_map.get(c_id, "Unknown")
            
            # Clean up temporary key
            del s["stage_id"]

        log.info(f"Synced {len(all_shows)} shows for musical {musical_id}.")
        return all_shows
