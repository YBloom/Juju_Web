import asyncio
import json
import logging
import traceback
import ssl
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set

import aiohttp
from sqlmodel import Session, select, or_, and_, col
from sqlalchemy.orm import joinedload

from services.db.connection import session_scope
from services.hulaquan.tables import (
    HulaquanEvent, 
    HulaquanTicket, 
    HulaquanCast, 
    TicketCastAssociation,
    HulaquanAlias,
    TicketUpdateLog,
    TicketStatus
)
from services.hulaquan.models import (
    EventInfo, 
    TicketInfo, 
    CastInfo, 
    TicketUpdate,
    SearchResult
)
from services.hulaquan.utils import standardize_datetime, extract_title_info, extract_text_in_brackets, detect_city_in_text
from services.saoju.service import SaojuService
from services.hulaquan.city_resolver import CityResolver
from services.utils.timezone import now as timezone_now

log = logging.getLogger(__name__)

class HulaquanService:
    BASE_URL = "https://clubz.cloudsation.com"
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    
    def __init__(self):
        self._db_write_lock = asyncio.Lock()  # Lock for SQLite writes
        self._fetch_semaphore = asyncio.Semaphore(5)  # Concurrency limit for Hulaquan API
        self._session: Optional[aiohttp.ClientSession] = None
        self._saoju = SaojuService()
        self._city_resolver = CityResolver()
        
    @property
    def saoju(self) -> SaojuService:
        return self._saoju
        
        # Load venue rules
        self.venue_rules = {}
        try:
            import json
            from pathlib import Path
            rule_path = Path(__file__).parent / "venue_rules.json"
            if rule_path.exists():
                with open(rule_path, 'r', encoding='utf-8') as f:
                    self.venue_rules = json.load(f).get("rules", {})
        except Exception as e:
            log.error(f"Failed to load venue rules: {e}")

    def _apply_city_rules(self, city: Optional[str], venue: Optional[str]) -> Optional[str]:
        if city:
            return city
        if not venue:
            return None
        
        for key, val in self.venue_rules.items():
            if key in venue:
                return val
        return None

    async def __aenter__(self):
        await self._ensure_session()
        await self._saoju._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        await self._saoju.close()

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            timeout = aiohttp.ClientTimeout(total=90, connect=20)
            self._session = aiohttp.ClientSession(
                headers=self.DEFAULT_HEADERS,
                connector=connector,
                timeout=timeout
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _fetch_json(self, url: str) -> Optional[Dict]:
        """Helper to fetch and parse JSON from API (handles BOM).
        从 API 获取和解析 JSON 的帮助程序（处理 BOM）。
        """
        await self._ensure_session()
        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    log.error(f"API Error {response.status}: {url}")
                    return None
                
                # Read as bytes first to handle BOM properly via utf-8-sig
                # 首先读取为字节，以便通过 utf-8-sig 正确处理 BOM
                content = await response.read()
                try:
                    text = content.decode('utf-8-sig')
                    return json.loads(text)
                except Exception as e:
                    log.error(f"JSON decode error for {url}: {e}")
                    # Fallback
                    # 回退
                    text = content.decode('utf-8', errors='ignore')
                    return json.loads(text)
        except (aiohttp.ClientConnectorError, ConnectionResetError, ssl.SSLError, asyncio.TimeoutError, TimeoutError) as e:
            # Fail Fast: Close session and re-raise to abort retry loops
            # 快速失败：关闭会话并重新引发以中止重试循环
            log.warning(f"Connection failed for {url}: {type(e).__name__}: {e} - Closing session.")
            await self.close()
            raise e
        except Exception as e:
            log.error(f"Error fetching {url}: {e}")
            log.error(traceback.format_exc())
            return None

    async def sync_all_data(self) -> List[TicketUpdate]:
        """
        Synchronize local database with remote API.
        将本地数据库与远程 API 同步。
        Returns a list of detected updates (new tickets, restocks, etc.)
        返回检测到的更新列表（新票、补货等）
        """
        log.info("Starting full Hulaquan data synchronization...")
        
        # 0. Ensure Saoju Indexes (Async Prefetch)
        try:
            await self._saoju._ensure_artist_indexes()
        except Exception as e:
            log.warning(f"Failed to prefetch Saoju artist indexes: {e}")

        # 1. Fetch recommended events with retry logic (legacy behavior)
        # 1. 使用重试逻辑获取推荐事件（旧有行为）
        limit = 95
        data = None
        while limit >= 10:
            url = f"{self.BASE_URL}/site/getevent.html?filter=recommendation&access_token=&limit={limit}&page=0"
            try:
                data = await self._fetch_json(url)
            except (aiohttp.ClientConnectorError, ConnectionResetError, ssl.SSLError, asyncio.TimeoutError, TimeoutError):
                log.warning("Hulaquan unreachable (connection/timeout issue), aborting sync.")
                data = None
                break
            
            if data is False or data is None:
                log.warning(f"API returned {data} for limit {limit}, retrying with smaller limit...")
                limit -= 5
                continue
            break
        
        if not data or "events" not in data:
            log.error(f"Failed to fetch event recommendations after retries. Last limit: {limit}")
            return []

        # Filter events by timeMark (following legacy logic)
        # 通过 timeMark 过滤事件（沿用旧有逻辑）
        basic_infos = [e["basic_info"] for e in data["events"] if e.get("timeMark", 0) > 0]
        event_ids = [str(e["id"]) for e in basic_infos]
        
        updates = []
        
        # 2. Concurrently fetch details (Semaphore limited)
        # 2. 并发获取详情（受信号量限制）
        tasks = [self._sync_event_wrapper(eid) for eid in event_ids]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in raw_results:
            if isinstance(res, list):
                updates.extend(res)
            elif isinstance(res, Exception):
                # Logged in wrapper, but just in case
                pass
        
        # [Bot Fix] Add detailed logging for updates
        for u in updates:
            log.info(f"📣 [更新] 类型: {u.change_type} | 标题: {u.event_title} | 消息: {u.message}")

        log.info(f"Synchronization complete. Detected {len(updates)} updates.")
        return updates

    async def _sync_event_wrapper(self, event_id: str) -> List[TicketUpdate]:
        """Exception-safe wrapper for gather."""
        try:
            return await self._sync_event_details(event_id)
        except Exception as e:
            log.error(f"Error syncing event {event_id}: {e}")
            log.error(traceback.format_exc())
            return []

    async def _sync_event_details(self, event_id: str) -> List[TicketUpdate]:
        """Fetch and sync a single event's details and tickets."""
        async with self._fetch_semaphore:
            detail_url = f"{self.BASE_URL}/event/getEventDetails.html?id={event_id}"
            data = await self._fetch_json(detail_url)
        
        if not data:
            return []

        # Phase 1: Read local context (Fast DB Read)
        # 阶段 1：读取本地上下文（快速数据库读取）
        loop = asyncio.get_running_loop()
        ctx = await loop.run_in_executor(None, self._get_sync_context_sync, event_id)
        
        # Phase 2: Enrich with Saoju Data (Pure DB Lookup - safe for concurrency)
        # 阶段 2：充实 Saoju 数据（纯数据库查找 - 并发安全）
        enrichment = await self._enrich_ticket_data_async(event_id, data, ctx)
        
        # Phase 3: Write Updates (Serialized DB Write)
        # 阶段 3：写入更新（串行数据库写入以避免锁定）
        async with self._db_write_lock:
            return await loop.run_in_executor(None, self._save_synced_data_sync, event_id, data, enrichment)

    def _get_sync_context_sync(self, event_id: str) -> Dict:
        """Read relevant local state before sync."""
        with session_scope() as session:
            event = session.get(HulaquanEvent, event_id)
            if not event:
                return {"exists": False}
            
            # Map ticket ID -> {city, has_casts}
            tickets_ctx = {}
            for t in event.tickets:
                has_casts = len(t.cast_members) > 0
                tickets_ctx[t.id] = {"city": t.city, "has_casts": has_casts}
                
            return {
                "exists": True,
                "title": event.title,
                "location": event.location, # Added location
                "saoju_musical_id": event.saoju_musical_id,
                "tickets": tickets_ctx
            }

    async def _enrich_ticket_data_async(self, event_id: str, data: dict, ctx: dict) -> Dict:
        """Perfom all Saoju lookups without holding DB lock."""
        res = {
            "saoju_musical_id": ctx.get("saoju_musical_id"),
            "tickets": {} # map tid -> {city: ..., casts: []}
        }
        
        b_info = data.get("basic_info", {})
        title = b_info.get("title", "")
        if not title and ctx.get("title"):
             title = ctx.get("title", "")
        
        # Determine Event-Level City Hints
        # Try to detect city from Event Location or Event Title
        # This serves as a fallback for tickets that don't satisfy self-resolution
        event_city_hint = None
        
        # 1. From Location (Most reliable if present, e.g. "Shanghai Grand Theatre")
        loc = b_info.get("location") or ctx.get("location")
        if loc:
            event_city_hint = self._city_resolver.resolve_from_text(loc)
            
        # 2. From Title (e.g. "【Shanghai】...")
        if not event_city_hint:
             event_city_hint = self._city_resolver.resolve_from_text(title)

        # 1. Auto-Link Musical ID if missing
        if not res["saoju_musical_id"]:
            try:
                search_name = extract_text_in_brackets(title, keep_brackets=False)
                mid = await self._saoju.resolve_musical_id_by_name(search_name)
                if mid:
                    res["saoju_musical_id"] = mid
            except Exception as e:
                log.warning(f"Failed to auto-link musical ID for {title}: {e}")

        # 2. Process Tickets for City/Casts
        ticket_details = data.get("ticket_details", [])
        for t_data in ticket_details:
            tid = str(t_data.get("id"))
            if not tid: continue
            
            t_title = t_data.get("title", "")
            if not t_title and int(t_data.get("total_ticket", 0)) == 0: continue # Invalid filter
            
            # Context for this ticket
            t_ctx = ctx.get("tickets", {}).get(tid, {})
            current_city = t_ctx.get("city")
            has_casts = t_ctx.get("has_casts", False)
            
            # Parse time
            session_time = self._parse_api_date(t_data.get("start_time"))
            
            enrich_t = {}
            
            # City Logic
            # Priority: 1. Existing DB City -> 2. Ticket Title -> 3. Saoju Lookup -> 4. Event Hint
            # Actually, if existing DB city is WRONG (poisoned), we might want to correct it?
            # But we can't easily know if it's wrong unless we force re-eval.
            # For now, let's assume if it's set, it's trusted, UNLESS we are in a 'reset' scenario where it's cleared.
            
            # If no city, try to resolve from Ticket Title first
            # (Skipped here as logic 4&5 in _save handles title extraction fallback, but we need it for Saoju lookup NOW)
            if not current_city:
                 city_from_title = self._city_resolver.resolve_from_text(t_title)
                 if city_from_title:
                     current_city = city_from_title
                     enrich_t["city"] = current_city
            
            # If still no city, try Saoju or Event Hint
            if not current_city and session_time and self._saoju:
                try:
                    search_name = extract_text_in_brackets(title, keep_brackets=False)
                    date_str = session_time.strftime("%Y-%m-%d")
                    time_str = session_time.strftime("%H:%M")
                    
                    # Use Event Hint if available to narrow search
                    search_city = event_city_hint
                    
                    saoju_match = await self._saoju.search_for_musical_by_date(
                        search_name, date_str, time_str, city=search_city, musical_id=res["saoju_musical_id"]
                    )
                    
                    if saoju_match and saoju_match.get("city"):
                        enrich_t["city"] = saoju_match.get("city")
                        current_city = enrich_t["city"]
                except Exception as e:
                    pass
            
            # Fallback: If we didn't find specific match but have an event hint, assume event city
            if not current_city and event_city_hint:
                current_city = event_city_hint
                enrich_t["city"] = current_city
                
            # Cast Logic
            if not has_casts and session_time:
                 try:
                    search_name = extract_text_in_brackets(title, keep_brackets=False)
                    # Use potentially newly found city
                    c_data = await self._saoju.get_cast_for_hulaquan_session(
                        search_name, session_time, current_city
                    )
                    if c_data:
                        enrich_t["casts"] = c_data
                 except Exception as e:
                    pass
            
            if enrich_t:
                res["tickets"][tid] = enrich_t
                
        return res

    def _save_synced_data_sync(self, event_id: str, data: dict, enrichment: dict) -> List[TicketUpdate]:
        """Perform all DB writes in a single fast transaction."""
        updates = []
        with session_scope() as session:
            # 1. Sync Event
            b_info = data.get("basic_info", {})
            event = session.get(HulaquanEvent, event_id)
            if not event:
                event = HulaquanEvent(id=event_id, title=b_info.get("title", ""))
                session.add(event)
            
            event.title = b_info.get("title", event.title)
            event.location = b_info.get("location", event.location)
            event.start_time = self._parse_api_date(b_info.get("start_time"))
            event.end_time = self._parse_api_date(b_info.get("end_time"))
            event.updated_at = timezone_now()
            
            # Update Musical ID if found in enrichment
            if enrichment.get("saoju_musical_id") and event.saoju_musical_id != enrichment["saoju_musical_id"]:
                 event.saoju_musical_id = enrichment["saoju_musical_id"]
                 event.last_synced_at = timezone_now()
                 session.add(event)
            
            # 2. Sync Tickets
            ticket_details = data.get("ticket_details", [])
            for t_data in ticket_details:
                tid = str(t_data.get("id"))
                if not tid: continue
                
                total_ticket = int(t_data.get("total_ticket", 0))
                left_ticket = int(t_data.get("left_ticket_count", 0))
                price = float(t_data.get("ticket_price", 0))
                status = t_data.get("status", "active")
                title = t_data.get("title", "")
                
                if not title and total_ticket == 0: continue
                # Allow 'expired' status to pass through to update DB
                # 允许 'expired' 状态通过以更新数据库
                
                ticket = session.get(HulaquanTicket, tid)

                is_new = False
                
                if not ticket:
                    is_new = True
                    ticket = HulaquanTicket(id=tid, event_id=event_id, title=title)
                    session.add(ticket)
                
                # Parse session time and extract cast names for detailed display
                # 解析场次时间和提取演员列表用于详细展示
                session_time = self._parse_api_date(t_data.get("start_time"))
                t_enrich = enrichment.get("tickets", {}).get(tid, {})
                
                # Logic: enrichment (new fetch) > existing DB > empty
                # 逻辑：enrichment (新抓取) > 现有数据库 > 空
                cast_names_list = [c.get("artist") for c in t_enrich.get("casts", []) if c.get("artist")]
                
                if not cast_names_list and not is_new:
                     # If we didn't fetch new info, but it's an existing ticket, it might already have casts
                     # 如果没有抓取新信息，但这是一张现有票，它可能已经有卡司了
                     # Note: ticket object is attached to session, so we can access relationships
                     # 注意：ticket 对象已附加到 session，所以我们可以访问关系
                     if ticket.cast_members:
                         cast_names_list = [c.name for c in ticket.cast_members]
                
                # Notifications
                raw_valid_from = t_data.get("valid_from")
                valid_from = None
                if raw_valid_from:
                    try:
                        # Normalize to YYYY-MM-DD HH:mm
                        valid_from = standardize_datetime(raw_valid_from, return_str=True, with_second=False)
                    except Exception:
                        valid_from = raw_valid_from # Fallback to raw if parsing fails

                if is_new:
                    if status == "pending":
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="pending", message=f"⏲️开票: {title}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    elif left_ticket > 0:
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="new", message=f"🆕上新: {title} 余票{left_ticket}/{total_ticket}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                else:
                    # Detect status changes
                    if status == "pending" and ticket.status != "pending":
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="pending", message=f"⏲️开票: {title}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    elif ticket.status == "pending" and status == "active":
                        # CRITICAL: Pending -> Active transition means OPENED FOR SALE
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="new", message=f"🚀正式开票: {title}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    # --- ALIGNED LOGIC ---
                    elif total_ticket > ticket.total_ticket:
                        # 判定为 add (🟢补票) - 总票数增加
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="add", message=f"🟢补票: {title} 余票{left_ticket}/{total_ticket}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    elif ticket.stock == 0 and left_ticket > 0:
                        # 判定为 restock (♻️回流) - 余票从0变为正 (Level 2)
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="restock", message=f"♻️回流: {title} 余票{left_ticket}/{total_ticket}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    elif left_ticket > ticket.stock:
                        # 判定为 back (➕票增) - 余票在正数基础上增加 (Level 3)
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="back", message=f"➕票增: {title} 余票{left_ticket}/{total_ticket}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    elif left_ticket < ticket.stock:
                        # 判定为 decrease (➖票减) - 余票减少 (Level 4)
                        updates.append(TicketUpdate(
                            ticket_id=tid, event_id=event_id, event_title=event.title, 
                            change_type="decrease", message=f"➖票减: {title} 余票{left_ticket}/{total_ticket}",
                            session_time=session_time, price=price, stock=left_ticket, 
                            total_ticket=total_ticket, cast_names=cast_names_list, valid_from=valid_from
                        ))
                    # ----------------------

                # Updates
                ticket.title = title
                ticket.stock = left_ticket
                ticket.total_ticket = total_ticket
                ticket.price = price
                ticket.status = status
                ticket.valid_from = valid_from
                ticket.session_time = session_time  # Already parsed above
                
                # Apply Enrichment (City)
                if t_enrich.get("city"):
                    ticket.city = t_enrich["city"]
                elif not ticket.city:
                    # Logic 4 & 5 (Text Extraction) fallback
                    info = extract_title_info(title)
                    if info.get("city"): ticket.city = info.get("city")

                # Apply Enrichment (Casts)
                if t_enrich.get("casts"):
                     # 获取 musical_id 和 role_orders 用于排序
                     musical_id = event.saoju_musical_id
                     role_orders = {}
                     if musical_id:
                         role_orders = self._saoju.data.get("artist_indexes", {}).get("role_orders", {}).get(str(musical_id), {})
                     
                     
                     for idx, c_item in enumerate(t_enrich["casts"]):
                        artist_name = c_item.get("artist")
                        role_name = c_item.get("role")
                        if not artist_name: continue
                        
                        stmt = select(HulaquanCast).where(HulaquanCast.name == artist_name)
                        cast_obj = session.exec(stmt).first()
                        if not cast_obj:
                            cast_obj = HulaquanCast(name=artist_name)
                            session.add(cast_obj)
                            session.flush() # Need ID
                        
                        # Use source index as rank (0-based)
                        # This guarantees storage order matches source string order
                        rank = idx
                        
                        # Check exist
                        stmt_assoc = select(TicketCastAssociation).where(
                            TicketCastAssociation.ticket_id == tid,
                            TicketCastAssociation.cast_id == cast_obj.id,
                            TicketCastAssociation.role == role_name
                        )
                        existing_assoc = session.exec(stmt_assoc).first()
                        if not existing_assoc:
                            assoc = TicketCastAssociation(
                                ticket_id=tid, 
                                cast_id=cast_obj.id, 
                                role=role_name,
                                rank=rank
                            )
                            session.add(assoc)
                        elif existing_assoc.rank != rank:
                            # Update rank if changed
                            existing_assoc.rank = rank
                            session.add(existing_assoc)


            # Write updates to TicketUpdateLog table for persistence
            # 将更新写入 TicketUpdateLog 表以持久化
            for update in updates:
                # CRITICAL FIX: If cast_names is empty, try to get it from DB
                # 关键修复：如果 cast_names 为空，尝试从数据库获取
                # This handles the case where cast associations were created AFTER the TicketUpdate object
                # 这处理了在 TicketUpdate 对象创建之后才建立卡司关联的情况
                final_cast_names = update.cast_names
                
                # --- CAST SORTING LOGIC ---
                # Sort cast names by official role sequence if possible
                try: 
                    # We need musical_id. Event might have it.
                    # Note: event object is in session context
                    current_event = session.get(HulaquanEvent, update.event_id)
                    musical_id = current_event.saoju_musical_id if current_event else None
                    
                    if musical_id:
                        # Helper to get sequence
                        # Since we are in sync method, and get_role_seq is async, we need a way to call it.
                        # Actually HulaquanService has reference to _saoju (SaojuService).
                        # SaojuService methods are async. We need a synchronous way or access internal data?
                        # SaojuService.data is a dict. We can access it directly if we are careful.
                        # But get_role_seq logic ensures index is built.
                        # Index should have been built during _sync_event_details -> _enrich_ticket_data_async -> ...
                        # It's better to preload it or access data directly.
                        
                        # Let's check if we can access data directly for now, assuming indexes are loaded.
                        # Or better: We can fetch role map in `sync_all_data` once and pass it down.
                        # But `_save_synced_data_sync` is sync.
                        
                        # Accessing `self._saoju.data["artist_indexes"]["role_orders"]` directly.
                        role_orders = self._saoju.data.get("artist_indexes", {}).get("role_orders", {}).get(str(musical_id), {})
                        
                        if not role_orders and self._saoju.data.get("artist_indexes") is None:
                             # If indexes not loaded, we can't sort efficiently in sync context without blocking.
                             # Skip sorting or accept best effort.
                             pass
                        
                        if role_orders:
                             # We need to map artist name -> role name to get seq
                             # But `final_cast_names` is just a list of names.
                             # We need the association to know the role.
                             # `update.cast_names` came from enrichment which had role info but we only kept names list.
                             # `ticket.cast_members` is list of casts.
                             # We need to look up role for each artist name.
                             # `TicketCastAssociation` has the role.
                             
                             # Re-fetch associations to be sure
                             stmt_roles = select(HulaquanCast.name, TicketCastAssociation.role).join(TicketCastAssociation).where(
                                 TicketCastAssociation.ticket_id == update.ticket_id,
                                 HulaquanCast.id == TicketCastAssociation.cast_id
                             )
                             cast_roles = session.exec(stmt_roles).all()
                             # Map: ArtistName -> RoleName
                             artist_role_map = {cname: role for cname, role in cast_roles}
                             
                             def get_seq(artist_name):
                                 role = artist_role_map.get(artist_name)
                                 if not role: return 999
                                 return role_orders.get(role, 999)
                                 
                             if final_cast_names:
                                 final_cast_names.sort(key=get_seq)
                except Exception as e:
                    log.warning(f"Failed to sort cast names: {e}")
                # --------------------------

                if not final_cast_names:
                    # Flush to ensure all associations are committed
                    # 刷新以确保所有关联都已提交
                    session.flush()
                    
                    # Get the ticket and check if it has cast_members now
                    # 获取票据并检查是否现在有 cast_members
                    ticket_obj = session.get(HulaquanTicket, update.ticket_id)
                    if ticket_obj and ticket_obj.cast_members:
                        final_cast_names = [c.name for c in ticket_obj.cast_members]
                
                log_entry = TicketUpdateLog(
                    ticket_id=update.ticket_id,
                    event_id=update.event_id,
                    event_title=update.event_title,
                    change_type=update.change_type,
                    message=update.message,
                    session_time=update.session_time,
                    price=update.price,
                    stock=update.stock,
                    total_ticket=update.total_ticket,
                    cast_names=json.dumps(final_cast_names) if final_cast_names else None,
                    valid_from=update.valid_from
                )
                session.add(log_entry)

            # 3. Cleanup Orphaned Tickets (Diff Cleanup)
            # 3. 清理孤儿票据（差集清理）
            # Tickets in DB for this event but NOT in current API response
            # 数据库中有但当前 API 响应中没有的票据
            api_ticket_ids = set()
            for t_data in ticket_details:
                if t_data.get("id"):
                    api_ticket_ids.add(str(t_data.get("id")))

            db_tickets = session.exec(select(HulaquanTicket).where(HulaquanTicket.event_id == event_id)).all()
            for db_t in db_tickets:
                if db_t.id not in api_ticket_ids:
                    # Logic: If API doesn't return it, it's removed/hidden by platform.
                    # We should remove it or mark as expired. 
                    # Given user wants to keep history but "remove outdated data", deletion seems cleaner for "vanished" tickets,
                    # while "expired" status handles tickets clearly marked as expired by API.
                    # 逻辑：如果 API 没有返回它，说明它已被平台移除/隐藏。
                    # 我们应该删除它或标记为过期。
                    # 鉴于用户希望保留历史记录但“删除过时数据”，对于“消失”的票据，删除似乎更干净。
                    # 而“过期”状态用于处理 API 明确标记为过期的票据。
                    log.info(f"Removing orphaned ticket {db_t.id} ({db_t.title}) from event {event_id}")
                    session.delete(db_t)

            session.commit()
        return updates

    def _parse_api_date(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return standardize_datetime(date_str, return_str=False)
        except Exception:
            return None

    async def search_events(self, query: str) -> List[EventInfo]:
        """Search events by title query (case-insensitive).
        按标题查询搜索事件（不区分大小写）。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_events_sync, query)

    async def search_events_smart(self, query: str) -> List[EventInfo]:
        """
        智能搜索剧目：支持“标题 城市”或“标题 关键词”格式。
        """
        # 1. 尝试直接搜索
        results = await self.search_events(query)
        
        # 2. 如果没找到，尝试拆分搜索 (标题 + 城市/关键词)
        filter_keyword = ""
        if not results and " " in query:
            parts = query.split(" ", 1)
            title_query = parts[0]
            filter_keyword = parts[1]
            if title_query:
                results = await self.search_events(title_query)
        
        # 3. 如果有筛选词，进行辅助过滤
        if results and filter_keyword:
            filtered = []
            kw = filter_keyword.lower()
            for event in results:
                # 检查 城市、地点、标题
                search_text = f"{event.city or ''} {event.location or ''} {event.title or ''}".lower()
                if kw in search_text:
                    filtered.append(event)
            
            if filtered:
                results = filtered
        
        return results

    def _search_events_sync(self, query: str) -> List[EventInfo]:
        with session_scope() as session:
            statement = select(HulaquanEvent).where(HulaquanEvent.title.contains(query))
            events = session.exec(statement).all()
            
            result = []
            for event in events:
                # Load tickets
                # 加载票据
                tickets = []
                for t in event.tickets:
                    if t.status == "expired": continue
                    
                    # Fetch cast info
                    # 获取演员信息
                    cast_infos = []
                    stmt_c = (
                        select(HulaquanCast, TicketCastAssociation.role)
                        .join(TicketCastAssociation)
                        .where(TicketCastAssociation.ticket_id == t.id)
                        .order_by(TicketCastAssociation.rank, HulaquanCast.name)
                    )
                    cast_results = session.exec(stmt_c).all()
                    for c_obj, role in cast_results:
                        cast_infos.append(CastInfo(name=c_obj.name, role=role))

                    tickets.append(TicketInfo(
                        id=t.id,
                        title=t.title,
                        session_time=t.session_time,
                        price=t.price,
                        stock=t.stock,
                        total_ticket=t.total_ticket,
                        city=t.city,
                        status=t.status,
                        valid_from=t.valid_from,
                        cast=cast_infos
                    ))
                
                result.append(self._format_event_info(event, tickets))
            return result
            
    async def search_actors(self, query: str) -> List[CastInfo]:
        """Search actors by name (case-insensitive)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_actors_sync, query)
    
    def _search_actors_sync(self, query: str) -> List[CastInfo]:
        from sqlmodel import col
        with session_scope() as session:
            # Simple contains search
            stmt = select(HulaquanCast).where(col(HulaquanCast.name).contains(query))
            artists = session.exec(stmt).all()
            return [CastInfo(name=a.name, role="") for a in artists]

    async def get_event(self, event_id: str) -> Optional[EventInfo]:
        """Get single event details by ID.
        按 ID 获取单个事件详情。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_event_sync, event_id)

    def _get_event_sync(self, event_id: str) -> Optional[EventInfo]:
        with session_scope() as session:
            event = session.get(HulaquanEvent, event_id)
            if not event:
                return None
            
            # Load tickets
            tickets = []
            for t in event.tickets:
                if t.status == "expired": continue
                
                # Fetch cast info
                cast_infos = []
                stmt_c = (
                    select(HulaquanCast, TicketCastAssociation.role)
                    .join(TicketCastAssociation)
                    .where(TicketCastAssociation.ticket_id == t.id)
                    .order_by(TicketCastAssociation.rank, HulaquanCast.name)
                )
                cast_results = session.exec(stmt_c).all()
                for c_obj, role in cast_results:
                    cast_infos.append(CastInfo(name=c_obj.name, role=role))

                tickets.append(TicketInfo(
                    id=t.id,
                    title=t.title,
                    session_time=t.session_time,
                    price=t.price,
                    stock=t.stock,
                    total_ticket=t.total_ticket,
                    city=t.city,
                    status=t.status,
                    valid_from=t.valid_from,
                    cast=cast_infos
                ))
            
            return self._format_event_info(event, tickets)

    def _format_event_info(self, event: HulaquanEvent, tickets: List[TicketInfo]) -> EventInfo:
        """Helper to format HulaquanEvent into EventInfo with calculated fields.
        将 HulaquanEvent 格式化为带有计算字段的 EventInfo 的帮助程序。
        """
        # 1. City Extraction
        city = extract_title_info(event.title).get("city")
        if not city and event.location:
            city = detect_city_in_text(event.location)
        if not city and tickets:
            for t in tickets:
                if t.city:
                    city = t.city
                    break
        
        # Fallback: Inference from Venue Rules
        if not city:
            city = self._apply_city_rules(city, event.location)
        
        # 2. Stock and Price Calculation
        total_stock = sum(t.stock for t in tickets)
        prices = [t.price for t in tickets if t.price > 0]
        
        if prices:
            min_p = min(prices)
            max_p = max(prices)
            if min_p == max_p:
                price_range = f"¥{int(min_p) if min_p.is_integer() else min_p}"
            else:
                price_range = f"¥{int(min_p) if min_p.is_integer() else min_p}-{int(max_p) if max_p.is_integer() else max_p}"
        else:
            price_range = "待定"

        # 3. Schedule Range Calculation
        start = event.start_time
        end = event.end_time
        
        if not (start and end) and tickets:
            session_times = [t.session_time for t in tickets if t.session_time]
            if session_times:
                if not start: start = min(session_times)
                if not end: end = max(session_times)
        
        if start and end:
            if start.date() == end.date():
                schedule_range = start.strftime("%Y.%m.%d")
            else:
                if start.year == end.year:
                    schedule_range = f"{start.strftime('%Y.%m.%d')}-{end.strftime('%m.%d')}"
                else:
                    # Different years
                    schedule_range = f"{start.strftime('%Y.%m.%d')}-{end.strftime('%Y.%m.%d')}"
        else:
            schedule_range = "待定"

        return EventInfo(
            id=event.id,
            title=event.title,
            location=event.location,
            city=city,
            update_time=event.updated_at,
            total_stock=total_stock,
            price_range=price_range,
            schedule_range=schedule_range,
            tickets=tickets
        )
        
    def _enrich_ticket_city(self, ticket: HulaquanTicket, event: HulaquanEvent) -> Optional[str]:
        """Resolve city for a ticket using multiple fallback strategies.
        Order:
        1. Config Rules (Venue)
        2. Config Rules (Title)
        3. DB City
        4. Ticket Title Extraction
        5. Event Title Extraction
        6. Event Location Extraction
        """
        # 1. Config Rules (Venue)
        if event.location:
            city = self._city_resolver.from_venue(event.location)
            if city: return city

        # 2. Config Rules (Title) - Check ticket title then event title
        city = self._city_resolver.from_title(ticket.title)
        if city: return city
        
        city = self._city_resolver.from_title(event.title)
        if city: return city

        # 3. Existing DB City
        if ticket.city:
            return ticket.city

        # 4 & 5. Text Extraction (Title)
        info = extract_title_info(ticket.title)
        if info.get("city"): return info.get("city")
        
        info = extract_title_info(event.title)
        if info.get("city"): return info.get("city")

        # 6. Text Extraction (Location)
        if event.location:
            city = detect_city_in_text(event.location)
            if city: return city
            
        return None

    async def get_events_by_date(self, check_date: datetime, city: Optional[str] = None) -> List[TicketInfo]:
        """Get tickets performing on a specific date.
        获取特定日期演出的票据。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_events_by_date_sync, check_date, city)

    def _get_events_by_date_sync(self, check_date: datetime, city: Optional[str] = None) -> List[TicketInfo]:
        start_of_day = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        with session_scope() as session:
            # Optimized: Eager load Event to prevent N+1 queries
            statement = (
                select(HulaquanTicket)
                .options(joinedload(HulaquanTicket.event))
                .where(
                    HulaquanTicket.session_time >= start_of_day,
                    HulaquanTicket.session_time < end_of_day
                )
            )
            if city:
                statement = statement.where(HulaquanTicket.city == city)
            
            tickets = session.exec(statement).all()
            if not tickets:
                return []
            
            # Optimized: Bulk fetch Casts for all retrieved tickets
            # This reduces N queries to 1 query
            tids = [t.id for t in tickets]
            cast_map = {} # tid -> List[CastInfo]
            
            if tids:
                stmt_c = (
                    select(TicketCastAssociation.ticket_id, HulaquanCast.name, TicketCastAssociation.role)
                    .join(HulaquanCast)
                    .where(TicketCastAssociation.ticket_id.in_(tids))
                )
                cast_rows = session.exec(stmt_c).all()
                for tid, cname, role in cast_rows:
                    if tid not in cast_map:
                        cast_map[tid] = []
                    cast_map[tid].append(CastInfo(name=cname, role=role))

            result = []
            
            for t in tickets:
                # No filtering for expired tickets here as requested for Date View
                
                # Event is already eager loaded via joinedload
                event = t.event
                
                # Enrich City
                final_city = self._enrich_ticket_city(t, event) if event else t.city
                
                # Use pre-fetched cast info
                cast_infos = cast_map.get(t.id, [])
                
                result.append(TicketInfo(
                    id=t.id,
                    event_id=t.event_id,
                    title=t.title,
                    session_time=t.session_time,
                    price=t.price,
                    stock=t.stock,
                    total_ticket=t.total_ticket,
                    city=final_city,
                    status=t.status,
                    valid_from=t.valid_from,
                    cast=cast_infos
                ))
            return result




    async def get_all_events(self) -> List[EventInfo]:
        """Get all known events."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_all_events_sync)

    def _get_all_events_sync(self) -> List[EventInfo]:
        with session_scope() as session:
            events = session.exec(select(HulaquanEvent)).all()
            results = []
            for e in events:
                # We need to process tickets to get stock/price for filtering
                processed_tickets = []
                # In list view, we don't necessarily need full ticket details for all events, 
                # but we need them for total_stock calculation if we want precision.
                # However, for the list view, we can just pass empty tickets to _format_event_info 
                # if it can handle it, or just fetch them.
                # Let's fetch them since we need total_stock.
                
                # To avoid heavy DB load in get_all_events, we can optimize later.
                # For now, let's keep it consistent.
                
                # Actually, let's just use the logic from get_all_events but cleaner.
                
                # Filter Expired: Skip events where all sessions are in the past
                # 过滤已过期：跳过所有场次均已过期的演出
                all_sessions = [t.session_time for t in e.tickets if t.session_time]
                if all_sessions:
                    # Check if the latest session is still in the past
                    # 检查最晚的场次是否仍在过去
                    # Using naive comparison assuming session_time is naive (local) and system is local
                    if max(all_sessions) < datetime.now():
                        continue

                # Calculate basic info
                total_stock = sum(t.stock for t in e.tickets)
                
                if total_stock > 0:
                    # For performance in list, we might not want to hydrate all CastInfo.
                    # But _format_event_info expects TicketInfo list.
                    # Let's just do a simplified version here or call _format_event_info with minimal ticket info.
                    
                    tickets_minimal = [TicketInfo(
                        id=t.id, title=t.title, session_time=t.session_time, 
                        price=t.price, stock=t.stock, total_ticket=t.total_ticket, 
                        city=t.city, status=t.status
                    ) for t in e.tickets if t.status != "expired"]
                    
                    results.append(self._format_event_info(e, tickets_minimal))
            
            # Sort Logic:
            # 1. City Count (Popular cities first)
            # 2. Update Time (Recently updated first)
            
            # Compute City Counts
            city_counts = {}
            for r in results:
                c = r.city or "其他"
                city_counts[c] = city_counts.get(c, 0) + 1
            
            # Sort
            def sort_key(item):
                c_count = city_counts.get(item.city or "其他", 0)
                # Ensure update_time is comparable (handle None)
                u_time = item.update_time.timestamp() if item.update_time else 0
                return (c_count, u_time)

            results.sort(key=sort_key, reverse=True)

            return results

    async def fix_legacy_data(self):
        """
        Maintenance method to fix legacy data validation.
        维护方法，用于修复存量数据的有效性。
        Fixes orphaned tickets from old events that are no longer in recommendation list.
        修复不再出现在推荐列表中的旧事件的孤立票据。
        Constraint: session_time < now AND status != 'expired' -> status = 'expired'
        约束：场次时间 < 现在 且 状态 != 'expired' -> 设为 'expired'
        """
        log.info("Starting legacy data maintenance...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._fix_legacy_data_sync)
        log.info("Legacy data maintenance complete.")

    def _fix_legacy_data_sync(self):
        from zoneinfo import ZoneInfo
        
        with session_scope() as session:
            # Find all active/pending tickets with past session_time
            # 查找所有 session_time 为过去且状态为 active/pending 的票据
            now = timezone_now()
            now_naive = now.replace(tzinfo=None)  # For comparison with naive datetimes
            shanghai_tz = ZoneInfo("Asia/Shanghai")
            
            statement = select(HulaquanTicket).where(
                HulaquanTicket.status.in_(["active", "pending"])
            )
            tickets = session.exec(statement).all()
            
            count = 0
            for t in tickets:
                # Double check with timezone handling
                # 双重检查并处理时区问题
                if t.session_time:
                    # Check if datetime is naive or aware
                    if t.session_time.tzinfo is None:
                        # Naive: localize to Shanghai then compare
                        session_time_aware = t.session_time.replace(tzinfo=shanghai_tz)
                        if session_time_aware < now:
                            t.status = "expired"
                            session.add(t)
                            count += 1
                    else:
                        # Already aware: direct comparison
                        if t.session_time < now:
                            t.status = "expired"
                            session.add(t)
                            count += 1
            
            session.commit()
            log.info(f"Fixed {count} expired legacy tickets.")

    async def get_aliases(self) -> List[HulaquanAlias]:
        """Get all theater aliases.
        获取所有剧院别名。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_aliases_sync)

    def _get_aliases_sync(self) -> List[HulaquanAlias]:
        with session_scope() as session:
            return session.exec(select(HulaquanAlias)).all()

    async def add_alias(self, event_id: str, alias: str, search_name: Optional[str] = None):
        """Add or update an alias for an event.
        添加或更新事件的别名。
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._add_alias_sync, event_id, alias, search_name)

    def _add_alias_sync(self, event_id: str, alias: str, search_name: Optional[str] = None):
        with session_scope() as session:
            stmt = select(HulaquanAlias).where(HulaquanAlias.alias == alias)
            alias_obj = session.exec(stmt).first()
            if not alias_obj:
                alias_obj = HulaquanAlias(event_id=event_id, alias=alias)
                session.add(alias_obj)
            else:
                alias_obj.event_id = event_id
            
            if search_name:
                curr_names = alias_obj.search_names.split(",") if alias_obj.search_names else []
                if search_name not in curr_names:
                    curr_names.append(search_name)
                    alias_obj.search_names = ",".join(curr_names)
            
            session.commit()



    async def get_event_id_by_name(self, name: str) -> Optional[Tuple[str, str]]:
        """
        Try to find event ID by title or alias.
        Returns (id, title) or None.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_event_id_by_name_sync, name)

    def _get_event_id_by_name_sync(self, name: str) -> Optional[Tuple[str, str]]:
        with session_scope() as session:
            # 1. Exact title match
            # 1. 精确标题匹配
            stmt = select(HulaquanEvent).where(HulaquanEvent.title == name)
            event = session.exec(stmt).first()
            if event:
                return event.id, event.title
            
            # 2. Alias match
            # 2. 别名匹配
            stmt_a = select(HulaquanAlias).where(HulaquanAlias.alias == name)
            alias = session.exec(stmt_a).first()
            if alias:
                stmt_e = select(HulaquanEvent).where(HulaquanEvent.id == alias.event_id)
                event = session.exec(stmt_e).first()
                if event:
                    return event.id, event.title
            
            # 3. Partial title match
            # 3. 部分标题匹配
            stmt_p = select(HulaquanEvent).where(HulaquanEvent.title.contains(name))
            event = session.exec(stmt_p).first()
            if event:
                return event.id, event.title
                
            return None
    async def get_event_details_by_id(self, event_id: str) -> List[EventInfo]:
        """Get full details for a single event by ID.
        按 ID 获取单个事件的完整详细信息。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_event_details_by_id_sync, event_id)

    def _get_event_details_by_id_sync(self, event_id: str) -> List[EventInfo]:
        from sqlalchemy.orm import selectinload
        with session_scope() as session:
            # Optimized: Eager load tickets to avoid N+1 if accessed
            stmt = select(HulaquanEvent).options(selectinload(HulaquanEvent.tickets)).where(HulaquanEvent.id == event_id)
            event = session.exec(stmt).first()
            
            if not event:
                return []
            
            # Optimized: Bulk fetch Casts for all tickets of this event
            tickets_list = event.tickets
            tids = [t.id for t in tickets_list if t.status != TicketStatus.EXPIRED]
            
            cast_map = {}
            if tids:
                stmt_c = (
                    select(TicketCastAssociation.ticket_id, HulaquanCast.name, TicketCastAssociation.role)
                    .join(HulaquanCast)
                    .where(TicketCastAssociation.ticket_id.in_(tids))
                )
                cast_rows = session.exec(stmt_c).all()
                for tid, cname, role in cast_rows:
                    if tid not in cast_map:
                        cast_map[tid] = []
                    cast_map[tid].append(CastInfo(name=cname, role=role))
            
            tickets = []
            for t in tickets_list:
                if t.status == TicketStatus.EXPIRED: continue
                
                # Fetch cast info (from map)
                cast_infos = cast_map.get(t.id, [])

                tickets.append(TicketInfo(
                    id=t.id,
                    title=t.title,
                    session_time=t.session_time,
                    price=t.price,
                    stock=t.stock,
                    total_ticket=t.total_ticket,
                    city=t.city,
                    status=t.status,
                    valid_from=t.valid_from,
                    cast=cast_infos
                ))
            
            return [self._format_event_info(event, tickets)]

    async def search_co_casts(self, cast_names: List[str]) -> List[Dict]:
        """
        Find tickets where ALL specified casts are performing together.
        查找所有指定演员共同演出的票据，返回扁平化数据以适配前端统计。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._search_co_casts_sync, cast_names)

    def _search_co_casts_sync(self, cast_names: List[str]) -> List[Dict]:
        if not cast_names:
            return []
            
        with session_scope() as session:
            # Find tickets for each cast
            ticket_sets = []
            for cast_name in cast_names:
                stmt = select(TicketCastAssociation.ticket_id).join(HulaquanCast).where(HulaquanCast.name == cast_name)
                tids = set(session.exec(stmt).all())
                ticket_sets.append(tids)
            
            if not ticket_sets:
                return []
                
            # Intersect to find common tickets
            common_tids = set.intersection(*ticket_sets)
            if not common_tids:
                return []
            
            # Fetch ticket details and format
            results = []
            for tid in sorted(list(common_tids)):
                t = session.get(HulaquanTicket, tid)
                if not t: continue
                
                # Fetch cast info for this ticket to get roles
                stmt_c = (
                    select(HulaquanCast, TicketCastAssociation.role)
                    .join(TicketCastAssociation)
                    .where(TicketCastAssociation.ticket_id == t.id)
                )
                cast_results = session.exec(stmt_c).all()
                
                # Map artist name to role
                role_map = {c_obj.name: role for c_obj, role in cast_results}
                
                # Order roles based on cast_names
                ordered_roles = [role_map.get(name, '未知角色') for name in cast_names]
                role_str = " & ".join(ordered_roles)
                
                # Other casts
                others = [c_obj.name for c_obj, _ in cast_results if c_obj.name not in cast_names]
                
                # Clean Title
                clean_title = t.title
                if t.event:
                    clean_title = extract_text_in_brackets(t.event.title, keep_brackets=False) or t.event.title
                
                # Date Formatting
                dt = t.session_time
                date_str = "-"
                year = timezone_now().year
                if dt:
                    year = dt.year
                    weekday_str = ['一', '二', '三', '四', '五', '六', '日'][dt.weekday()]
                    date_str = f"{dt.month:02d}月{dt.day:02d}日 星期{weekday_str} {dt.strftime('%H:%M')}"
                
                # Enrich City using service logic
                final_city = self._enrich_ticket_city(t, t.event) if t.event else t.city

                results.append({
                    "date": date_str,
                    "year": year,
                    "title": clean_title,
                    "role": role_str,
                    "others": others,
                    "city": final_city or "未知城市",
                    "location": (t.event.location if t.event else None) or "未知剧场",
                    "_raw_time": dt.isoformat() if dt else ""
                })
            
            # Sort by time
            results.sort(key=lambda x: x.get("_raw_time", ""))
            return results

    async def get_recent_updates(
        self,
        limit: int = 20,
        change_types: Optional[List[str]] = None
    ) -> List[TicketUpdate]:
        """
        Get recent ticket updates from the database.
        从数据库获取最近的票务更新。
        
        Args:
            limit: Maximum number of updates to return (default 20, max 100)
            change_types: List of change types to filter (e.g. ["new", "restock"])
        
        Returns:
            List of TicketUpdate objects with detailed fields
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_recent_updates_sync, limit, change_types)
    
    def _get_recent_updates_sync(self, limit: int, change_types: Optional[List[str]]) -> List[TicketUpdate]:
        # Cap limit to 100 for global safety, but we will use it per-type if types not specified
        limit = min(limit, 100)
        
        with session_scope() as session:
            now = timezone_now()
            
            # Helper to fetch updates for a set of types
            def fetch_type_updates(types_to_fetch, sub_limit):
                # We use outerjoin to HulaquanTicket to keep logs even if the ticket record is deleted
                # Using TicketUpdateLog.session_time for filtering to avoid dependency on the joined table
                stmt = select(TicketUpdateLog, HulaquanTicket).outerjoin(
                    HulaquanTicket, TicketUpdateLog.ticket_id == HulaquanTicket.id
                ).where(
                    or_(
                        TicketUpdateLog.session_time >= now,
                        TicketUpdateLog.session_time == None
                    )
                )
                
                if types_to_fetch:
                    stmt = stmt.where(TicketUpdateLog.change_type.in_(types_to_fetch))
                
                stmt = stmt.order_by(col(TicketUpdateLog.created_at).desc()).limit(sub_limit)
                return session.exec(stmt).all()

            all_results = []
            
            if not change_types:
                # If no specific types requested by frontend (unlikely in current implementation)
                # we group by our 4 core types and get 20 for each to build the 80-item buffer
                core_types = ['new', 'pending', 'restock', 'back']
                for ctype in core_types:
                    all_results.extend(fetch_type_updates([ctype], 20))
            else:
                # If specific types requested (e.g. user toggled pills)
                # We still fetch 20 for EACH requested type to ensure depth
                for ctype in change_types:
                    all_results.extend(fetch_type_updates([ctype], 20))

            # Deduplicate by ID just in case (though log IDs should be unique)
            seen_ids = set()
            unique_results = []
            for log_item, t_item in all_results:
                if log_item.id not in seen_ids:
                    unique_results.append((log_item, t_item))
                    seen_ids.add(log_item.id)

            # Sort the combined buffer by created_at DESC
            unique_results.sort(key=lambda x: x[0].created_at, reverse=True)
            
            # Convert to TicketUpdate objects
            updates = []
            # We don't slice yet, let frontend handle the 20-row limit for groups
            for log, ticket in unique_results:
                cast_names_list = None
                if log.cast_names:
                    try:
                        cast_names_list = json.loads(log.cast_names)
                    except Exception:
                        pass
                
                updates.append(TicketUpdate(
                    ticket_id=log.ticket_id,
                    event_id=log.event_id,
                    event_title=log.event_title,
                    change_type=log.change_type,
                    message=log.message,
                    session_time=log.session_time,
                    price=log.price,
                    stock=log.stock, 
                    total_ticket=log.total_ticket,
                    cast_names=cast_names_list,
                    created_at=log.created_at,
                    valid_from=log.valid_from or (ticket.valid_from if ticket else None) 
                ))
            
            return updates
