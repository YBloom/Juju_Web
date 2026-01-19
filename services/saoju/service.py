import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import aiohttp
from sqlmodel import select
from services.utils.timezone import now as timezone_now
from services.db.connection import session_scope
from services.hulaquan.tables import SaojuCache, SaojuShow, SaojuChangeLog

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
        
        # NOTE: Always ensure indexes are loaded for sorting features
        # We can't await in __init__, so we rely on explicit calls or lazy loading.
        # But HulaquanService needs it.
        # Done: We will ensure `HulaquanService.sync_all_data` calls `saoju.ensure_artist_indexes()`


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
                    # DO NOT close session here as it kills concurrent requests
                    await asyncio.sleep(backoff_time)  # 退避等待
                else:
                    log.error(
                        f"Error fetching Saoju API\n"
                        f"    URL: {url}\n"
                        f"    Params: {params}\n"
                        f"    Error: {type(e).__name__}: {e}"
                    )
                    # Do not close session on error, let it persist or be closed by lifespan
                    return None
            except Exception as e:
                log.error(
                    f"Error fetching Saoju API\n"
                    f"    URL: {url}\n"
                    f"    Params: {params}\n"
                    f"    Error: {type(e).__name__}: {e}"
                )
                return None

    async def search_for_musical_by_date(self, search_name: str, date_str: str, time_str: str, city: Optional[str] = None, musical_id: Optional[str] = None) -> Optional[Dict]:
        """
        Search for a musical show in LOCAL DB ONLY (SaojuShow).
        Replaces the old network-dependent logic to prevent N+1 request issues.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_show_db_sync, search_name, date_str, time_str, city)

    def _search_show_db_sync(self, search_name: str, date_str: str, time_str: str, city: Optional[str] = None) -> Optional[Dict]:
        try:
            target_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None

        with session_scope() as session:
            # Index scan on date
            stmt = select(SaojuShow).where(SaojuShow.date == target_dt)
            if city:
                stmt = stmt.where(SaojuShow.city == city)
            
            candidates = session.exec(stmt).all()
            
            # Memory filter for title fuzzy match
            for show in candidates:
                if not search_name:
                    # Defensive: if no search name, return first match or None? 
                    # Logic implies we are looking for specific show info.
                    continue
                
                # Check title overlap (e.g. "时光" in "时光代理人")
                if search_name in show.musical_name or show.musical_name in search_name:
                    return {
                        "musical": show.musical_name,
                        "city": show.city,
                        "theatre": show.theatre,
                        "time": show.date.strftime("%H:%M")
                    }
            
            return None

    async def get_cast_for_hulaquan_session(self, search_name: str, session_time: datetime, city: Optional[str] = None) -> List[Dict]:
        """
        Dedicated method for Hulaquan Service to populate cast info from LOCAL DB ONLY.
        Strictly NO network I/O.
        从本地数据库获取卡司信息，无网络 I/O。
        """
        if not search_name or not session_time:
            return []
            
        with session_scope() as session:
            # 使用时间窗口匹配 (±1秒)，以容忍微秒精度差异
            # Use time window matching (±1 second) to tolerate microsecond precision differences
            time_start = session_time.replace(microsecond=0) - timedelta(seconds=1)
            time_end = session_time.replace(microsecond=0) + timedelta(seconds=2)  # +2秒包含完整的下一秒
            stmt = select(SaojuShow).where(SaojuShow.date >= time_start, SaojuShow.date < time_end)
            if city:
                stmt = stmt.where(SaojuShow.city == city)
                
            candidates = session.exec(stmt).all()
            
            # Fuzzy Title Match in Memory
            matched_show = None
            for show in candidates:
                # Check if titles overlap
                if search_name in show.musical_name or show.musical_name in search_name:
                    matched_show = show
                    break
            
            if not matched_show or not matched_show.cast_str:
                return []
                
            # Parse cast_str back to list of dicts
            # Format: "Role:Actor / Role:Actor" or "Actor / Actor"
            result = []
            
            # Robust split using regex to avoid splitting "Role/Name:Actor" inside the role
            # We assume dividers are " / " (slash with spaces) or just spaces if no slash is used as divider
            import re
            if ' / ' in matched_show.cast_str:
                segments = [s.strip() for s in matched_show.cast_str.split(' / ')]
            elif '/' in matched_show.cast_str:
                # If has '/' but no ' / ', this is likely space-separated format with role names containing slashes
                # e.g. "程小时:舒荣波 陆光:杨浩然 林贞/陈潇妈:沈恬"
                # Split by whitespace to preserve the slash in role names
                segments = matched_show.cast_str.split()
            else:
                segments = matched_show.cast_str.split()
                
            for seg in segments:
                if not seg: continue
                item = {}
                if ':' in seg:
                    # Role:Name
                    try:
                        r_part, a_part = seg.split(':', 1)
                        item['role'] = r_part.strip()
                        item['artist'] = a_part.strip()
                    except:
                        item['artist'] = seg
                else:
                    item['artist'] = seg
                
                if item.get('artist'):
                    result.append(item)
                    
            return result

    async def match_co_casts(self, co_casts: List[str], show_others: bool = True, progress_callback=None, start_date: str = None, end_date: str = None) -> List[Dict]:
        """
        Find shows where all artists in `co_casts` performed together.
        Optimized to use SaojuShow table.
        """
        if not co_casts:
            return []
            
        with session_scope() as session:
            # Construct query
            # We need shows where cast_str contains ALL names
            # SQLite 'LIKE' is case insensitive usually, but names are standard
            # We will filter in python to be safe if names are substrings of others (e.g. '张伟' vs '张伟大')
            # But usually full name match is required.
            
            # Since SQLModel/SQLAlchemy query construction for multiple LIKEs:
            query = select(SaojuShow)
            
            # Date filtering
            if start_date:
                try:
                    dt_start = datetime.strptime(start_date, "%Y-%m-%d")
                    query = query.where(SaojuShow.date >= dt_start)
                except: pass
            
            if end_date:
                try:
                    dt_end = datetime.strptime(end_date, "%Y-%m-%d")
                    # Inclusive end date -> +1 day 00:00
                    query = query.where(SaojuShow.date < dt_end + timedelta(days=1))
                except: pass
                
            entries = session.exec(query).all()
            
            results = []
            import re
            
            for show in entries:
                # Python-side verification for exact/safe matching
                if not show.cast_str:
                    continue
                
                # cast_str format: "Role:Name / Role:Name" or legacy "Name / Name"
                # We need to extract actor names for matching and roles for display
                
                current_cast = set()
                role_map = {}  # actor -> role for later use
                
                # Split logic: prioritize " / " to protect slashes in roles (e.g. "Role/SubRole:Actor")
                if ' / ' in show.cast_str:
                    segments = [s.strip() for s in show.cast_str.split(' / ')]
                elif '/' in show.cast_str and not ':' in show.cast_str:
                     # Legacy "A/B/C" without colons? Split by /
                     segments = [s.strip() for s in show.cast_str.split('/')]
                elif '/' in show.cast_str:
                     # Has slash and has colons, but no " / ". This is ambiguous "Role:A/Role:B" vs "Role/Name:A".
                     # Assuming "Role:A/Role:B" is rare without spaces?
                     # Let's try splitting by regex `\s*/\s*` if it's not "Role/Name".
                     # Actually, safe fallback is to treat as one block if we can't be sure, 
                     # BUT likely we need to split.
                     # Given the bug report, let's assume standard format is " / " for separation.
                     # If only tight slashes, we might just split by space?
                     segments = show.cast_str.split()
                else:
                    segments = show.cast_str.split()
                
                for seg in segments:
                    if not seg: continue
                    if ':' in seg:
                        # Format: role:actor
                        try:
                            # Split by first colon only
                            r_part, a_part = seg.split(':', 1)
                            role_name = r_part.strip()
                            actor_name = a_part.strip()
                            current_cast.add(actor_name)
                            role_map[actor_name] = role_name
                        except:
                            current_cast.add(seg)
                    else:
                        current_cast.add(seg.strip())
                
                if all(name in current_cast for name in co_casts):
                    # Found match
                    others = []
                    for x in current_cast:
                        if x in co_casts: continue
                        role = role_map.get(x)
                        if role:
                            others.append(f"{role}:{x}")
                        else:
                            others.append(x)
                    
                    # Format date: 08月03日 星期日 14:30
                    dt = show.date
                    weekday_str = ['一', '二', '三', '四', '五', '六', '日'][dt.weekday()]
                    formatted_date = f"{dt.month:02d}月{dt.day:02d}日 星期{weekday_str} {dt.strftime('%H:%M')}"

                    # Attempt to resolve roles
                    role_str = "见详情"
                    try:
                        resolved_roles = []
                        # Ensure we have maps
                        if not self.data.get("artists_map"):
                             # This might be blocking if not loaded, but ensure_artist_map called?
                             # Let's rely on cached data if available or just skip if empty to avoid big delays
                             pass
                        
                        artist_map = self.data.get("artists_map", {})
                        indexes = self.data.get("artist_indexes", {})
                        artist_musicals = indexes.get("artist_musicals", {})

                        for cast_name in co_casts:
                             # 1. Try to get specific role from this show's record
                             specific_role = role_map.get(cast_name)
                             if specific_role:
                                 if len(co_casts) == 1:
                                     resolved_roles.append(specific_role)
                                 else:
                                     resolved_roles.append(f"{cast_name}: {specific_role}")
                                 continue
                                 
                             # 2. Fallback to aggregate data
                             artist_id = artist_map.get(cast_name)
                             if not artist_id: continue
                             
                             # Find musical entry for this artist
                             # We have show.musical_name. We need to find which mid matches this name in artist's record
                             my_musicals = artist_musicals.get(str(artist_id), {})
                             
                             # Search by name match (O(N) but N is small)
                             found_roles = []
                             for mid, payload in my_musicals.items():
                                 if payload.get("name") == show.musical_name:
                                     # Found it
                                     rs = payload.get("roles", [])
                                     if rs: found_roles.extend(rs)
                                     break
                             
                             if found_roles:
                                 r_list = sorted(list(set(found_roles)))
                                 r_txt = "/".join(r_list)
                                 # For one artist, just "Role". For multiple, "Name: Role"
                                 if len(co_casts) == 1:
                                     resolved_roles.append(r_txt)
                                 else:
                                     resolved_roles.append(f"{cast_name}: {r_txt}")
                        
                        if resolved_roles:
                            role_str = " & ".join(resolved_roles)
                        else:
                            # Fallback: if we have NO role info, maybe empty string is better than "见详情"?
                            # User said "变成了见详情", implying they want the old behavior or real data.
                            # Changing to empty string might be cleaner if unknown.
                            # But let's stick to simple " " if not found to avoid visual clutter
                            role_str = "" 

                    except Exception as e:
                        # Log debug if needed, but don't crash
                        pass
                    
                    results.append({
                        "date": formatted_date,
                        "year": dt.year,
                        "title": show.musical_name,
                        "role": role_str or " ", # Use space to keep layout if needed, or empty
                        "others": others,
                        "city": show.city,
                        "location": show.theatre,
                        "_raw_time": dt.isoformat() # Added for frontend sorting
                    })
            
            # Sort
            results.sort(key=lambda x: (x["year"], x["date"]))
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

    async def resolve_musical_id_by_name(self, name: str) -> Optional[str]:
        """Look up musical ID by exact name (Resolves via network if needed)."""
        await self.ensure_musical_map()
        return self.data.get("musical_map", {}).get(name)

    async def get_tours(self, musical_id: int) -> List[Dict]:
        """Fetch tours for a specific musical."""
        return await self._fetch_json("tour/", params={"musical": musical_id}) or []

    async def get_schedules(self, tour_id: int) -> List[Dict]:
        """Fetch schedules for a specific tour."""
        return await self._fetch_json("schedule/", params={"tour": tour_id}) or []

    async def get_shows(self, schedule_id: int) -> List[Dict]:
        """Fetch shows for a specific schedule."""
        return await self._fetch_json("show/", params={"schedule": schedule_id}) or []

    async def get_show_cast(self, show_id: int) -> List[Dict]:
        """Fetch cast entries for a specific show."""
        return await self._fetch_json("musicalcast/", params={"show": show_id}) or []

    # --- Helper methods ported and adapted from SaojuDataManager ---
    
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
        # Check if role_orders exists (migration)
        if indexes and "role_orders" not in indexes:
             indexes = None # Force rebuild
             
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
                
        # Build Role Orders
        # Map: musical_id -> {role_name: seq}
        role_orders = defaultdict(dict)
        for item in role_data:
            fields = item.get("fields", {})
            mid = fields.get("musical")
            name = fields.get("name")
            seq = fields.get("seq", 999) # Default high number if missing
            if mid and name:
                role_orders[str(mid)][name] = seq

        from services.hulaquan.utils import dateTimeToStr
        result = {
            "artist_musicals": normalized,
            "role_orders": role_orders,
            "updated_at": dateTimeToStr(timezone_now(), with_second=True),
        }
        self.save_data()
        return result
    async def get_role_seq(self, musical_id: str, role_name: str) -> int:
        """Get official loop sequence number for a role in a musical. Default 999."""
        if not musical_id or not role_name:
            return 999
            
        indexes = await self._ensure_artist_indexes()
        role_orders = indexes.get("role_orders", {})
        
        musical_roles = role_orders.get(str(musical_id), {})
        return musical_roles.get(role_name, 999)

    async def sync_future_days(self, start_days: int = 0, end_days: int = 120):
        """
        Sync future days using search_day API with Change Data Capture (CDC).
        Range: [today + start_days, today + end_days]
        """
        today = datetime.now()
        
        target_dates = []
        for i in range(start_days, end_days + 1):
            date_val = today + timedelta(days=i)
            target_dates.append(date_val)
            
        log.info(f"Syncing future days {start_days}-{end_days} (Total {len(target_dates)} days)...")
        
        # Concurrency limit
        sem = asyncio.Semaphore(10)
        
        async def fetch_and_save(date_val):
            async with sem:
                date_str = date_val.strftime("%Y-%m-%d")
                try:
                    data = await self._fetch_json("search_day/", params={"date": date_str})
                    if not data or "show_list" not in data:
                        return
                    
                    shows = data["show_list"]
                    with session_scope() as session:
                        for item in shows:
                            musical_name = item.get("musical")
                            time_part = item.get("time") # HH:MM usually in search_day context
                            
                            if not musical_name or not time_part:
                                continue
                                
                            try:
                                full_dt = datetime.strptime(f"{date_str} {time_part}", "%Y-%m-%d %H:%M")
                            except:
                                continue

                            cast_list = item.get("cast", [])
                            parts = []
                            for c in cast_list:
                                artist = c.get("artist")
                                if not artist: continue
                                role = c.get("role")
                                if role:
                                    parts.append(f"{role}:{artist}")
                                else:
                                    parts.append(artist)
                            cast_str = " / ".join(parts)
                            city = item.get("city", "")
                            theatre = item.get("theatre", "")
                            
                            # CDC Check
                            existing = session.get(SaojuShow, (full_dt, musical_name))
                            
                            if not existing:
                                # New Record
                                show_db = SaojuShow(
                                    date=full_dt,
                                    city=city,
                                    musical_name=musical_name,
                                    cast_str=cast_str,
                                    theatre=theatre,
                                    source="api_daily",
                                    updated_at=timezone_now()
                                )
                                session.add(show_db)
                                
                                # Log Change
                                change = SaojuChangeLog(
                                    show_date=full_dt,
                                    musical_name=musical_name,
                                    change_type="NEW",
                                    details=f"新增排期: {city} {theatre}"
                                )
                                session.add(change)
                                
                            else:
                                # Update Check
                                changes = []
                                if existing.cast_str != cast_str:
                                    changes.append(f"卡司变更: {existing.cast_str} -> {cast_str}")
                                if existing.theatre != theatre and theatre:
                                    changes.append(f"剧院变更: {existing.theatre} -> {theatre}")
                                    
                                if changes:
                                    existing.cast_str = cast_str
                                    existing.theatre = theatre
                                    existing.city = city # Update city too just in case
                                    existing.source = "api_daily"
                                    existing.updated_at = timezone_now()
                                    session.add(existing)
                                    
                                    change = SaojuChangeLog(
                                        show_date=full_dt,
                                        musical_name=musical_name,
                                        change_type="UPDATE",
                                        details="; ".join(changes)
                                    )
                                    session.add(change)
                except Exception as e:
                    log.error(f"Error syncing date {date_str}: {e}")

        tasks = [fetch_and_save(d) for d in target_dates]
        await asyncio.gather(*tasks)
        log.info(f"Finished syncing {len(target_dates)} days.")


    async def sync_distant_tours(self, start_buffer_days: int = 120):
        """
        Metedata-Driven Discovery for Distant Future (> start_buffer_days).
        1. Fetch Tours -> Active in distant future.
        2. Fetch Schedules.
        3. Crawl specific dates.
        """
        log.info(f"Starting Distant Tour Discovery (>{start_buffer_days} days)...")
        tours = await self._fetch_json("tour/")
        if not tours:
            return

        cutoff_date = datetime.now() + timedelta(days=start_buffer_days)
        active_tours = []
        
        # Filter active tours in distant future
        for tour in tours:
            fields = tour.get("fields", {})
            end_date_str = fields.get("end_date")
            is_long_term = fields.get("is_long_term", False)
            
            if is_long_term:
                active_tours.append(tour)
                continue
                
            if end_date_str:
                try:
                    ed = datetime.strptime(end_date_str, "%Y-%m-%d")
                    if ed > cutoff_date:
                        active_tours.append(tour)
                except:
                    pass
        
        log.info(f"Found {len(active_tours)} active distant tours.")
        
        # Fetch schedules for these tours
        target_dates = set()
        
        for tour in active_tours:
            schedules = await self.get_schedules(tour["pk"])
            for sched in schedules:
                try:
                    fields = sched.get("fields", {})
                    begin = fields.get("begin_date")
                    end = fields.get("end_date")
                    
                    if not begin or not end:
                         continue
                         
                    bd = datetime.strptime(begin, "%Y-%m-%d")
                    ed = datetime.strptime(end, "%Y-%m-%d")
                    
                    # Intersect [begin, end] with [cutoff, +1 year]
                    # We only care about dates > cutoff
                    
                    scan_start = max(bd, cutoff_date)
                    scan_end = min(ed, datetime.now() + timedelta(days=365)) # Cap at 1 year
                    
                    if scan_start <= scan_end:
                        curr = scan_start
                        while curr <= scan_end:
                            target_dates.add(curr.strftime("%Y-%m-%d"))
                            curr += timedelta(days=1)
                except Exception as e:
                    log.error(f"Error processing schedule {sched}: {e}")

        log.info(f"Identified {len(target_dates)} distant dates to crawl.")
        
        # Crawl identified dates
        # Reuse logic from sync_future_days but just pass specific dates if I refactor
        # Or just copy paste core logic for now to avoid dependency
        
        sem = asyncio.Semaphore(5)
        
        async def fetch_and_save_distant(date_str):
            async with sem:
                try:
                    data = await self._fetch_json("search_day/", params={"date": date_str})
                    if not data or "show_list" not in data:
                        return
                    
                    shows = data["show_list"]
                    with session_scope() as session:
                        for item in shows:
                            musical_name = item.get("musical")
                            time_part = item.get("time")
                            if not musical_name or not time_part:
                                continue
                            
                            try:
                                full_dt = datetime.strptime(f"{date_str} {time_part}", "%Y-%m-%d %H:%M")
                            except:
                                continue

                            cast_list = item.get("cast", [])
                            cast_str = " / ".join([c.get("artist") for c in cast_list if c.get("artist")])
                            city = item.get("city", "")
                            theatre = item.get("theatre", "")
                            
                            # CDC Logic (duplicated for now given constraints)
                            existing = session.get(SaojuShow, (full_dt, musical_name))
                            
                            if not existing:
                                show_db = SaojuShow(
                                    date=full_dt,
                                    city=city,
                                    musical_name=musical_name,
                                    cast_str=cast_str,
                                    theatre=theatre,
                                    source="api_tour",
                                    updated_at=timezone_now()
                                )
                                session.add(show_db)
                                
                                change = SaojuChangeLog(
                                    show_date=full_dt,
                                    musical_name=musical_name,
                                    change_type="NEW",
                                    details=f"远期新增: {city} {theatre}"
                                )
                                session.add(change)
                            else:
                                changes = []
                                if existing.cast_str != cast_str:
                                    changes.append(f"卡司变更: {existing.cast_str} -> {cast_str}")
                                if existing.theatre != theatre and theatre:
                                    changes.append(f"剧院变更: {existing.theatre} -> {theatre}")
                                    
                                if changes:
                                    existing.cast_str = cast_str
                                    existing.theatre = theatre
                                    existing.city = city
                                    existing.source = "api_tour"
                                    existing.updated_at = timezone_now()
                                    session.add(existing)
                                    
                                    change = SaojuChangeLog(
                                        show_date=full_dt,
                                        musical_name=musical_name,
                                        change_type="UPDATE",
                                        details="; ".join(changes)
                                    )
                                    session.add(change)

                except Exception as e:
                    log.error(f"Error syncing distant date {date_str}: {e}")

        # Execute
        tasks = [fetch_and_save_distant(d) for d in target_dates]
        if tasks:
            await asyncio.gather(*tasks)
        log.info("Distant Tour Discovery Complete.")

    async def sync_musical_data(self, musical_id: int):
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

    async def get_total_shows_count(self) -> int:
        """获取收录的演出总数。"""
        from sqlmodel import func
        with session_scope() as session:
            count = session.exec(select(func.count()).select_from(SaojuShow)).one()
            return count

    async def get_heatmap_data(self, year: int) -> Dict[str, Any]:
        """获取指定年份的演出热力图数据。"""
        import calendar
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        with session_scope() as session:
            stmt = select(SaojuShow.date).where(SaojuShow.date >= start_date, SaojuShow.date <= end_date)
            # 仅在 Python 侧进行简单计数，避免复杂的 SQL 分组操作（考虑到 SQLite 的局限性）
            all_dates = session.exec(stmt).all()
            
            counts = {}
            for dt in all_dates:
                d_str = dt.strftime("%Y-%m-%d")
                counts[d_str] = counts.get(d_str, 0) + 1
            
            data = [[d, c] for d, c in counts.items()]
            total = sum(counts.values())
            peak = max(counts.values()) if counts else 0
            
            days_in_year = 366 if calendar.isleap(year) else 365
            zero_days = days_in_year - len(counts)
            
            return {
                "total": total,
                "peak": peak,
                "zero_days": zero_days,
                "data": data
            }
