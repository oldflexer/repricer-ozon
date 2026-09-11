"""
Tests for OzonPricingRules in core.domain.pricing_rules.
"""
import pytest
from decimal import Decimal
from core.domain.pricing_rules import OzonPricingRules
from core.domain.value_objects import Money, Percentage, DiscountCoefficient


@pytest.fixture
def rules() -> OzonPricingRules:
    """Default OzonPricingRules instance for testing."""
    return OzonPricingRules()


@pytest.fixture
def custom_rules() -> OzonPricingRules:
    """Custom OzonPricingRules instance for testing."""
    return OzonPricingRules(
        min_price_ratio=Decimal("0.5"),
        old_price_multiplier=Decimal("1.5"),
        old_price_round_step=100,
        default_discount_coef=DiscountCoefficient.from_ratio("0.5"),
    )


class TestValidateMinPrice:
    """Tests for validate_min_price method."""

    def test_min_price_below_lower_bound(self, rules: OzonPricingRules):
        """Test min_price below lower bound gets raised to lower bound."""
        price = Money.from_rubles(100.00)
        min_price = Money.from_rubles(30.00)  # Below 50 (price * 0.5)
        result = rules.validate_min_price(price, min_price)
        assert result.rubles == Decimal("50.00")

    def test_min_price_above_upper_bound(self, rules: OzonPricingRules):
        """Test min_price above upper bound gets lowered to price."""
        price = Money.from_rubles(100.00)
        min_price = Money.from_rubles(120.00)  # Above price
        result = rules.validate_min_price(price, min_price)
        assert result.rubles == Decimal("100.00")

    def test_min_price_within_bounds(self, rules: OzonPricingRules):
        """Test min_price within bounds stays unchanged."""
        price = Money.from_rubles(100.00)
        min_price = Money.from_rubles(75.00)  # Between 50 and 100
        result = rules.validate_min_price(price, min_price)
        assert result.rubles == Decimal("75.00")

    def test_min_price_at_lower_bound(self, rules: OzonPricingRules):
        """Test min_price exactly at lower bound."""
        price = Money.from_rubles(100.00)
        min_price = Money.from_rubles(50.00)  # Exactly price * 0.5
        result = rules.validate_min_price(price, min_price)
        assert result.rubles == Decimal("50.00")

    def test_min_price_at_upper_bound(self, rules: OzonPricingRules):
        """Test min_price exactly at upper bound (price)."""
        price = Money.from_rubles(100.00)
        min_price = Money.from_rubles(100.00)
        result = rules.validate_min_price(price, min_price)
        assert result.rubles == Decimal("100.00")

    def test_custom_min_price_ratio(self, custom_rules: OzonPricingRules):
        """Test with custom min_price_ratio."""
        price = Money.from_rubles(100.00)
        min_price = Money.from_rubles(30.00)  # Below 50
        result = custom_rules.validate_min_price(price, min_price)
        assert result.rubles == Decimal("50.00")


class TestCalculateOldPrice:
    """Tests for calculate_old_price method."""

    def test_manual_old_price_higher_than_calculated(self, rules: OzonPricingRules):
        """Test manual old_price used when higher than calculated."""
        price = Money.from_rubles(100.00)
        manual_old = Money.from_rubles(200.00)  # Higher than 100 * 1.5 = 150
        result = rules.calculate_old_price(price, manual_old)
        assert result.rubles == Decimal("200.00")

    def test_manual_old_price_lower_than_calculated(self, rules: OzonPricingRules):
        """Test calculated old_price used when manual is lower."""
        price = Money.from_rubles(100.00)
        manual_old = Money.from_rubles(120.00)  # Lower than 150
        result = rules.calculate_old_price(price, manual_old)
        # Should use calculated: 100 * 1.5 = 150, rounded to 100 step = 200
        assert result.rubles == Decimal("200.00")

    def test_no_manual_old_price(self, rules: OzonPricingRules):
        """Test calculated old_price when no manual provided."""
        price = Money.from_rubles(100.00)
        result = rules.calculate_old_price(price, None)
        # 100 * 1.5 = 150, rounded up to nearest 100 = 200
        assert result.rubles == Decimal("200.00")

    def test_old_price_rounding(self, rules: OzonPricingRules):
        """Test old_price rounding to step."""
        price = Money.from_rubles(100.00)
        result = rules.calculate_old_price(price, None)
        # 100 * 1.5 = 150, rounded up to nearest 100 = 200
        assert result.rubles == Decimal("200.00")

    def test_old_price_exact_multiple(self, rules: OzonPricingRules):
        """Test old_price when already multiple of round_step."""
        price = Money.from_rubles(200.00)
        result = rules.calculate_old_price(price, None)
        # 200 * 1.5 = 300, already multiple of 100
        assert result.rubles == Decimal("300.00")

    def test_custom_old_price_multiplier(self, custom_rules: OzonPricingRules):
        """Test with custom old_price_multiplier."""
        price = Money.from_rubles(100.00)
        result = custom_rules.calculate_old_price(price, None)
        # 100 * 1.5 = 150, rounded up to 100 = 200
        assert result.rubles == Decimal("200.00")


class TestCalculateTargetMinPrice:
    """Tests for calculate_target_min_price method."""

    def test_basic_calculation(self, rules: OzonPricingRules):
        """Test basic target_min_price calculation."""
        rip = Money.from_rubles(100.00)
        discount_coef = DiscountCoefficient.from_ratio("0.5")
        result = rules.calculate_target_min_price(rip, discount_coef)
        # 100 / 0.5 = 200
        assert result.rubles == Decimal("200.00")

    def test_with_different_discount_coef(self, rules: OzonPricingRules):
        """Test with different discount coefficient."""
        rip = Money.from_rubles(100.00)
        discount_coef = DiscountCoefficient.from_ratio("0.8")
        result = rules.calculate_target_min_price(rip, discount_coef)
        # 100 / 0.8 = 125
        assert result.rubles == Decimal("125.00")

    def test_with_small_rip(self, rules: OzonPricingRules):
        """Test with small RIP value."""
        rip = Money.from_rubles(10.00)
        discount_coef = DiscountCoefficient.from_ratio("0.5")
        result = rules.calculate_target_min_price(rip, discount_coef)
        # 10 / 0.5 = 20
        assert result.rubles == Decimal("20.00")


class TestStrategyApplications:
    """Tests for strategy application methods."""

    def test_apply_strategy_below(self, rules: OzonPricingRules):
        """Test 'Below' strategy: base_price * (1 - percent)."""
        base_price = Money.from_rubles(100.00)
        percent = Percentage.from_ratio(0.10)  # 10%
        result = rules.apply_strategy_below(base_price, percent)
        # 100 * (1 - 0.10) = 90
        assert result.rubles == Decimal("90.00")

    def test_apply_strategy_above(self, rules: OzonPricingRules):
        """Test 'Above' strategy: base_price * (1 + percent)."""
        base_price = Money.from_rubles(100.00)
        percent = Percentage.from_ratio(0.10)  # 10%
        result = rules.apply_strategy_above(base_price, percent)
        # 100 * (1 + 0.10) = 110
        assert result.rubles == Decimal("110.00")

    def test_apply_strategy_equal(self, rules: OzonPricingRules):
        """Test 'Equal' strategy: returns target_min_price as is."""
        target_min = Money.from_rubles(150.00)
        result = rules.apply_strategy_equal(target_min)
        assert result.rubles == Decimal("150.00")

    def test_strategy_below_with_zero_percent(self, rules: OzonPricingRules):
        """Test 'Below' strategy with 0%."""
        base_price = Money.from_rubles(100.00)
        percent = Percentage.from_ratio(0.0)
        result = rules.apply_strategy_below(base_price, percent)
        assert result.rubles == Decimal("100.00")

    def test_strategy_above_with_zero_percent(self, rules: OzonPricingRules):
        """Test 'Above' strategy with 0%."""
        base_price = Money.from_rubles(100.00)
        percent = Percentage.from_ratio(0.0)
        result = rules.apply_strategy_above(base_price, percent)
        assert result.rubles == Decimal("100.00")


class TestFromSettings:
    """Tests for from_settings class method."""

    def test_from_settings_uses_defaults(self):
        """Test from_settings creates instance with defaults when settings missing."""
        from config.settings import Settings
        
        # Create minimal settings with COEFFICIENT_OZON set to 0.5
        settings = Settings(
            OZON_CLIENT_ID="test",
            OZON_API_KEY="test",
            DATA_FILE="test.xlsx",
            DATABASE_PATH="test.db",
            COEFFICIENT_OZON=0.5,
        )
        
        rules = OzonPricingRules.from_settings(settings)
        assert isinstance(rules, OzonPricingRules)
        assert rules.min_price_ratio == Decimal("0.5")
        assert rules.old_price_multiplier == Decimal("1.5")