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
from services.hulaquan.utils import standardize_datetime, extract_title_info, extract_text_in_brackets, detect_city_in_text
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
        
        # 1. Fetch recommended events with retry logic (legacy behavior)
        # 1. 使用重试逻辑获取推荐事件（旧有行为）
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
        # 通过 timeMark 过滤事件（沿用旧有逻辑）
        basic_infos = [e["basic_info"] for e in data["events"] if e.get("timeMark", 0) > 0]
        event_ids = [str(e["id"]) for e in basic_infos]
        
        updates = []
        
        # 2. Sequentially fetch details for each event to avoid SQLite lock issues
        # 2. 顺序获取每个事件的详细信息以避免 SQLite 锁定问题
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
        """Fetch and sync a single event's details and tickets.
        获取并同步单个事件的详细信息和票据。
        """
        async with self._semaphore:
            detail_url = f"{self.BASE_URL}/event/getEventDetails.html?id={event_id}"
            data = await self._fetch_json(detail_url)
            if not data:
                return []

        updates = []
        with session_scope() as session:
            # 1. Sync Event
            # 1. 同步事件
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
            # 2. 同步票据
            ticket_details = data.get("ticket_details", [])
            for t_data in ticket_details:
                tid = str(t_data.get("id"))
                if not tid:
                    continue
                
                # Basic fields
                # 基本字段
                total_ticket = int(t_data.get("total_ticket", 0))
                left_ticket = int(t_data.get("left_ticket_count", 0))
                price = float(t_data.get("ticket_price", 0))
                status = t_data.get("status", "active")
                title = t_data.get("title", "")
                
                # Skip invalid tickets (following legacy logic)
                # 跳过无效票据（沿用旧有逻辑）
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
                # 检测状态更改以进行通知
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
                    # 检查状态是否更改为待处理
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
                # 更新票据属性
                ticket.title = title
                ticket.stock = left_ticket
                ticket.total_ticket = total_ticket
                ticket.price = price
                ticket.status = status
                ticket.valid_from = t_data.get("valid_from")
                ticket.session_time = self._parse_api_date(t_data.get("start_time"))
                
                # Extract city if not present
                # 如果不存在，则提取城市
                if not ticket.city:
                    info = extract_title_info(title)
                    ticket.city = info.get("city")
                
                # Auto-Link Logic: Try to find persistent Saoju ID (Before city/cast sync)
                # 自动关联逻辑：尝试查找持久的扫剧 ID（在城市/卡司同步之前）
                if not event.saoju_musical_id:
                    try:
                        search_name = extract_text_in_brackets(event.title, keep_brackets=False)
                        musical_id = await self._saoju.get_musical_id_by_name(search_name)
                        if musical_id:
                            event.saoju_musical_id = musical_id
                            event.last_synced_at = datetime.now()
                            session.add(event)
                            log.info(f"Auto-linked {event.title} to Saoju ID: {musical_id}")
                    except Exception as e:
                        log.warning(f"Failed to auto-link musical ID for {event.title}: {e}")

                # Fallback: Try to find city via Saoju match if still missing
                # 回退：如果仍然缺失，尝试通过扫剧匹配查找城市
                if not ticket.city and ticket.session_time and self._saoju:
                    try:
                        search_name = extract_text_in_brackets(event.title, keep_brackets=False)
                        date_str = ticket.session_time.strftime("%Y-%m-%d")
                        time_str = ticket.session_time.strftime("%H:%M")
                        
                        # Use ID if available for precision
                        saoju_match = await self._saoju.search_for_musical_by_date(
                            search_name, 
                            date_str, 
                            time_str, 
                            city=None,
                            musical_id=event.saoju_musical_id
                        )
                        if saoju_match and saoju_match.get("city"):
                            ticket.city = saoju_match.get("city")
                            log.info(f"Filled missing city for {title} via Saoju: {ticket.city}")
                    except Exception as e:
                        log.warning(f"Saoju fallback city search failed for {title}: {e}")

                # 3. Sync Casts (Enrichment)
                # 3. 同步演员阵容（丰富数据）
                if not ticket.cast_members and ticket.session_time:
                    # Search name from title brackets
                    # 从标题括号中搜索名称
                    search_name = extract_text_in_brackets(event.title, keep_brackets=False)
                    cast_data = await self._saoju.get_cast_for_show(
                        search_name, 
                        ticket.session_time, 
                        ticket.city,
                        musical_id=event.saoju_musical_id
                    )
                    
                    for c_item in cast_data:
                        artist_name = c_item.get("artist")
                        role_name = c_item.get("role")
                        if not artist_name: continue
                        
                        # Get or create Cast
                        # 获取或创建演员
                        stmt = select(HulaquanCast).where(HulaquanCast.name == artist_name)
                        cast_obj = session.exec(stmt).first()
                        if not cast_obj:
                            cast_obj = HulaquanCast(name=artist_name)
                            session.add(cast_obj)
                            session.flush()
                        
                        # Link with role
                        # 与角色关联
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
        """Search events by title query (case-insensitive).
        按标题查询搜索事件（不区分大小写）。
        """
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

    async def get_events_by_date(self, check_date: datetime, city: Optional[str] = None) -> List[TicketInfo]:
        """Get tickets performing on a specific date.
        获取特定日期演出的票据。
        """
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
                # 获取演员信息
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
        """Add or update a user subscription. mode=0 means unsubscribe.
        添加或更新用户订阅。mode=0 表示取消订阅。
        """
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
        """Get all subscriptions for a user.
        获取用户的所有订阅。
        """
        with session_scope() as session:
            stmt = select(HulaquanSubscription).where(HulaquanSubscription.user_id == user_id)
            return session.exec(stmt).all()

    async def get_all_events(self) -> List[EventInfo]:
        """Get all known events."""
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
            return results

    async def get_aliases(self) -> List[HulaquanAlias]:
        """Get all theater aliases.
        获取所有剧院别名。
        """
        with session_scope() as session:
            return session.exec(select(HulaquanAlias)).all()

    async def add_alias(self, event_id: str, alias: str, search_name: Optional[str] = None):
        """Add or update an alias for an event.
        添加或更新事件的别名。
        """
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
        with session_scope() as session:
            event = session.get(HulaquanEvent, event_id)
            if not event:
                return []
            
            # Reuse logic from search_events for ticket processing
            # 重用 search_events 的逻辑进行票务处理
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
            
            return [self._format_event_info(event, tickets)]

    async def search_co_casts(self, cast_names: List[str]) -> List[TicketInfo]:
        """
        Find tickets where ALL specified casts are performing together.
        查找所有指定演员共同演出的票据。
        """
        if not cast_names:
            return []
            
        with session_scope() as session:
            # Find tickets for each cast
            # 查找每个演员的票据
            ticket_sets = []
            for cast_name in cast_names:
                stmt = select(TicketCastAssociation.ticket_id).join(HulaquanCast).where(HulaquanCast.name == cast_name)
                tids = set(session.exec(stmt).all())
                ticket_sets.append(tids)
            
            if not ticket_sets:
                return []
                
            # Intersect to find common tickets
            # 求交集以查找共同票据
            common_tids = set.intersection(*ticket_sets)
            if not common_tids:
                return []
            
            # Fetch ticket details
            # 获取票据详细信息
            result = []
            for tid in sorted(list(common_tids)):
                t = session.get(HulaquanTicket, tid)
                if not t: continue
                
                # Fetch cast info (can be optimized with eager loading, but this is fine for now)
                # 获取演员信息（可以使用急切加载进行优化，但目前这样也可以）
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
