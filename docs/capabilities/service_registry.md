# Core Service Capability Registry

**Trigger**: When fetching data from Hulaquan/Saoju, syncing events, or accessing the database.

## Service Access Strategy
> [!WARNING]
> Do NOT instantiate `HulaquanService()` or `SaojuService()` inside a route if a global instance is available.
> *Exception*: Scripts/CLI tools should instantiate their own.

---

## Saoju Service (`services/saoju/service.py`)
*The "Brain" - Metadata & Knowledge Graph*

### `resolve_musical_id_by_name(name: str) -> str`
- **Purpose**: Fuzzy matching to find Saoju Musical ID.
- **Cost**: Medium (Read DB/Cache).
- **Use Case**: Linking a raw string "Phantom" to ID "61".

### `search_for_musical_by_date(...)` **[REFRACTORED]**
- **Purpose**: Find show context (City/Theatre) for a specific date/time.
- **Cost**: **Low** (Pure DB Lookup - SaojuShow).
- **Note**: No longer triggers Network I/O. Safe to use in loops.

### `match_co_casts(co_casts: List[str], ...) -> List[Dict]`
- **Purpose**: The "Cast Schedule" engine. Finds shows where listed artists perform.
- **Cost**: Medium (Complex SQL LIKE queries).
- **Features**: Supports single artist or combination.

### `get_cast_for_hulaquan_session(...)`
- **Purpose**: Get cast list for a specific show time/city.

---

## Hulaquan Service (`services/hulaquan/service.py`)
*The "Pipe" - Ticket Data Ingestion*

### `sync_all_data() -> List[TicketUpdate]`
- **Purpose**: The "Big Red Button". Syncs recommended events, updates DB, logs changes.
- **Concurrency**: Optimized with `asyncio.gather` + Semaphore(5).
- **Locking**: Uses `_db_write_lock` for safe SQLite writes.

### `get_recent_updates(limit=20)`
- **Purpose**: Read-only access to `TicketUpdateLog`.

---

## Database Patterns (`services/db/connection.py`)

### Context Manager: `session_scope()`
```python
from services.db.connection import session_scope
with session_scope() as session:
    # Do work
    # Auto-commits on exit
    # Auto-rollbacks on error
```
- **Constraint**: SQLite is single-writer. Short transactions only.
- **Retry**: Implementation includes logic to handle "database is locked".

---

## Network Patterns
- **Do NOT use**: `requests.get`, `aiohttp.ClientSession()` (raw).
- **USE**: `service._fetch_json(url)`.
    - Handles: BOM decoding (`utf-8-sig`), Retry logic, Error logging, User-Agent rotation.
