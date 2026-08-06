import sqlite3
from config.settings import settings

conn = sqlite3.connect(str(settings.DATABASE_PATH_PATH))
conn.row_factory = sqlite3.Row
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print(f'Table: {t["name"]}')
    cols = conn.execute(f'PRAGMA table_info({t["name"]})').fetchall()
    for c in cols:
        print(f'  {c["name"]} ({c["type"]})')
    print()