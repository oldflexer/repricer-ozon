# show_schema.py
import sqlite3
from config.settings import settings

db_path = settings.DATABASE_PATH_PATH
print(f"База данных: {db_path}\n")

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 1. Список всех таблиц
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print("Таблицы:", ", ".join(tables), "\n")

# 2. Для каждой таблицы – схема
for table in tables:
    print(f"--- {table} ---")
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    for col in columns:
        cid, name, col_type, notnull, default, pk = col
        print(f"  {name} {col_type}" + (" PRIMARY KEY" if pk else "") + 
              (" NOT NULL" if notnull else "") +
              (f" DEFAULT {default}" if default else ""))
    # Индексы для таблицы
    cursor.execute(f"PRAGMA index_list({table})")
    indexes = cursor.fetchall()
    for idx in indexes:
        idx_name = idx[1]
        print(f"  Индекс: {idx_name} (unique={idx[2]})")
    print()

conn.close()