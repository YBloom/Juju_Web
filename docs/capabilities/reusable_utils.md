# Hulaquan Utils Capability Registry

**Location**: `services/hulaquan/utils.py`
**Trigger**: When parsing dates, extracting cities, cleaning text, or handling Chinese character alignment.

## Date & Time (High Reuse)

> [!IMPORTANT]
> Do NOT write your own `strptime` or regex for dates. Use these standard parsers which handle "Today", "Year wrapping", and generic formats.

### `standardize_datetime(dateAndTime, return_str=True, with_second=True)`
- **Purpose**: Powerhouse parser for various API date formats (ISO 8601, "YYYY-MM-DD", "MM-DD", etc.)
- **Inputs**: `dateAndTime` (str).
- **Outputs**: `datetime` object or formatted string.
- **Features**: Handles missing year (auto-fills current year), trims "Z", handles common separators (/, -, :).

### `standardize_datetime_for_saoju(dateAndTime, return_str=False, latest_str=None)`
- **Purpose**: Specialized parser for Saoju's human-readable formats like `8月3日 星期日 14:30`.
- **Special Logic**: 
    - Auto-infers year based on "distance to now" (handles year wrapping for Dec/Jan shows).
    - Can borrow date from `latest_str` if input is only HH:MM.

---

## Text Extraction (NLP-lite)

### `extract_text_in_brackets(text, keep_brackets=True)`
- **Purpose**: Extract musical title from `《Phantom of the Opera》`.
- **Usage**: Use `keep_brackets=False` to get raw title for searching.

### `detect_city_in_text(text)`
- **Purpose**: O(1) high-performance city extraction using compiled regex Aho-Corasick style massive OR pattern.
- **Scope**: Covers ~300 Chinese cities.
- **Performance**: Optimized with module-level `CITY_PATTERN` compilation.

### `extract_title_info(text)`
- **Purpose**: Composite extractor. Returns `{title, price, full_price, city}` from a raw text blob.

---

## Formatting

### `ljust_for_chinese(s, width, fillchar=' ')`
- **Purpose**: Correctly pads strings containing wide Chinese characters (count as 2 visual spaces) for console alignment.
- **Use Case**: CLI dashboards, log output.

---

## Constants
- `CITIES`: List[str] - large list of supporting cities sorted by length.
