import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    """Работа с SQLite базой данных репрайсера (новая схема)"""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_tables()

    def _ensure_db_dir(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица товаров
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    offer_id TEXT PRIMARY KEY,
                    product_name TEXT,
                    cost_price REAL,
                    min_price REAL,
                    current_price REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Стратегии (интервалы)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS product_strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offer_id TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    strategy_type INTEGER NOT NULL,
                    percent REAL DEFAULT 0,
                    FOREIGN KEY (offer_id) REFERENCES products (offer_id) ON DELETE CASCADE
                )
            ''')

            # Конкуренты
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    product_name TEXT,
                    shop_name TEXT
                )
            ''')

            # Связь товар-конкурент
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS product_competitors (
                    offer_id TEXT NOT NULL,
                    competitor_id INTEGER NOT NULL,
                    competitor_index INTEGER,
                    PRIMARY KEY (offer_id, competitor_id),
                    FOREIGN KEY (offer_id) REFERENCES products (offer_id) ON DELETE CASCADE,
                    FOREIGN KEY (competitor_id) REFERENCES competitors (id) ON DELETE CASCADE
                )
            ''')

            # История цен товара
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offer_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    target_price REAL,
                    margin REAL,
                    FOREIGN KEY (offer_id) REFERENCES products (offer_id)
                )
            ''')

            # История цен конкурентов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitor_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor_id INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    price REAL,
                    FOREIGN KEY (competitor_id) REFERENCES competitors (id)
                )
            ''')

            conn.commit()
        logger.debug("База данных инициализирована (новая схема)")

    # --- Товары ---
    def upsert_product(self, product: Dict[str, Any]) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO products (offer_id, product_name, cost_price, min_price, current_price)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    product.get('offer_id'),
                    product.get('product_name'),
                    product.get('cost_price'),
                    product.get('min_price'),
                    product.get('current_price')
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения товара {product.get('offer_id')}: {e}")
            return False

    def get_all_products(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Стратегии ---
    def set_strategies(self, offer_id: str, intervals: List[Dict]) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM product_strategies WHERE offer_id = ?', (offer_id,))
                for inv in intervals:
                    cursor.execute('''
                        INSERT INTO product_strategies (offer_id, start_time, end_time, strategy_type, percent)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        offer_id,
                        inv['start'],
                        inv['end'],
                        inv['strategy'],
                        inv['percent']
                    ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения стратегий для {offer_id}: {e}")
            return False

    def get_strategies(self, offer_id: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT start_time, end_time, strategy_type, percent
                FROM product_strategies
                WHERE offer_id = ?
                ORDER BY start_time
            ''', (offer_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Конкуренты ---
    def get_or_create_competitor(self, url: str, product_name: Optional[str] = None,
                                 shop_name: Optional[str] = None) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, product_name, shop_name FROM competitors WHERE url = ?', (url,))
            row = cursor.fetchone()
            if row:
                if product_name or shop_name:
                    upd_name = product_name if product_name else row['product_name']
                    upd_shop = shop_name if shop_name else row['shop_name']
                    cursor.execute('UPDATE competitors SET product_name = ?, shop_name = ? WHERE id = ?',
                                   (upd_name, upd_shop, row['id']))
                    conn.commit()
                return row['id']
            else:
                cursor.execute('''
                    INSERT INTO competitors (url, product_name, shop_name)
                    VALUES (?, ?, ?)
                ''', (url, product_name, shop_name))
                conn.commit()
                new_id = cursor.lastrowid
                if new_id is None:
                    raise RuntimeError("Не удалось получить lastrowid после INSERT")
                return new_id

    def link_product_competitor(self, offer_id: str, competitor_id: int, index: int) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO product_competitors (offer_id, competitor_id, competitor_index)
                VALUES (?, ?, ?)
            ''', (offer_id, competitor_id, index))
            conn.commit()

    def get_competitors_for_product(self, offer_id: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.id, c.url, c.product_name, c.shop_name, pc.competitor_index
                FROM competitors c
                JOIN product_competitors pc ON c.id = pc.competitor_id
                WHERE pc.offer_id = ?
                ORDER BY pc.competitor_index
            ''', (offer_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_all_competitors_with_details(self) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.id, c.url, c.product_name, c.shop_name,
                       GROUP_CONCAT(DISTINCT p.offer_id) as offer_ids,
                       GROUP_CONCAT(DISTINCT p.product_name) as product_names
                FROM competitors c
                LEFT JOIN product_competitors pc ON c.id = pc.competitor_id
                LEFT JOIN products p ON pc.offer_id = p.offer_id
                GROUP BY c.id
                ORDER BY c.shop_name, c.product_name
            ''')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- История цен товара ---
    def save_price_record(self, offer_id: str, target_price: float, margin: float) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO price_history (offer_id, target_price, margin)
                    VALUES (?, ?, ?)
                ''', (offer_id, target_price, margin))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения истории цены для {offer_id}: {e}")
            return False

    def get_average_margin(self, offer_id: str, days: int) -> Optional[float]:
        cutoff = datetime.now() - timedelta(days=days)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT AVG(margin) FROM price_history
                WHERE offer_id = ? AND timestamp >= ?
            ''', (offer_id, cutoff.isoformat()))
            row = cursor.fetchone()
            if row and row[0] is not None:
                return round(row[0], 2)
            return None

    def get_price_history(self, offer_id: str) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, target_price, margin
                FROM price_history
                WHERE offer_id = ?
                ORDER BY timestamp ASC
            ''', (offer_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- История цен конкурентов ---
    def save_competitor_price(self, competitor_id: int, price: float) -> bool:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO competitor_price_history (competitor_id, price)
                    VALUES (?, ?)
                ''', (competitor_id, price))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения цены конкурента {competitor_id}: {e}")
            return False

    def get_competitor_price_history(self, competitor_id: int) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, price
                FROM competitor_price_history
                WHERE competitor_id = ?
                ORDER BY timestamp ASC
            ''', (competitor_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        
    def delete_old_records(self, days: int = 7) -> int:
        """Удаляет записи из price_history и competitor_price_history старше указанного количества дней."""
        cutoff = datetime.now() - timedelta(days=days)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM price_history WHERE timestamp < ?', (cutoff.isoformat(),))
            deleted_price = cursor.rowcount
            cursor.execute('DELETE FROM competitor_price_history WHERE timestamp < ?', (cutoff.isoformat(),))
            deleted_comp = cursor.rowcount
            conn.commit()
            total = deleted_price + deleted_comp
            logger.info(f"Удалено старых записей: {total} (price_history: {deleted_price}, competitor_price: {deleted_comp})")
            return total

    # --- Вспомогательные методы ---
    def get_last_run_time(self) -> Optional[datetime]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(timestamp) FROM price_history')
            row = cursor.fetchone()
            if row and row[0]:
                dt = datetime.fromisoformat(row[0])
                return dt.replace(tzinfo=timezone.utc)
            return None