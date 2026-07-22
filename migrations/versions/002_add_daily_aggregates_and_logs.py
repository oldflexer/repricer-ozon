# migrations/versions/002_add_daily_aggregates_and_logs.py

"""add daily aggregates and logs tables

Revision ID: 002
Revises: 001
Create Date: 2026-07-22 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_price_daily',
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('avg_price', sa.REAL(), nullable=True),
        sa.Column('avg_marginality', sa.REAL(), nullable=True),
        sa.Column('min_price', sa.REAL(), nullable=True),
        sa.Column('max_price', sa.REAL(), nullable=True),
        sa.Column('updates_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('product_id', 'date'),
        sa.ForeignKeyConstraint(['product_id'], ['product.product_id'], ),
    )
    op.create_table(
        'price_calculation_logs',
        sa.Column('history_id', sa.Integer(), nullable=False),
        sa.Column('log_details', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('history_id'),
        sa.ForeignKeyConstraint(['history_id'], ['product_price_history.id'], ),
    )
    # Индексы
    op.create_index('idx_history_timestamp', 'product_price_history', ['timestamp'])
    op.create_index('idx_history_product_marginality', 'product_price_history', ['product_id', 'marginality'])
    op.create_index('idx_daily_product_date', 'product_price_daily', ['product_id', 'date'])


def downgrade() -> None:
    op.drop_index('idx_daily_product_date', table_name='product_price_daily')
    op.drop_index('idx_history_product_marginality', table_name='product_price_history')
    op.drop_index('idx_history_timestamp', table_name='product_price_history')
    op.drop_table('price_calculation_logs')
    op.drop_table('product_price_daily')