"""
Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-07-22 20:00:00.000000

Создаёт основные таблицы:
    - product
    - strategy
    - product_strategy
    - product_price_history
    - product_marginality_history
    - maintenance

Добавляет начальные данные стратегий (Ниже, Выше, Равная)
и запись в maintenance о последней очистке.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Идентификаторы ревизии
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Применяет миграцию – создаёт таблицы и индексы, заполняет начальными данными."""
    # Таблица товаров
    op.create_table(
        "product",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Text(), nullable=True),
        sa.Column("sku", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("rip", sa.REAL(), nullable=True),
        sa.Column("net_price", sa.REAL(), nullable=True),
        sa.Column(
            "last_updated",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("real_customer_price", sa.REAL(), nullable=True),
        sa.PrimaryKeyConstraint("product_id"),
        sa.UniqueConstraint("sku"),
    )

    # Таблица стратегий (справочник)
    op.create_table(
        "strategy",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("strategy_name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_name"),
    )

    # Связь товаров со стратегиями (интервалы)
    op.create_table(
        "product_strategy",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("interval_start", sa.Text(), nullable=True),
        sa.Column("interval_stop", sa.Text(), nullable=True),
        sa.Column("strategy_id", sa.Integer(), nullable=True),
        sa.Column("strategy_percent", sa.REAL(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["product.product_id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategy.id"]),
    )

    # История цен
    op.create_table(
        "product_price_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("min_price", sa.REAL(), nullable=True),
        sa.Column("price", sa.REAL(), nullable=True),
        sa.Column("old_price", sa.REAL(), nullable=True),
        sa.Column("marketing_seller_price", sa.REAL(), nullable=True),
        sa.Column("external_index_data_price", sa.REAL(), nullable=True),
        sa.Column("external_index_data_index", sa.REAL(), nullable=True),
        sa.Column("ozon_index_data_price", sa.REAL(), nullable=True),
        sa.Column("ozon_index_data_index", sa.REAL(), nullable=True),
        sa.Column("self_marketplaces_index_data_price", sa.REAL(), nullable=True),
        sa.Column("self_marketplaces_index_data_index", sa.REAL(), nullable=True),
        sa.Column("result_target_price", sa.REAL(), nullable=True),
        sa.Column("discount_coef", sa.REAL(), nullable=True),
        sa.Column("marginality", sa.REAL(), nullable=True),
        sa.Column("sales_percent_fbs", sa.REAL(), nullable=True),
        sa.Column("acquiring", sa.REAL(), nullable=True),
        sa.Column("fbs_first_mile_min_amount", sa.REAL(), nullable=True),
        sa.Column("fbs_first_mile_max_amount", sa.REAL(), nullable=True),
        sa.Column("fbs_direct_flow_trans_min_amount", sa.REAL(), nullable=True),
        sa.Column("fbs_direct_flow_trans_max_amount", sa.REAL(), nullable=True),
        sa.Column("fbs_deliv_to_customer_amount", sa.REAL(), nullable=True),
        sa.Column("log_details", sa.Text(), nullable=True),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("real_price", sa.REAL(), nullable=True),
        sa.Column("fbo_deliv_to_customer_amount", sa.REAL(), nullable=True),
        sa.Column("fbo_direct_flow_trans_min_amount", sa.REAL(), nullable=True),
        sa.Column("fbo_direct_flow_trans_max_amount", sa.REAL(), nullable=True),
        sa.Column("fbo_return_flow_amount", sa.REAL(), nullable=True),
        sa.Column("fbs_return_flow_amount", sa.REAL(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["product.product_id"]),
    )

    # История маржинальности
    op.create_table(
        "product_marginality_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("marginality", sa.REAL(), nullable=True),
        sa.Column("marginality_week", sa.REAL(), nullable=True),
        sa.Column("marginality_month", sa.REAL(), nullable=True),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["product.product_id"]),
    )

    # Служебная таблица (для хранения даты последней очистки и т.п.)
    op.create_table(
        "maintenance",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("key"),
    )

    # Индексы
    op.create_index("idx_product_sku", "product", ["sku"])
    op.create_index(
        "idx_history_product_timestamp",
        "product_price_history",
        ["product_id", "timestamp"],
    )
    op.create_index(
        "idx_marginality_product_timestamp",
        "product_marginality_history",
        ["product_id", "timestamp"],
    )

    # Начальные данные стратегий
    op.execute(
        "INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (1, 'Ниже')"
    )
    op.execute(
        "INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (2, 'Выше')"
    )
    op.execute(
        "INSERT OR IGNORE INTO strategy(id, strategy_name) VALUES (3, 'Равная')"
    )

    # Начальные данные maintenance
    op.execute(
        "INSERT OR IGNORE INTO maintenance (key, value) "
        "VALUES ('last_cleanup', '1970-01-01 00:00:00')"
    )


def downgrade() -> None:
    """Откатывает миграцию – удаляет таблицы и индексы."""
    op.drop_index("idx_marginality_product_timestamp", table_name="product_marginality_history")
    op.drop_index("idx_history_product_timestamp", table_name="product_price_history")
    op.drop_index("idx_product_sku", table_name="product")

    op.drop_table("maintenance")
    op.drop_table("product_marginality_history")
    op.drop_table("product_price_history")
    op.drop_table("product_strategy")
    op.drop_table("strategy")
    op.drop_table("product")