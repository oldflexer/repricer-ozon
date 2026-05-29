import sqlite3
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from core.entities import ProductInfo, StrategyInterval, PricingData, PriceCalculationResult
from core.repository import IProductRepository
from config.settings import settings
from infrastructure.logger import logger


class SQLiteRepository(IProductRepository):
    # Текущая версия схемы БД (увеличивать при добавлении миграций)
    SCHEMA_VERSION = 5

    def __init__(self, db_path: Path = settings.DATABASE_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_schema_version(self, conn) -> int:
        """Возвращает текущую версию схемы БД."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] if row[0] is not None else 0

    def _apply_migrations(self, conn):
        """Применяет миграции от текущей версии до целевой."""
        current = self._get_schema_version(conn)

        if current == 0:
            logger.info("Применяем миграцию 0 -> 1: создание таблиц (если их нет)")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS product (
                    product_id INTEGER PRIMARY KEY,
                    offer_id TEXT,
                    sku TEXT UNIQUE,
                    product_name TEXT,
                    rip REAL,
                    net_price REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS strategy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT UNIQUE
                );
                INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES(1,'Ниже'), (2,'Выше'), (3,'Равная');
                CREATE TABLE IF NOT EXISTS product_strategy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER REFERENCES product(product_id),
                    interval_start TEXT,
                    interval_stop TEXT,
                    strategy_id INTEGER REFERENCES strategy(id),
                    strategy_percent REAL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS product_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER REFERENCES product(product_id),
                    min_price REAL, price REAL, old_price REAL,
                    marketing_seller_price REAL,
                    external_index_data_price REAL, external_index_data_index REAL,
                    ozon_index_data_price REAL, ozon_index_data_index REAL,
                    self_marketplaces_index_data_price REAL, self_marketplaces_index_data_index REAL,
                    result_target_price REAL, discount_coef REAL, marginality REAL,
                    sales_percent_fbs REAL, acquiring REAL,
                    fbs_first_mile_min_amount REAL, fbs_first_mile_max_amount REAL,
                    fbs_direct_flow_trans_min_amount REAL, fbs_direct_flow_trans_max_amount REAL,
                    fbs_deliv_to_customer_amount REAL,
                    log_details TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS product_marginality_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER REFERENCES product(product_id),
                    marginality REAL, marginality_week REAL, marginality_month REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (1)")
            current = self._get_schema_version(conn)

        if current == 1:
            logger.info("Применяем миграцию 1 -> 2: добавление колонки real_customer_price и real_price")
            columns_product = [row[1] for row in conn.execute("PRAGMA table_info(product)")]
            if 'real_customer_price' not in columns_product:
                conn.execute("ALTER TABLE product ADD COLUMN real_customer_price REAL")
            columns_history = [row[1] for row in conn.execute("PRAGMA table_info(product_price_history)")]
            if 'real_price' not in columns_history:
                conn.execute("ALTER TABLE product_price_history ADD COLUMN real_price REAL")
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (2)")
            current = self._get_schema_version(conn)

        if current == 2:
            logger.info("Применяем миграцию 2 -> 3: добавление индексов")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_product_sku ON product(sku)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_product_timestamp ON product_price_history(product_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_marginality_product_timestamp ON product_marginality_history(product_id, timestamp)")
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (3)")
            current = 3

        if current == 3:
            logger.info("Применяем миграцию 3 -> 4: создание таблицы maintenance")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO maintenance (key, value) VALUES ('last_cleanup', '1970-01-01 00:00:00')
            """)
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (4)")
            current = 4

        if current == 4:
            logger.info("Применяем миграцию 4 -> 5: подготовка к автоматической очистке")
            # Здесь можно добавить дополнительные индексы, если нужно
            conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (5)")
            current = 5

        if current < self.SCHEMA_VERSION:
            logger.error(f"Текущая версия {current} ниже целевой {self.SCHEMA_VERSION}, но миграций больше нет")
        elif current > self.SCHEMA_VERSION:
            logger.warning(f"Версия БД ({current}) выше целевой ({self.SCHEMA_VERSION}). Возможно, вы используете старую версию кода.")

    def _init_tables(self):
        with self._get_connection() as conn:
            self._apply_migrations(conn)

    # ------------------- Товары -------------------
    def get_all_products(self) -> List[ProductInfo]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT product_id, offer_id, sku, product_name, rip, net_price, real_customer_price
                FROM product
            """).fetchall()
            return [
                ProductInfo(
                    sku=r['sku'],
                    product_name=r['product_name'],
                    product_id=r['product_id'],
                    offer_id=r['offer_id'],
                    min_price=r['rip'] or 0.0,
                    cost_price=r['net_price'] or 0.0,
                    real_customer_price=r['real_customer_price']
                )
                for r in rows
            ]

    def upsert_product(self, product: ProductInfo) -> bool:
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO product (product_id, offer_id, sku, product_name, rip, net_price, real_customer_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product.product_id, product.offer_id, product.sku, product.product_name,
                  product.min_price, product.cost_price, product.real_customer_price))
            conn.commit()
            return True

    def update_real_customer_price(self, sku: str, real_price: float) -> bool:
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE product SET real_customer_price = ?, last_updated = CURRENT_TIMESTAMP
                WHERE sku = ?
            """, (real_price, sku))
            conn.commit()
            return True

    # ------------------- Стратегии -------------------
    def get_strategies(self, sku: str) -> List[StrategyInterval]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT ps.interval_start, ps.interval_stop, ps.strategy_id, ps.strategy_percent
                FROM product_strategy ps
                JOIN product p ON p.product_id = ps.product_id
                WHERE p.sku = ?
                ORDER BY ps.interval_start
            """, (sku,)).fetchall()
            return [
                StrategyInterval(
                    start=r['interval_start'],
                    end=r['interval_stop'],
                    strategy_type=r['strategy_id'],
                    percent=r['strategy_percent']
                )
                for r in rows
            ]

    def set_strategies(self, sku: str, intervals: List[StrategyInterval]) -> bool:
        with self._get_connection() as conn:
            product_id = conn.execute("SELECT product_id FROM product WHERE sku=?", (sku,)).fetchone()
            if not product_id:
                return False
            pid = product_id['product_id']
            conn.execute("DELETE FROM product_strategy WHERE product_id=?", (pid,))
            for inv in intervals:
                conn.execute("""
                    INSERT INTO product_strategy (product_id, interval_start, interval_stop, strategy_id, strategy_percent)
                    VALUES (?, ?, ?, ?, ?)
                """, (pid, inv.start, inv.end, inv.strategy_type, inv.percent))
            conn.commit()
            return True

    # ------------------- История цен -------------------
    def save_price_history(self, sku: str, pricing: PricingData, result: PriceCalculationResult, real_price: Optional[float] = None) -> bool:
        with self._get_connection() as conn:
            product_id = conn.execute("SELECT product_id FROM product WHERE sku=?", (sku,)).fetchone()
            if not product_id:
                return False
            pid = product_id['product_id']
            conn.execute("""
                INSERT INTO product_price_history (
                    product_id, min_price, price, old_price,
                    marketing_seller_price,
                    external_index_data_price, external_index_data_index,
                    ozon_index_data_price, ozon_index_data_index,
                    self_marketplaces_index_data_price, self_marketplaces_index_data_index,
                    result_target_price, discount_coef, marginality,
                    sales_percent_fbs, acquiring,
                    fbs_first_mile_min_amount, fbs_first_mile_max_amount,
                    fbs_direct_flow_trans_min_amount, fbs_direct_flow_trans_max_amount,
                    fbs_deliv_to_customer_amount,
                    real_price, log_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pid,
                pricing.min_price,
                pricing.price,
                pricing.old_price,
                pricing.marketing_seller_price,
                pricing.external_index_data_price,
                pricing.external_index_data_index,
                pricing.ozon_index_data_price,
                pricing.ozon_index_data_index,
                pricing.self_marketplaces_index_data_price,
                pricing.self_marketplaces_index_data_index,
                result.result_target_price,
                result.log_details.get('discount_coef', 0),
                result.marginality,
                pricing.sales_percent_fbs,
                pricing.acquiring,
                pricing.fbs_first_mile_min_amount,
                pricing.fbs_first_mile_max_amount,
                pricing.fbs_direct_flow_trans_min_amount,
                pricing.fbs_direct_flow_trans_max_amount,
                pricing.fbs_deliv_to_customer_amount,
                real_price,
                json.dumps(result.log_details, ensure_ascii=False)
            ))
            conn.commit()
            return True

    def get_price_history(self, sku: str) -> List[dict]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    ph.timestamp, 
                    ph.result_target_price,
                    ph.discount_coef,
                    ph.real_price,
                    ph.marginality
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE p.sku = ?
                ORDER BY ph.timestamp
            """, (sku,)).fetchall()
            result = []
            for row in rows:
                if row['real_price'] is not None:
                    customer_price = row['real_price']
                else:
                    customer_price = row['result_target_price'] * row['discount_coef']
                result.append({
                    "timestamp": row["timestamp"],
                    "customer_price": customer_price,
                    "marginality": row["marginality"]
                })
            return result

    # ------------------- Маржинальность -------------------
    def save_marginality(self, sku: str, marginality: float,
                         marginality_week: float, marginality_month: float) -> bool:
        with self._get_connection() as conn:
            product_id = conn.execute("SELECT product_id FROM product WHERE sku=?", (sku,)).fetchone()
            if not product_id:
                return False
            pid = product_id['product_id']
            conn.execute("""
                INSERT INTO product_marginality_history (product_id, marginality, marginality_week, marginality_month)
                VALUES (?, ?, ?, ?)
            """, (pid, marginality, marginality_week, marginality_month))
            conn.commit()
            return True

    def get_average_marginality(self, sku: str, days: int) -> Optional[float]:
        with self._get_connection() as conn:
            product_id = conn.execute("SELECT product_id FROM product WHERE sku=?", (sku,)).fetchone()
            if not product_id:
                return None
            pid = product_id['product_id']
            cutoff = datetime.now() - timedelta(days=days)
            row = conn.execute("""
                SELECT AVG(marginality) FROM product_marginality_history
                WHERE product_id=? AND timestamp >= ?
            """, (pid, cutoff.isoformat())).fetchone()
            return row[0] if row and row[0] else None

    def get_last_run_time(self) -> Optional[datetime]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT MAX(timestamp) FROM product_price_history").fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
            return None

    # ------------------- Обслуживание -------------------
    def delete_old_records(self, days: int) -> int:
        """Ручная очистка записей старше указанного количества дней."""
        with self._get_connection() as conn:
            cutoff = datetime.now() - timedelta(days=days)
            deleted_price = conn.execute(
                "DELETE FROM product_price_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_margin = conn.execute(
                "DELETE FROM product_marginality_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            conn.commit()
            return deleted_price + deleted_margin

    # ---------- Автоматическая очистка (старше 3 месяцев) ----------
    def delete_records_older_than(self, months: int = 3) -> int:
        """Удаляет записи старше указанного числа месяцев."""
        with self._get_connection() as conn:
            cutoff = datetime.now() - timedelta(days=months * 30)
            deleted_price = conn.execute(
                "DELETE FROM product_price_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_margin = conn.execute(
                "DELETE FROM product_marginality_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            conn.commit()
            logger.info(f"Очистка БД: удалено {deleted_price} записей истории цен и {deleted_margin} записей маржинальности старше {months} месяцев")
            return deleted_price + deleted_margin

    def get_last_cleanup_date(self) -> Optional[datetime]:
        """Возвращает дату последней автоматической очистки в UTC."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM maintenance WHERE key = 'last_cleanup'").fetchone()
            if row and row['value']:
                try:
                    dt = datetime.fromisoformat(row['value'])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except:
                    return None
            return None

    def set_last_cleanup_date(self, dt: datetime):
        """Сохраняет дату последней очистки (если dt naive, то добавляет UTC)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE maintenance SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_cleanup'",
                (dt.isoformat(),)
            )
            conn.commit()

    def auto_cleanup_if_needed(self, months: int = 3, days_threshold: int = 1) -> int:
        """
        Автоматически запускает очистку, если с последней очистки прошло больше days_threshold дней.
        Возвращает количество удалённых записей (0, если очистка не производилась).
        """
        last = self.get_last_cleanup_date()
        if last is None:
            # Никогда не чистили – делаем сейчас
            deleted = self.delete_records_older_than(months)
            self.set_last_cleanup_date(datetime.now())
            return deleted
        else:
            if (datetime.now() - last).days >= days_threshold:
                deleted = self.delete_records_older_than(months)
                self.set_last_cleanup_date(datetime.now())
                return deleted
        return 0