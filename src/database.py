import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging
from datetime import timezone

from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)


class Database:
    """Работа с SQLite базой данных репрайсера"""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_tables()

    def _ensure_db_dir(self):
        """Создаёт директорию для БД, если её нет"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Создаёт соединение с БД"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self):
        """Создаёт таблицы, если их нет"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица товаров (синхронизируется с загрузчиком)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    offer_id TEXT PRIMARY KEY,
                    product_name TEXT,
                    cost_price REAL,
                    min_price REAL,
                    current_price REAL,
                    strategy INTEGER,
                    strategy_percent REAL,
                    schedule TEXT,
                    competitor_urls TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # История цен и маржинальности
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offer_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    target_price REAL,
                    margin REAL,
                    competitor_prices TEXT,  -- JSON массив цен конкурентов
                    FOREIGN KEY (offer_id) REFERENCES products (offer_id)
                )
            ''')

            # История цен конкурентов (для детального анализа)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitor_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    offer_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    competitor_index INTEGER,
                    price REAL,
                    FOREIGN KEY (offer_id) REFERENCES products (offer_id)
                )
            ''')

            conn.commit()
        logger.debug("База данных инициализирована")

    # --- Методы для работы с товарами ---

    def upsert_product(self, product: Dict) -> bool:
        """Добавляет или обновляет информацию о товаре"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO products
                        (offer_id, product_name, cost_price, min_price, current_price,
                         strategy, strategy_percent, schedule, competitor_urls, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    product.get('offer_id'),
                    product.get('product_name'),
                    product.get('cost_price'),
                    product.get('min_price'),
                    product.get('current_price'),
                    product.get('strategy'),
                    product.get('strategy_percent'),
                    product.get('schedule'),
                    json.dumps(product.get('competitor_urls', []))
                ))
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения товара {product.get('offer_id')}: {e}")
            return False

    def get_all_products(self) -> List[Dict]:
        """Возвращает все товары из БД"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products')
            rows = cursor.fetchall()
            products = []
            for row in rows:
                product = dict(row)
                product['competitor_urls'] = json.loads(product.get('competitor_urls', '[]'))
                products.append(product)
            return products

    # --- Методы для истории цен ---

    def save_price_record(self, offer_id: str, target_price: float, margin: float,
                          competitor_prices: List[Optional[float]]):
        """Сохраняет запись о рассчитанной цене и марже"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO price_history (offer_id, target_price, margin, competitor_prices)
                    VALUES (?, ?, ?, ?)
                ''', (offer_id, target_price, margin, json.dumps(competitor_prices)))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения истории цены для {offer_id}: {e}")
            return False

    def get_average_margin(self, offer_id: str, days: int) -> Optional[float]:
        """Возвращает среднюю маржинальность за последние N дней"""
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

    def get_sales_volume(self, offer_id: str, days: int = 30) -> int:
        """
        Возвращает количество записей в истории цен за последние N дней.
        Можно использовать как прокси для объёма продаж (каждый день одна запись).
        В реальном проекте лучше брать данные из отчётов Ozon.
        """
        cutoff = datetime.now() - timedelta(days=days)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM price_history
                WHERE offer_id = ? AND timestamp >= ?
            ''', (offer_id, cutoff.isoformat()))
            row = cursor.fetchone()
            return row[0] if row else 0

    # --- Вспомогательные методы ---

    def get_last_run_time(self) -> Optional[datetime]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(timestamp) FROM price_history')
            row = cursor.fetchone()
            if row and row[0]:
                # SQLite хранит в UTC, возвращаем aware datetime
                dt = datetime.fromisoformat(row[0])
                return dt.replace(tzinfo=timezone.utc)
            return None