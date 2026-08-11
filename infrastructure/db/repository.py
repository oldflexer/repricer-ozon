"""
Базовый класс репозитория SQLite и CRUD-методы.
Собирает все миксины для получения итогового класса.
"""

import sqlite3
from pathlib import Path

from config.settings import settings
from core.entities import ProductInfo, StrategyInterval
from core.repository import IProductRepository

from .analytics import AnalyticsMixin

# Импортируем миксины
from .history import HistoryMixin
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
        """Создаёт таблицы, если они не существуют (для тестов и простого запуска без миграций).

        DDL читается из SQL-файлов в migrations/sql/ — single source of truth.
        """
        sql_dir = Path(__file__).resolve().parent.parent.parent / "migrations" / "sql"

        # Выполняем миграцию 001
        sql_001 = sql_dir / "001_initial_schema.sql"
        if sql_001.exists():
            with self._get_connection() as conn, sql_001.open(encoding="utf-8") as f:
                conn.executescript(f.read())

        # Выполняем миграцию 002
        sql_002 = sql_dir / "002_add_daily_aggregates_and_logs.sql"
        if sql_002.exists():
            with self._get_connection() as conn, sql_002.open(encoding="utf-8") as f:
                conn.executescript(f.read())

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

    def get_all_products(self) -> list[ProductInfo]:
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

    def get_strategies(self, sku: str) -> list[StrategyInterval]:
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

    def set_strategies(self, sku: str, intervals: list[StrategyInterval]) -> bool:
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

