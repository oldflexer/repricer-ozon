"""
Базовый класс репозитория SQLite и CRUD-методы.
Собирает все миксины для получения итогового класса.
"""

import sqlite3
from pathlib import Path
from typing import List

from config.settings import settings
from core.entities import ProductInfo, StrategyInterval
from core.repository import IProductRepository

# Импортируем миксины
from .history import HistoryMixin
from .analytics import AnalyticsMixin
from .maintenance import MaintenanceMixin


class SQLiteRepository(
    HistoryMixin,
    AnalyticsMixin,
    MaintenanceMixin,
    IProductRepository,
):
    """
    Реализация репозитория на основе SQLite.

    Использует PRAGMA busy_timeout и WAL-режим для конкурентного доступа.
    """

    def __init__(self, db_path: Path = settings.DATABASE_PATH_PATH) -> None:
        """
        Инициализирует репозиторий, создавая директорию для БД при необходимости.

        Args:
            db_path: Путь к файлу SQLite (по умолчанию из настроек).
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Создаёт таблицы, если они не существуют (для тестов и простого запуска без миграций)."""
        with self._get_connection() as conn:
            # Таблица товаров
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product (
                    product_id INTEGER PRIMARY KEY,
                    offer_id TEXT,
                    sku TEXT UNIQUE,
                    product_name TEXT,
                    rip REAL,
                    net_price REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    real_customer_price REAL
                )
            """)
            # Таблица стратегий (справочник)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strategy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT UNIQUE
                )
            """)
            # Начальные данные стратегий
            conn.execute("INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (1, 'Ниже')")
            conn.execute("INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (2, 'Выше')")
            conn.execute("INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (3, 'Равная')")
            # Связь товаров со стратегиями (интервалы)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_strategy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    interval_start TEXT,
                    interval_stop TEXT,
                    strategy_id INTEGER,
                    strategy_percent REAL,
                    FOREIGN KEY(product_id) REFERENCES product(product_id),
                    FOREIGN KEY(strategy_id) REFERENCES strategy(id)
                )
            """)
            # История цен
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    min_price REAL,
                    price REAL,
                    old_price REAL,
                    marketing_seller_price REAL,
                    net_price REAL,
                    external_index_data_price REAL,
                    external_index_data_index REAL,
                    ozon_index_data_price REAL,
                    ozon_index_data_index REAL,
                    self_marketplaces_index_data_price REAL,
                    self_marketplaces_index_data_index REAL,
                    result_target_price REAL,
                    discount_coef REAL,
                    marginality REAL,
                    sales_percent_fbs REAL,
                    acquiring REAL,
                    fbs_first_mile_min_amount REAL,
                    fbs_first_mile_max_amount REAL,
                    fbs_direct_flow_trans_min_amount REAL,
                    fbs_direct_flow_trans_max_amount REAL,
                    fbs_deliv_to_customer_amount REAL,
                    log_details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    real_price REAL,
                    fbo_deliv_to_customer_amount REAL,
                    fbo_direct_flow_trans_min_amount REAL,
                    fbo_direct_flow_trans_max_amount REAL,
                    fbo_return_flow_amount REAL,
                    fbs_return_flow_amount REAL,
                    FOREIGN KEY(product_id) REFERENCES product(product_id)
                )
            """)
            # История маржинальности
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_marginality_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    marginality REAL,
                    marginality_week REAL,
                    marginality_month REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(product_id) REFERENCES product(product_id)
                )
            """)
            # Служебная таблица
            conn.execute("""
                CREATE TABLE IF NOT EXISTS maintenance (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("INSERT OR IGNORE INTO maintenance (key, value) VALUES ('last_cleanup', '1970-01-01 00:00:00')")
            # Индексы
            conn.execute("CREATE INDEX IF NOT EXISTS idx_product_sku ON product(sku)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_product_timestamp ON product_price_history(product_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_marginality_product_timestamp ON product_marginality_history(product_id, timestamp)")
            # Таблица дневных агрегатов (миграция 002)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_price_daily (
                    product_id INTEGER NOT NULL,
                    date DATE NOT NULL,
                    avg_price REAL,
                    avg_marginality REAL,
                    min_price REAL,
                    max_price REAL,
                    updates_count INTEGER,
                    PRIMARY KEY (product_id, date),
                    FOREIGN KEY(product_id) REFERENCES product(product_id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_product_date ON product_price_daily(product_id, date)")
            # Таблица логов расчётов (миграция 002)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_calculation_logs (
                    history_id INTEGER PRIMARY KEY,
                    log_details TEXT,
                    FOREIGN KEY(history_id) REFERENCES product_price_history(id)
                )
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Создаёт и возвращает соединение с SQLite с нужными настройками."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    # ------------------------------------------------------------------
    # Реализация методов IProductRepository (CRUD)
    # ------------------------------------------------------------------

    def get_all_products(self) -> List[ProductInfo]:
        """Возвращает список всех товаров из таблицы product."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT product_id, offer_id, sku, product_name, rip, net_price, real_customer_price
                FROM product
            """).fetchall()
            return [
                ProductInfo(
                    sku=r["sku"],
                    product_name=r["product_name"],
                    product_id=r["product_id"],
                    offer_id=r["offer_id"],
                    min_price=r["rip"] or 0.0,
                    cost_price=r["net_price"] or 0.0,
                    real_customer_price=r["real_customer_price"],
                )
                for r in rows
            ]

    def upsert_product(self, product: ProductInfo) -> bool:
        """
        Вставляет или заменяет запись о товаре.

        Args:
            product: Данные товара.

        Returns:
            True в случае успеха.
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO product
                (product_id, offer_id, sku, product_name, rip, net_price, real_customer_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product.product_id,
                    product.offer_id,
                    product.sku,
                    product.product_name,
                    product.min_price,
                    product.cost_price,
                    product.real_customer_price,
                ),
            )
            conn.commit()
            return True

    def update_real_customer_price(self, sku: str, real_price: float) -> bool:
        """
        Обновляет реальную цену покупателя для товара.

        Args:
            sku: Артикул товара.
            real_price: Новая реальная цена.

        Returns:
            True в случае успеха.
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE product
                SET real_customer_price = ?, last_updated = CURRENT_TIMESTAMP
                WHERE sku = ?
                """,
                (real_price, sku),
            )
            conn.commit()
            return True

    def get_strategies(self, sku: str) -> List[StrategyInterval]:
        """
        Возвращает интервалы стратегий для товара.

        Args:
            sku: Артикул товара.

        Returns:
            Список StrategyInterval, отсортированный по времени начала.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT ps.interval_start, ps.interval_stop, ps.strategy_id, ps.strategy_percent
                FROM product_strategy ps
                JOIN product p ON p.product_id = ps.product_id
                WHERE p.sku = ?
                ORDER BY ps.interval_start
                """,
                (sku,),
            ).fetchall()
            return [
                StrategyInterval(
                    start=r["interval_start"],
                    end=r["interval_stop"],
                    strategy_type=r["strategy_id"],
                    percent=r["strategy_percent"],
                )
                for r in rows
            ]

    def set_strategies(self, sku: str, intervals: List[StrategyInterval]) -> bool:
        """
        Сохраняет интервалы стратегий для товара (заменяет существующие).

        Args:
            sku: Артикул товара.
            intervals: Список интервалов.

        Returns:
            True в случае успеха, False если товар не найден.
        """
        with self._get_connection() as conn:
            product_id = conn.execute(
                "SELECT product_id FROM product WHERE sku = ?", (sku,)
            ).fetchone()
            if not product_id:
                return False
            pid = product_id["product_id"]

            conn.execute("DELETE FROM product_strategy WHERE product_id = ?", (pid,))
            for inv in intervals:
                conn.execute(
                    """
                    INSERT INTO product_strategy
                    (product_id, interval_start, interval_stop, strategy_id, strategy_percent)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (pid, inv.start, inv.end, inv.strategy_type, inv.percent),
                )
            conn.commit()
            return True