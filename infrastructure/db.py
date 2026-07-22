import subprocess
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from core.entities import ProductInfo, StrategyInterval, PricingData, PriceCalculationResult
from core.repository import IProductRepository
from config.settings import settings
from infrastructure.logger import logger


class SQLiteRepository(IProductRepository):
    def __init__(self, db_path: Path = settings.DATABASE_PATH_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_migrations()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_migrations(self):
        """
        Проверяет состояние миграций и применяет их безопасно.
        - Если есть alembic_version → ничего не делаем.
        - Если есть schema_version=6 → выполняем автоматический переход на Alembic 002.
        - Если есть schema_version<6 → пробуем upgrade (маловероятно).
        - Если ничего нет → выполняем upgrade head (новая БД).
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Проверяем alembic_version
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
            if cursor.fetchone() is not None:
                conn.close()
                logger.info("Alembic уже инициализирован.")
                return

            # Проверяем schema_version
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
            if cursor.fetchone() is not None:
                cursor.execute("SELECT MAX(version) FROM schema_version")
                row = cursor.fetchone()
                ver = int(row[0]) if row and row[0] is not None else 0
                conn.close()

                if ver == 6:
                    # Целевая версия для автоматического перехода
                    logger.info("Обнаружена БД с schema_version=6, выполняем автоматический переход на Alembic 002.")
                    self._migrate_from_schema_version_6()
                    return
                elif ver > 6:
                    # Это может быть версия 7, но без alembic_version (если что-то пошло не так)
                    # Просто зафиксируем как 002
                    logger.warning(f"Обнаружена БД с schema_version={ver}, фиксируем как Alembic 002.")
                    self._stamp_migration("002")
                    return
                else:
                    # Более старые версии (0-5) – пробуем upgrade
                    logger.warning(f"Обнаружена БД с schema_version={ver}, пробуем выполнить upgrade head.")
                    self._run_upgrade()
                    return

            conn.close()
            # Новая БД (нет ни alembic_version, ни schema_version)
            logger.info("Новая БД, выполняем все миграции.")
            self._run_upgrade()

        except sqlite3.Error as e:
            logger.error(f"Ошибка SQLite: {e}")
            raise
        except Exception as e:
            logger.error(f"Ошибка при проверке миграций: {e}")
            raise

    def _migrate_from_schema_version_6(self):
        """
        Выполняет переход из schema_version=6 в Alembic версии 002.
        Создаёт таблицы агрегатов и логов, заполняет агрегаты, фиксирует версию.
        """
        logger.info("Начинаем миграцию из schema_version=6...")

        # 1. Создаём недостающие таблицы (если их нет)
        with self._get_connection() as conn:
            # Таблица дневных агрегатов
            conn.execute("""
                CREATE TABLE IF NOT EXISTS product_price_daily (
                    product_id INTEGER REFERENCES product(product_id),
                    date DATE,
                    avg_price REAL,
                    avg_marginality REAL,
                    min_price REAL,
                    max_price REAL,
                    updates_count INTEGER,
                    PRIMARY KEY (product_id, date)
                )
            """)
            # Таблица для вынесенных логов
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_calculation_logs (
                    history_id INTEGER PRIMARY KEY REFERENCES product_price_history(id),
                    log_details TEXT
                )
            """)
            # Индексы
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON product_price_history(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_product_marginality ON product_price_history(product_id, marginality)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_product_date ON product_price_daily(product_id, date)")
            conn.commit()

        logger.info("Таблицы и индексы созданы (если отсутствовали).")

        # 2. Заполняем агрегаты из истории (если есть данные)
        self._fill_daily_aggregates()

        # 3. Фиксируем Alembic версию 002
        self._stamp_migration("002")

        # 4. Удаляем старую таблицу schema_version (опционально)
        try:
            with self._get_connection() as conn:
                conn.execute("DROP TABLE schema_version")
                conn.commit()
                logger.info("Таблица schema_version удалена.")
        except Exception as e:
            logger.warning(f"Не удалось удалить schema_version: {e}")

        logger.info("Переход на Alembic 002 завершён.")

    def _fill_daily_aggregates(self):
        """Заполняет таблицу product_price_daily из существующей истории."""
        try:
            # Импортируем migrate_aggregates, чтобы использовать ту же логику
            from migrate_aggregates import migrate_aggregates
            migrate_aggregates()
        except ImportError:
            # Если скрипт не найден, выполняем SQL-запрос напрямую (повторяем логику)
            logger.warning("Скрипт migrate_aggregates не найден, выполняем SQL-запрос напрямую.")
            with self._get_connection() as conn:
                # Проверяем, есть ли уже данные в агрегатах
                count = conn.execute("SELECT COUNT(*) FROM product_price_daily").fetchone()[0]
                if count > 0:
                    logger.info("В таблице product_price_daily уже есть данные, пропускаем.")
                    return

                query = """
                    INSERT OR REPLACE INTO product_price_daily (product_id, date, avg_price, avg_marginality, min_price, max_price, updates_count)
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
                conn.execute(query)
                conn.commit()
                logger.info("Агрегаты заполнены напрямую.")

    def _run_upgrade(self):
        """Запускает alembic upgrade head."""
        root_dir = Path(__file__).resolve().parent.parent
        try:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                logger.error(f"Ошибка выполнения миграций: {result.stderr}")
                raise RuntimeError(f"Не удалось применить миграции: {result.stderr}")
            logger.info("Миграции успешно применены.")
        except Exception as e:
            logger.error(f"Не удалось запустить alembic: {e}")
            raise

    def _stamp_migration(self, revision: str):
        """Выполняет alembic stamp <revision> для существующей БД."""
        root_dir = Path(__file__).resolve().parent.parent
        try:
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "stamp", revision],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                logger.error(f"Ошибка stamping миграции {revision}: {result.stderr}")
                raise RuntimeError(f"Не удалось зафиксировать версию {revision}: {result.stderr}")
            logger.info(f"БД зафиксирована как версия {revision}.")
        except Exception as e:
            logger.error(f"Не удалось запустить alembic stamp: {e}")
            raise

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

    def save_price_history(self, sku: str, pricing: PricingData, result: PriceCalculationResult, real_price: Optional[float] = None) -> bool:
        with self._get_connection() as conn:
            product_id = conn.execute("SELECT product_id FROM product WHERE sku=?", (sku,)).fetchone()
            if not product_id:
                return False
            pid = product_id['product_id']
            log_details_json = json.dumps(result.log_details, ensure_ascii=False)

            cursor = conn.execute("""
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
                    fbo_deliv_to_customer_amount, fbo_direct_flow_trans_min_amount,
                    fbo_direct_flow_trans_max_amount, real_price, log_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                pricing.fbo_deliv_to_customer_amount,
                pricing.fbo_direct_flow_trans_min_amount,
                pricing.fbo_direct_flow_trans_max_amount,
                real_price,
                None  # log_details сохраняем отдельно
            ))
            history_id = cursor.lastrowid

            if log_details_json:
                conn.execute("""
                    INSERT INTO price_calculation_logs (history_id, log_details)
                    VALUES (?, ?)
                """, (history_id, log_details_json))

            conn.commit()
            return True

    def save_daily_aggregates(self, sku: str, pricing: PricingData, result: PriceCalculationResult, real_price: Optional[float] = None):
        today = datetime.now(timezone.utc).date()
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT avg_price, avg_marginality, min_price, max_price, updates_count
                FROM product_price_daily
                WHERE product_id = (SELECT product_id FROM product WHERE sku = ?) AND date = ?
            """, (sku, today.isoformat())).fetchone()

            price_val = real_price if real_price is not None else result.result_target_price * result.log_details.get('discount_coef', 1.0)
            margin_val = result.marginality

            if row:
                avg_price = (row['avg_price'] * row['updates_count'] + price_val) / (row['updates_count'] + 1)
                avg_marginality = (row['avg_marginality'] * row['updates_count'] + margin_val) / (row['updates_count'] + 1)
                min_price = min(row['min_price'], price_val)
                max_price = max(row['max_price'], price_val)
                updates_count = row['updates_count'] + 1
                conn.execute("""
                    UPDATE product_price_daily
                    SET avg_price = ?, avg_marginality = ?, min_price = ?, max_price = ?, updates_count = ?
                    WHERE product_id = (SELECT product_id FROM product WHERE sku = ?) AND date = ?
                """, (avg_price, avg_marginality, min_price, max_price, updates_count, sku, today.isoformat()))
            else:
                conn.execute("""
                    INSERT INTO product_price_daily (product_id, date, avg_price, avg_marginality, min_price, max_price, updates_count)
                    VALUES ((SELECT product_id FROM product WHERE sku = ?), ?, ?, ?, ?, ?, ?)
                """, (sku, today.isoformat(), price_val, margin_val, price_val, price_val, 1))
            conn.commit()

    def get_daily_trends_aggregated(self, days: int = 7) -> pd.DataFrame:
        with self._get_connection() as conn:
            query = """
                SELECT 
                    date as day,
                    AVG(avg_price) as avg_price,
                    AVG(avg_marginality) as avg_margin
                FROM product_price_daily
                WHERE date >= date('now', ? || ' days')
                GROUP BY date
                ORDER BY date
            """
            return pd.read_sql_query(query, conn, params=(-days,))

    def get_daily_trends(self, days: int = 7) -> pd.DataFrame:
        df = self.get_daily_trends_aggregated(days)
        if df.empty:
            with self._get_connection() as conn:
                query = """
                    SELECT 
                        DATE(ph.timestamp) as day,
                        AVG(ph.result_target_price * ph.discount_coef) as avg_price,
                        AVG(ph.marginality) as avg_margin
                    FROM product_price_history ph
                    WHERE ph.timestamp >= datetime('now', ? || ' days')
                    GROUP BY day
                    ORDER BY day
                """
                return pd.read_sql_query(query, conn, params=(-days,))
        return df

    def get_daily_deviation(self, days: int = 30) -> pd.DataFrame:
        with self._get_connection() as conn:
            query = """
                SELECT 
                    DATE(ph.timestamp) as day,
                    AVG( (ph.result_target_price * ph.discount_coef) / NULLIF(ph.ozon_index_data_price, 0) ) as avg_ratio
                FROM product_price_history ph
                WHERE ph.ozon_index_data_price > 0
                AND ph.timestamp >= datetime('now', ? || ' days')
                GROUP BY day
                ORDER BY day
            """
            return pd.read_sql_query(query, conn, params=(-days,))

    # ---------- Остальные методы ----------
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

    def get_strategy_roi(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            query = """
                SELECT 
                    s.strategy_name,
                    AVG( ph.result_target_price - (
                        p.net_price + 
                        (ph.result_target_price * ph.sales_percent_fbs / 100) +
                        (ph.fbs_first_mile_min_amount + ph.fbs_first_mile_max_amount)/2 +
                        (ph.fbs_direct_flow_trans_min_amount + ph.fbs_direct_flow_trans_max_amount)/2 +
                        ph.fbs_deliv_to_customer_amount
                    ) ) as avg_abs_profit,
                    AVG(ph.marginality) as avg_marginality,
                    COUNT(*) as updates_count
                FROM product_price_history ph
                JOIN product p ON ph.product_id = p.product_id
                JOIN product_strategy ps ON ph.product_id = ps.product_id
                JOIN strategy s ON ps.strategy_id = s.id
                WHERE ph.timestamp >= datetime('now', '-30 days')
                GROUP BY s.id
            """
            return pd.read_sql_query(query, conn)

    def get_ozon_index_vs_price(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            query = """
                SELECT 
                    p.sku,
                    p.product_name,
                    ph.ozon_index_data_price,
                    (ph.result_target_price * ph.discount_coef) as real_price,
                    ph.marginality,
                    ph.ozon_index_data_index
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                AND ph.ozon_index_data_price > 0
                ORDER BY ph.ozon_index_data_price
            """
            return pd.read_sql_query(query, conn)

    def get_kpi_metrics(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            today_margin = conn.execute("""
                SELECT AVG(marginality) FROM product_price_history
                WHERE timestamp >= datetime('now', '-1 day')
            """).fetchone()[0]
            yesterday_margin = conn.execute("""
                SELECT AVG(marginality) FROM product_price_history
                WHERE timestamp >= datetime('now', '-2 days')
                AND timestamp < datetime('now', '-1 day')
            """).fetchone()[0]
            updates_week = conn.execute("""
                SELECT COUNT(*) FROM product_price_history
                WHERE timestamp >= datetime('now', '-7 days')
            """).fetchone()[0]
            unprofitable = conn.execute("""
                WITH last_prices AS (
                    SELECT ph.product_id, ph.marginality,
                        ROW_NUMBER() OVER (PARTITION BY ph.product_id ORDER BY ph.timestamp DESC) as rn
                    FROM product_price_history ph
                )
                SELECT COUNT(*) FROM last_prices
                WHERE rn = 1 AND marginality < 0
            """).fetchone()[0]
            no_index = conn.execute("""
                SELECT COUNT(DISTINCT p.product_id)
                FROM product p
                JOIN product_price_history ph ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = p.product_id
                )
                AND (ph.ozon_index_data_price = 0 OR ph.ozon_index_data_price IS NULL)
            """).fetchone()[0]
            return {
                'avg_margin_today': today_margin * 100 if today_margin else 0,
                'avg_margin_yesterday': yesterday_margin * 100 if yesterday_margin else 0,
                'updates_last_week': updates_week,
                'unprofitable_count': unprofitable,
                'no_index_count': no_index,
            }

    def get_recent_history(self, limit: int = 100) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query('''
                SELECT 
                    p.sku as "SKU",
                    ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as "Цена",
                    ph.marginality as "Маржинальность"
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                LIMIT ?
            ''', conn, params=(limit,))

    def get_strategy_counts(self) -> Dict[str, int]:
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT p.sku, ps.strategy_id
                FROM product p
                JOIN product_strategy ps ON p.product_id = ps.product_id
            """).fetchall()
            counts = {"Ниже": 0, "Выше": 0, "Равная": 0, "Смешанная": 0}
            per_sku = {}
            for r in rows:
                sku = r['sku']
                sid = r['strategy_id']
                per_sku.setdefault(sku, set()).add(sid)
            for strategies in per_sku.values():
                if len(strategies) > 1:
                    counts["Смешанная"] += 1
                elif 1 in strategies:
                    counts["Ниже"] += 1
                elif 2 in strategies:
                    counts["Выше"] += 1
                else:
                    counts["Равная"] += 1
            return counts

    def get_strategy_performance(self, days: int = 30) -> pd.DataFrame:
        with self._get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT 
                    s.strategy_name as "Стратегия",
                    AVG(ph.marginality) * 100 as "Средняя маржинальность (%)",
                    COUNT(*) as "Количество обновлений (30 дней)"
                FROM product_price_history ph
                JOIN product_strategy ps ON ph.product_id = ps.product_id
                JOIN strategy s ON ps.strategy_id = s.id
                WHERE ph.timestamp >= datetime('now', ? || ' days')
                GROUP BY s.id
            ''', conn, params=(-days,))
            return df

    def get_stale_products(self, days: int = 7) -> pd.DataFrame:
        with self._get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT 
                    p.sku, p.product_name,
                    MAX(ph.timestamp) as last_update,
                    JULIANDAY('now') - JULIANDAY(MAX(ph.timestamp)) as days_stale
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                GROUP BY p.sku
                HAVING days_stale > ?
                ORDER BY days_stale DESC
            ''', conn, params=(days,))
            return df

    def get_update_heatmap(self, days: int = 90) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query('''
                SELECT 
                    strftime('%w', timestamp) as weekday,
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as updates
                FROM product_price_history
                WHERE timestamp >= datetime('now', ? || ' days')
                GROUP BY weekday, hour
            ''', conn, params=(-days,))

    def get_top_bottom_marginality(self, limit: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
        with self._get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT 
                    p.sku, p.product_name,
                    ph.marginality * 100 as marginality_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id)
                ORDER BY ph.marginality DESC
            ''', conn)
            return df.head(limit), df.tail(limit)

    def get_recent_changes(self, limit: int = 10) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query('''
                SELECT 
                    p.sku, p.product_name, ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
                LIMIT ?
            ''', conn, params=(limit,))

    def export_full_history(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query('''
                SELECT 
                    p.sku, p.product_name, ph.timestamp,
                    ROUND(ph.result_target_price * ph.discount_coef, 0) as price,
                    ROUND(ph.marginality * 100, 2) as margin_pct
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                ORDER BY ph.timestamp DESC
            ''', conn)

    def get_commission_analysis(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            return pd.read_sql_query('''
                SELECT 
                    p.sku,
                    p.product_name,
                    ph.result_target_price,
                    ph.discount_coef,
                    ph.sales_percent_fbs,
                    ph.fbs_first_mile_min_amount,
                    ph.fbs_first_mile_max_amount,
                    ph.fbs_direct_flow_trans_min_amount,
                    ph.fbs_direct_flow_trans_max_amount,
                    ph.fbs_deliv_to_customer_amount,
                    ph.external_index_data_price,
                    ph.ozon_index_data_price,
                    ph.ozon_index_data_index,
                    ph.self_marketplaces_index_data_price,
                    (ph.result_target_price * ph.discount_coef) as real_price,
                    ph.marginality
                FROM product_price_history ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.timestamp = (
                    SELECT MAX(timestamp) FROM product_price_history WHERE product_id = ph.product_id
                )
                ORDER BY p.sku
            ''', conn)

    def delete_product(self, sku: str) -> Dict[str, int]:
        with self._get_connection() as conn:
            product_id_row = conn.execute("SELECT product_id FROM product WHERE sku = ?", (sku,)).fetchone()
            if not product_id_row:
                return {"product": 0, "strategies": 0, "price_history": 0, "margin_history": 0}
            pid = product_id_row['product_id']
            deleted_strategies = conn.execute("DELETE FROM product_strategy WHERE product_id = ?", (pid,)).rowcount
            deleted_price_history = conn.execute("DELETE FROM product_price_history WHERE product_id = ?", (pid,)).rowcount
            deleted_margin_history = conn.execute("DELETE FROM product_marginality_history WHERE product_id = ?", (pid,)).rowcount
            deleted_product = conn.execute("DELETE FROM product WHERE product_id = ?", (pid,)).rowcount
            conn.commit()
            return {
                "product": deleted_product,
                "strategies": deleted_strategies,
                "price_history": deleted_price_history,
                "margin_history": deleted_margin_history,
            }

    def delete_old_records(self, days: int) -> int:
        with self._get_connection() as conn:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
            deleted_price = conn.execute(
                "DELETE FROM product_price_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_margin = conn.execute(
                "DELETE FROM product_marginality_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            conn.execute("""
                DELETE FROM price_calculation_logs
                WHERE history_id IN (SELECT id FROM product_price_history WHERE timestamp < ?)
            """, (cutoff,))
            conn.commit()
            return deleted_price + deleted_margin

    def delete_records_older_than(self, months: int = 3) -> int:
        with self._get_connection() as conn:
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=months * 30)
            deleted_price = conn.execute(
                "DELETE FROM product_price_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            deleted_margin = conn.execute(
                "DELETE FROM product_marginality_history WHERE timestamp < ?", (cutoff,)
            ).rowcount
            conn.execute("""
                DELETE FROM price_calculation_logs
                WHERE history_id IN (SELECT id FROM product_price_history WHERE timestamp < ?)
            """, (cutoff,))
            conn.commit()
            logger.info(f"Очистка БД: удалено {deleted_price} записей истории цен и {deleted_margin} записей маржинальности старше {months} месяцев")
            return deleted_price + deleted_margin

    def get_last_cleanup_date(self) -> Optional[datetime]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM maintenance WHERE key = 'last_cleanup'").fetchone()
            if row and row['value']:
                try:
                    dt = datetime.fromisoformat(row['value'])
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except Exception:
                    return None
            return None

    def set_last_cleanup_date(self, dt: datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE maintenance SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_cleanup'",
                (dt.isoformat(),)
            )
            conn.commit()

    def auto_cleanup_if_needed(self, months: int = 3, days_threshold: int = 1) -> int:
        last = self.get_last_cleanup_date()
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if last is None:
            deleted = self.delete_records_older_than(months)
            self.set_last_cleanup_date(datetime.now(timezone.utc))
            return deleted
        else:
            last_naive = last.astimezone(timezone.utc).replace(tzinfo=None)
            if (now_utc_naive - last_naive).days >= days_threshold:
                deleted = self.delete_records_older_than(months)
                self.set_last_cleanup_date(datetime.now(timezone.utc))
                return deleted
        return 0

    def get_all_last_prices(self) -> pd.DataFrame:
        with self._get_connection() as conn:
            query = """
                SELECT 
                    p.sku,
                    p.product_name,
                    COALESCE(p.real_customer_price, ph.customer_price) as last_price,
                    ph.marginality as last_margin
                FROM (
                    SELECT product_id, 
                        CASE WHEN real_price IS NOT NULL THEN real_price 
                             ELSE result_target_price * discount_coef END as customer_price,
                        marginality,
                        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY timestamp DESC) as rn
                    FROM product_price_history
                ) ph
                JOIN product p ON p.product_id = ph.product_id
                WHERE ph.rn = 1
            """
            return pd.read_sql_query(query, conn)