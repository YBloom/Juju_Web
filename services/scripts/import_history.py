import csv
import glob
import os
import sys
from datetime import datetime

# Adjust path to allow imports from project root
sys.path.append(os.getcwd())

from sqlmodel import select
from services.db.connection import session_scope
from services.hulaquan.tables import SaojuShow
from services.utils.timezone import now as timezone_now

def parse_cast(cast_raw):
    """
    Convert space-separated cast string to ' / ' separated.
    CSV format: "Role:Actor Role2:Actor2"
    DB format: "Role:Actor / Role2:Actor2"
    """
    if not cast_raw:
        return None
    # Split by space and rejoin with separator
    parts = cast_raw.split(' ')
    # Filter out empty strings just in case
    parts = [p for p in parts if p.strip()]
    return ' / '.join(parts)

def import_csv_files(data_dir):
    csv_files = glob.glob(os.path.join(data_dir, '*.csv'))
    print(f"Found {len(csv_files)} CSV files in {data_dir}")
    
    total_inserted = 0
    total_updated = 0
    total_skipped = 0
    
    with session_scope() as session:
        for file_path in csv_files:
            print(f"Processing {file_path}...")
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Ensure headers match expected: 时间,城市,音乐剧,卡司,剧院
                # DictReader uses first row as header.
                
                for row in reader:
                    time_str = row.get('时间')
                    city = row.get('城市')
                    musical_name = row.get('音乐剧')
                    cast_raw = row.get('卡司')
                    theatre = row.get('剧院')
                    
                    if not time_str or not musical_name or not city:
                        continue
                        
                    try:
                        # Parse date: 2023-01-01 11:00
                        date_val = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    except ValueError as e:
                        print(f"Skipping invalid date {time_str}: {e}")
                        continue
                        
                    cast_str = parse_cast(cast_raw)
                    
                    # Check existence
                    existing = session.get(SaojuShow, (date_val, musical_name, city))
                    
                    if existing:
                        # Optional: Update if cast is better? 
                        # For now, let's assume if it exists, we stick with what we have 
                        # unless it's clearly empty vs populated.
                        # Actually, user said historical data is missing, so likely it doesn't exist.
                        # But if it does, and source is not CSV, maybe keep it?
                        # Let's just update if cast_str is missing in DB but present in CSV.
                        
                        updated = False
                        if not existing.cast_str and cast_str:
                            existing.cast_str = cast_str
                            updated = True
                        if not existing.theatre and theatre:
                            existing.theatre = theatre
                            updated = True
                            
                        if updated:
                            session.add(existing)
                            total_updated += 1
                        else:
                            total_skipped += 1
                    else:
                        # Create new
                        new_show = SaojuShow(
                            date=date_val,
                            musical_name=musical_name,
                            city=city,
                            cast_str=cast_str,
                            theatre=theatre,
                            source="csv_history",
                            updated_at=timezone_now()
                        )
                        session.add(new_show)
                        total_inserted += 1
            
            # Commit per file or check point roughly?
            # session_scope auto commits at end.
            # To avoid huge transaction, maybe commit occasionally? 
            # But context manager commits at exit. 
            # Let's trust session to handle it or we can flush.
            session.flush() 

    print("Import finished.")
    print(f"Inserted: {total_inserted}")
    print(f"Updated: {total_updated}")
    print(f"Skipped: {total_skipped}")

if __name__ == "__main__":
    # Assuming run from project root: python services/scripts/import_history.py
    data_dir = os.path.join(os.getcwd(), 'data', 'history_data')
    import_csv_files(data_dir)
