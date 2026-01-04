
# Simulation Script for Price Sorting
# Mimicking app.js logic

data = [
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show A", "price": 99},
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show A", "price": 199},
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show A", "price": "99"},
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show A", "price": "199"},
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show A", "price": "¥99"},
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show A", "price": "¥199"},
    {"city": "Shanghai", "session_time": "2024-01-01T14:30:00", "title": "Show B", "price": 100}
]

import re

def get_price(p):
    if isinstance(p, (int, float)):
        return p
    if not p:
        return 0
    # mimics String(p).replace(/[^\d.]/g, '')
    s = str(p)
    s_clean = re.sub(r'[^\d.]', '', s)
    try:
        return float(s_clean)
    except:
        return 0

city_counts = {"Shanghai": 100}

def sort_key(item):
    # Just mocking the comparison logic structure
    # In JS sort((a,b) => ...)
    # 1. Time (assume equal)
    # 2. City Count (desc) (assume equal)
    # 3. City Name (asc) (assume equal)
    # 4. Title (asc)
    # 5. Price (asc)
    return (item['title'], get_price(item['price']))

sorted_data = sorted(data, key=lambda x: (x['title'], get_price(x['price'])))

print("--- Sorted Results ---")
for item in sorted_data:
    print(f"{item['title']} - {item['price']} (Parsed: {get_price(item['price'])})")
