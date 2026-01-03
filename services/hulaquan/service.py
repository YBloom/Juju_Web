import asyncio
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set

import aiohttp
from sqlmodel import Session, select, or_

from services.db.connection import session_scope
from services.hulaquan.tables import (
    HulaquanEvent, 
    HulaquanTicket, 
    HulaquanCast, 
    TicketCastAssociation,
    HulaquanSubscription,
    HulaquanAlias
)
from services.hulaquan.models import (
    EventInfo, 
    TicketInfo, 
    CastInfo, 
    TicketUpdate,
    SearchResult
)
from services.hulaquan.utils import standardize_datetime, extract_title_info, extract_text_in_brackets
from services.saoju.service import SaojuService

log = logging.getLogger(__name__)

class HulaquanService:
    BASE_URL = "https://clubz.cloudsation.com"
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    
    def __init__(self):
        self._semaphore = asyncio.Semaphore(1)  # Sequential sync to avoid SQLite locking
        self._session: Optional[aiohttp.ClientSession] = None
        self._saoju = SaojuService()

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
            timeout = aiohttp.ClientTimeout(total=60, connect=15)
            self._session = aiohttp.ClientSession(
                headers=self.DEFAULT_HEADERS,
                connector=connector,
                timeout=timeout
            )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _fetch_json(self, url: str) -> Optional[Dict]:
        """Helper to fetch and parse JSON from API (handles BOM)."""
        await self._ensure_session()
        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    log.error(f"API Error {response.status}: {url}")
                    return None
                
                # Read as bytes first to handle BOM properly via utf-8-sig
                content = await response.read()
                try:
                    text = content.decode('utf-8-sig')
                    return json.loads(text)
                except Exception as e:
                    log.error(f"JSON decode error for {url}: {e}")
                    # Fallback
                    text = content.decode('utf-8', errors='ignore')
                    return json.loads(text)
        except Exception as e:
            log.error(f"Error fetching {url}: {e}")
            log.error(traceback.format_exc())
            return None

    async def sync_all_data(self) -> List[TicketUpdate]:
        """
        Synchronize local database with remote API.
        Returns a list of detected updates (new tickets, restocks, etc.)
        """
        log.info("Starting full Hulaquan data synchronization...")
        
        # 1. Fetch recommended events with retry logic (legacy behavior)
        limit = 95
        data = None
        while limit >= 10:
            url = f"{self.BASE_URL}/site/getevent.html?filter=recommendation&access_token=&limit={limit}&page=0"
            data = await self._fetch_json(url)
            if data is False or data is None:
                log.warning(f"API returned {data} for limit {limit}, retrying with smaller limit...")
                limit -= 5
                continue
            break
        
        if not data or "events" not in data:
            log.error(f"Failed to fetch event recommendations after retries. Last limit: {limit}")
            return []

        # Filter events by timeMark (following legacy logic)
        basic_infos = [e["basic_info"] for e in data["events"] if e.get("timeMark", 0) > 0]
        event_ids = [str(e["id"]) for e in basic_infos]
        
        updates = []
        
        # 2. Sequentially fetch details for each event to avoid SQLite lock issues
        for eid in event_ids:
            try:
                res = await self._sync_event_details(eid)
                if res:
                    updates.extend(res)
            except Exception as e:
                log.error(f"Error syncing event {eid}: {e}")
                log.error(traceback.format_exc())
        
        log.info(f"Synchronization complete. Detected {len(updates)} updates.")
        return updates

    async def _sync_event_details(self, event_id: str) -> List[TicketUpdate]:
        """Fetch and sync a single event's details and tickets."""
        async with self._semaphore:
            detail_url = f"{self.BASE_URL}/event/getEventDetails.html?id={event_id}"
            data = await self._fetch_json(detail_url)
            if not data:
                return []

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
            event.updated_at = datetime.now()
            
            # 2. Sync Tickets
            ticket_details = data.get("ticket_details", [])
            for t_data in ticket_details:
                tid = str(t_data.get("id"))
                if not tid:
                    continue
                
                # Basic fields
                total_ticket = int(t_data.get("total_ticket", 0))
                left_ticket = int(t_data.get("left_ticket_count", 0))
                price = float(t_data.get("ticket_price", 0))
                status = t_data.get("status", "active")
                title = t_data.get("title", "")
                
                # Skip invalid tickets (following legacy logic)
                if not title and total_ticket == 0:
                    continue
                if status == "expired":
                    continue

                ticket = session.get(HulaquanTicket, tid)
                is_new = False
                
                if not ticket:
                    is_new = True
                    ticket = HulaquanTicket(
                        id=tid, 
                        event_id=event_id, 
                        title=title
                    )
                    session.add(ticket)
                
                # Detect state changes for notification
                if is_new:
                    if status == "pending":
                        updates.append(TicketUpdate(
                            ticket_id=tid,
                            event_id=event_id,
                            event_title=event.title,
                            change_type="pending",
                            message=f"⏲️开票: {title} (开票时间: {t_data.get('valid_from') or '未知'})"
                        ))
                    elif left_ticket > 0:
                        updates.append(TicketUpdate(
                            ticket_id=tid,
                            event_id=event_id,
                            event_title=event.title,
                            change_type="new",
                            message=f"🆕上新: {title} 余票{left_ticket}/{total_ticket}"
                        ))
                else:
                    # Check for status change to pending
                    if status == "pending" and ticket.status != "pending":
                        updates.append(TicketUpdate(
                            ticket_id=tid,
                            event_id=event_id,
                            event_title=event.title,
                            change_type="pending",
                            message=f"⏲️开票: {title} (开票时间: {t_data.get('valid_from') or '未知'})"
                        ))
                    elif ticket.stock == 0 and left_ticket > 0:
                        updates.append(TicketUpdate(
                            ticket_id=tid,
                            event_id=event_id,
                            event_title=event.title,
                            change_type="restock",
                            message=f"♻️回流: {title} 余票{left_ticket}/{total_ticket}"
                        ))
                    elif left_ticket > ticket.stock:
                        updates.append(TicketUpdate(
                            ticket_id=tid,
                            event_id=event_id,
                            event_title=event.title,
                            change_type="back",
                            message=f"➕票增: {title} 余票{left_ticket}/{total_ticket}"
                        ))
                
                # Update ticket attributes
                ticket.title = title
                ticket.stock = left_ticket
                ticket.total_ticket = total_ticket
                ticket.price = price
                ticket.status = status
                ticket.valid_from = t_data.get("valid_from")
                ticket.session_time = self._parse_api_date(t_data.get("start_time"))
                
                # Extract city if not present
                if not ticket.city:
                    info = extract_title_info(title)
                    ticket.city = info.get("city")

                # 3. Sync Casts (Enrichment)
                if not ticket.cast_members and ticket.session_time:
                    # Search name from title brackets
                    search_name = extract_text_in_brackets(event.title, keep_brackets=False)
                    cast_data = await self._saoju.get_cast_for_show(
                        search_name, 
                        ticket.session_time, 
                        ticket.city
                    )
                    
                    for c_item in cast_data:
                        artist_name = c_item.get("artist")
                        role_name = c_item.get("role")
                        if not artist_name: continue
                        
                        # Get or create Cast
                        stmt = select(HulaquanCast).where(HulaquanCast.name == artist_name)
                        cast_obj = session.exec(stmt).first()
                        if not cast_obj:
                            cast_obj = HulaquanCast(name=artist_name)
                            session.add(cast_obj)
                            session.flush()
                        
                        # Link with role
                        assoc = TicketCastAssociation(
                            ticket_id=tid,
                            cast_id=cast_obj.id,
                            role=role_name
                        )
                        session.add(assoc)
            
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
        """Search events by title query (case-insensitive)."""
        with session_scope() as session:
            statement = select(HulaquanEvent).where(HulaquanEvent.title.contains(query))
            events = session.exec(statement).all()
            
            result = []
            for event in events:
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
                
                result.append(EventInfo(
                    id=event.id,
                    title=event.title,
                    location=event.location,
                    update_time=event.updated_at,
                    tickets=tickets
                ))
            return result

    async def get_events_by_date(self, check_date: datetime, city: Optional[str] = None) -> List[TicketInfo]:
        """Get tickets performing on a specific date."""
        start_of_day = check_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        with session_scope() as session:
            statement = select(HulaquanTicket).where(
                HulaquanTicket.session_time >= start_of_day,
                HulaquanTicket.session_time < end_of_day
            )
            if city:
                statement = statement.where(HulaquanTicket.city == city)
            
            tickets = session.exec(statement).all()
            result = []
            for t in tickets:
                if t.status == "expired": continue
                
                # Fetch cast info
                cast_infos = []
                stmt_c = (
                    select(HulaquanCast, TicketCastAssociation.role)
                    .join(TicketCastAssociation)
                    .where(TicketCastAssociation.ticket_id == t.id)
                )
                cast_results = session.exec(stmt_c).all()
                for c_obj, role in cast_results:
                    cast_infos.append(CastInfo(name=c_obj.name, role=role))
                
                result.append(TicketInfo(
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
            return result

    async def manage_subscription(self, user_id: str, target_id: str, target_type: str, mode: int):
        """Add or update a user subscription. mode=0 means unsubscribe."""
        with session_scope() as session:
            statement = select(HulaquanSubscription).where(
                HulaquanSubscription.user_id == user_id,
                HulaquanSubscription.target_id == target_id,
                HulaquanSubscription.target_type == target_type
            )
            sub = session.exec(statement).first()
            if mode == 0:
                if sub:
                    session.delete(sub)
            else:
                if not sub:
                    sub = HulaquanSubscription(
                        user_id=user_id,
                        target_id=target_id,
                        target_type=target_type,
                        mode=mode
                    )
                    session.add(sub)
                else:
                    sub.mode = mode
            session.commit()

    async def get_user_subscriptions(self, user_id: str) -> List[HulaquanSubscription]:
        """Get all subscriptions for a user."""
        with session_scope() as session:
            stmt = select(HulaquanSubscription).where(HulaquanSubscription.user_id == user_id)
            return session.exec(stmt).all()

    async def get_all_events(self) -> List[HulaquanEvent]:
        """Get all known events."""
        with session_scope() as session:
            return session.exec(select(HulaquanEvent)).all()

    async def get_aliases(self) -> List[HulaquanAlias]:
        """Get all theater aliases."""
        with session_scope() as session:
            return session.exec(select(HulaquanAlias)).all()

    async def add_alias(self, event_id: str, alias: str, search_name: Optional[str] = None):
        """Add or update an alias for an event."""
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
        with session_scope() as session:
            # 1. Exact title match
            stmt = select(HulaquanEvent).where(HulaquanEvent.title == name)
            event = session.exec(stmt).first()
            if event:
                return event.id, event.title
            
            # 2. Alias match
            stmt_a = select(HulaquanAlias).where(HulaquanAlias.alias == name)
            alias = session.exec(stmt_a).first()
            if alias:
                stmt_e = select(HulaquanEvent).where(HulaquanEvent.id == alias.event_id)
                event = session.exec(stmt_e).first()
                if event:
                    return event.id, event.title
            
            # 3. Partial title match
            stmt_p = select(HulaquanEvent).where(HulaquanEvent.title.contains(name))
            event = session.exec(stmt_p).first()
            if event:
                return event.id, event.title
                
            return None
    async def get_event_details_by_id(self, event_id: str) -> List[EventInfo]:
        """Get full details for a single event by ID."""
        with session_scope() as session:
            event = session.get(HulaquanEvent, event_id)
            if not event:
                return []
            
            # Reuse logic from search_events for ticket processing
            tickets = []
            for t in event.tickets:
                if t.status == "expired": continue
                
                # Fetch cast info
                cast_infos = []
                stmt_c = (
                    select(HulaquanCast, TicketCastAssociation.role)
                    .join(TicketCastAssociation)
                    .where(TicketCastAssociation.ticket_id == t.id)
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
            
            return [EventInfo(
                id=event.id,
                title=event.title,
                location=event.location,
                update_time=event.updated_at,
                tickets=tickets
            )]

    async def search_co_casts(self, cast_names: List[str]) -> List[TicketInfo]:
        """
        Find tickets where ALL specified casts are performing together.
        """
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
            
            # Fetch ticket details
            result = []
            for tid in sorted(list(common_tids)):
                t = session.get(HulaquanTicket, tid)
                if not t: continue
                
                # Fetch cast info (can be optimized with eager loading, but this is fine for now)
                cast_infos = []
                stmt_c = (
                    select(HulaquanCast, TicketCastAssociation.role)
                    .join(TicketCastAssociation)
                    .where(TicketCastAssociation.ticket_id == t.id)
                )
                cast_results = session.exec(stmt_c).all()
                for c_obj, role in cast_results:
                    cast_infos.append(CastInfo(name=c_obj.name, role=role))
                
                result.append(TicketInfo(
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
            
            return result
