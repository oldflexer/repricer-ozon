"""
Tests for Value Objects in core.domain.value_objects.
"""
import pytest
from decimal import Decimal
from core.domain.value_objects import SKU, Money, Percentage, DiscountCoefficient, TimeInterval


class TestSKU:
    """Tests for SKU value object."""

    def test_create_valid_sku(self):
        """Test creating a valid SKU."""
        sku = SKU("TEST-001")
        assert str(sku) == "TEST-001"
        assert sku.value == "TEST-001"

    def test_create_sku_strips_whitespace(self):
        """Test that SKU strips whitespace."""
        sku = SKU("  TEST-001  ")
        assert sku.value == "TEST-001"

    def test_create_empty_sku_raises(self):
        """Test that empty SKU raises ValueError."""
        with pytest.raises(ValueError, match="SKU cannot be empty"):
            SKU("")

    def test_create_whitespace_only_sku_raises(self):
        """Test that whitespace-only SKU raises ValueError."""
        with pytest.raises(ValueError, match="SKU cannot be empty"):
            SKU("   ")

    def test_sku_equality(self):
        """Test SKU equality comparison."""
        sku1 = SKU("TEST-001")
        sku2 = SKU("TEST-001")
        sku3 = SKU("TEST-002")
        assert sku1 == sku2
        assert sku1 != sku3
        assert sku1 != "TEST-001"

    def test_sku_hash(self):
        """Test SKU can be used as dict key/set element."""
        sku1 = SKU("TEST-001")
        sku2 = SKU("TEST-001")
        d = {sku1: "value"}
        assert d[sku2] == "value"
        s = {sku1, sku2}
        assert len(s) == 1

class TestPercentage:
    """Tests for Percentage value object."""

    def test_create_from_ratio(self):
        """Test creating Percentage from ratio."""
        p = Percentage.from_ratio(0.05)
        assert p.percent == Decimal("5.00")
        assert p.percent_float == 5.0

    def test_create_from_ratio_int(self):
        """Test creating Percentage from int ratio."""
        p = Percentage.from_ratio(0.1)
        assert p.percent == Decimal("10.00")

    def test_percentage_addition(self):
        """Test Percentage addition."""
        p1 = Percentage.from_ratio(0.05)
        p2 = Percentage.from_ratio(0.03)
        result = p1 + p2
        assert result.percent == Decimal("8.00")

    def test_percentage_string_repr(self):
        """Test Percentage string representation."""
        p = Percentage.from_ratio(0.05)
        assert str(p) == "5.00%"

    def test_percentage_repr(self):
        """Test Percentage repr."""
        p = Percentage.from_ratio(0.05)
        assert repr(p) == "Percentage(5.00%)"


class TestDiscountCoefficient:
    """Tests for DiscountCoefficient value object."""

    def test_create_valid(self):
        """Test creating valid DiscountCoefficient."""
        dc = DiscountCoefficient.from_ratio(0.95)
        assert dc.value == Decimal("0.95")
        assert dc.value_float == 0.95

    def test_create_invalid_zero_raises(self):
        """Test that zero coefficient raises ValueError."""
        with pytest.raises(ValueError, match=r"must be in \(0, 1\]"):
            DiscountCoefficient.from_ratio(0)

    def test_create_invalid_negative_raises(self):
        """Test that negative coefficient raises ValueError."""
        with pytest.raises(ValueError, match=r"must be in \(0, 1\]"):
            DiscountCoefficient.from_ratio(-0.1)

    def test_create_invalid_greater_than_one_raises(self):
        """Test that coefficient > 1 raises ValueError."""
        with pytest.raises(ValueError, match=r"must be in \(0, 1\]"):
            DiscountCoefficient.from_ratio(1.1)

    def test_apply_to_money(self):
        """Test applying discount coefficient to Money."""
        dc = DiscountCoefficient.from_ratio(0.9)
        marketing_price = Money.from_rubles(100.00)
        real_price = dc.apply_to(marketing_price)
        assert real_price.rubles == Decimal("90.00")

    def test_reverse_money(self):
        """Test reversing discount coefficient from real price."""
        dc = DiscountCoefficient.from_ratio(0.9)
        real_price = Money.from_rubles(90.00)
        marketing_price = dc.reverse(real_price)
        assert marketing_price.rubles == Decimal("100.00")

    def test_string_repr(self):
        """Test string representation."""
        dc = DiscountCoefficient.from_ratio(0.95)
        assert str(dc) == "0.9500"


class TestTimeInterval:
    """Tests for TimeInterval value object."""

    def test_create_valid(self):
        """Test creating valid TimeInterval."""
        ti = TimeInterval(9, 0, 18, 0)
        assert ti.start_hour == 9
        assert ti.start_minute == 0
        assert ti.end_hour == 18
        assert ti.end_minute == 0

    def test_create_from_string(self):
        """Test creating TimeInterval from string."""
        ti = TimeInterval.from_string("09:00", "18:00")
        assert ti.start_hour == 9
        assert ti.end_hour == 18

    def test_invalid_hour_raises(self):
        """Test that invalid hour raises ValueError."""
        with pytest.raises(ValueError, match="Invalid start time"):
            TimeInterval(24, 0, 18, 0)

    def test_invalid_minute_raises(self):
        """Test that invalid minute raises ValueError."""
        with pytest.raises(ValueError, match="Invalid start time"):
            TimeInterval(9, 60, 18, 0)

    def test_contains_normal_interval(self):
        """Test contains for normal interval (no midnight crossover)."""
        ti = TimeInterval(9, 0, 18, 0)
        assert ti.contains(12, 0) is True
        assert ti.contains(9, 0) is True
        assert ti.contains(18, 0) is True
        assert ti.contains(8, 59) is False
        assert ti.contains(18, 1) is False

    def test_contains_midnight_crossover(self):
        """Test contains for interval crossing midnight."""
        ti = TimeInterval(22, 0, 6, 0)
        assert ti.contains(23, 0) is True
        assert ti.contains(0, 0) is True
        assert ti.contains(5, 0) is True
        assert ti.contains(21, 59) is False
        assert ti.contains(6, 1) is False

    def test_contains_edge_cases(self):
        """Test contains edge cases."""
        ti = TimeInterval(9, 0, 18, 0)
        assert ti.contains(9, 0) is True
        assert ti.contains(18, 0) is True

    def test_string_repr(self):
        """Test string representation."""
        ti = TimeInterval(9, 0, 18, 0)
        assert str(ti) == "09:00-18:00"

    def test_start_end_minutes(self):
        """Test start_minutes and end_minutes properties."""
        ti = TimeInterval(9, 30, 18, 45)
        assert ti.start_minutes == 570
        assert ti.end_minutes == 1125
