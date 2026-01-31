import sys
import os
# Adjust path to project root
sys.path.append(os.path.abspath("/Users/yaobii/Developer/MY PROJECTS/MusicalBot"))

from services.db.connection import session_scope
from services.hulaquan.tables import SaojuShow
from sqlmodel import select, func

def check_dates():
    with session_scope() as session:
        min_date = session.exec(select(func.min(SaojuShow.date))).first()
        max_date = session.exec(select(func.max(SaojuShow.date))).first()
        count = session.exec(select(func.count(SaojuShow.date))).first()
        print(f"Total shows: {count}")
        print(f"Earliest date: {min_date}")
        print(f"Latest date: {max_date}")

if __name__ == "__main__":
    check_dates()
