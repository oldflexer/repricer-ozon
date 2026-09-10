"""
Database repositories package.

Provides separate repository classes for each domain area.
"""

from .base import BaseRepository, DBConnectionMixin
from .product_repo import ProductRepository
from .price_history_repo import PriceHistoryRepository
from .marginality_repo import MarginalityRepository
from .analytics_repo import AnalyticsRepository
from .maintenance_repo import MaintenanceRepository

__all__ = [
    "BaseRepository",
    "DBConnectionMixin",
    "ProductRepository",
    "PriceHistoryRepository",
    "MarginalityRepository",
    "AnalyticsRepository",
    "MaintenanceRepository",
]