"""
Protocols package - typed interfaces for dependency injection.
"""

from .repository import (
    IAnalyticsRepository,
    IMaintenanceRepository,
    IMarginalityRepository,
    IPriceHistoryRepository,
    IProductRepository,
    IRepository,
)

__all__ = [
    "IProductRepository",
    "IPriceHistoryRepository",
    "IMarginalityRepository",
    "IAnalyticsRepository",
    "IMaintenanceRepository",
    "IRepository",
]
