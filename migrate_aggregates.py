#!/usr/bin/env python3
"""
Скрипт для заполнения таблицы product_price_daily из существующих данных.
Запускать один раз после обновления схемы БД.
"""
import sys
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from infrastructure.logger import logger


def migrate_aggregates():
    db_path = settings.DATABASE_PATH_PATH
    if not db_path.exists():
        logger.error(f"База данных не найдена: {db_path}")
        return

    logger.info("Начинаем заполнение агрегатов...")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Проверяем, есть ли уже данные в таблице агрегатов
    count = conn.execute("SELECT COUNT(*) FROM product_price_daily").fetchone()[0]
    if count > 0:
        logger.warning(f"В таблице product_price_daily уже есть {count} записей. Пропускаем.")
        conn.close()
        return

    # Собираем агрегаты из истории
    query = """
        SELECT 
            product_id,
            DATE(timestamp) as date,
            AVG(real_price) as avg_price,
            AVG(marginality) as avg_marginality,
            MIN(real_price) as min_price,
            MAX(real_price) as max_price,
            COUNT(*) as updates_count
        FROM product_price_history
        WHERE real_price IS NOT NULL
        GROUP BY product_id, DATE(timestamp)
    """
    df = pd.read_sql_query(query, conn)

    if df.empty:
        logger.info("Нет данных для миграции (история пуста или real_price везде NULL).")
        conn.close()
        return

    # Вставляем в таблицу агрегатов
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO product_price_daily
            (product_id, date, avg_price, avg_marginality, min_price, max_price, updates_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row['product_id'],
            row['date'],
            row['avg_price'],
            row['avg_marginality'],
            row['min_price'],
            row['max_price'],
            row['updates_count']
        ))
    conn.commit()
    conn.close()

    logger.info(f"Агрегаты заполнены: добавлено {len(df)} записей.")


if __name__ == "__main__":
    migrate_aggregates()