import sqlite3
from pathlib import Path


def get_db():
    db_path = Path("data/musicalbot.db")
    return sqlite3.connect(db_path)