"""
Core domain package - Rich Domain Model.
"""

from .pricing_rules import OzonPricingRules, get_pricing_rules, set_pricing_rules
from .product import PricingStrategy, Product
from .value_objects import SKU, DiscountCoefficient, Money, Percentage, TimeInterval

__all__ = [
    "SKU",
    "Money",
    "Percentage",
    "DiscountCoefficient",
    "TimeInterval",
    "OzonPricingRules",
    "get_pricing_rules",
    "set_pricing_rules",
    "Product",
    "PricingStrategy",
]
