import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.ozon_parser import OzonPriceParser


@pytest.fixture
def parser():
    with patch('undetected_chromedriver.Chrome') as mock_driver_class:
        mock_driver = MagicMock()
        mock_driver_class.return_value = mock_driver
        p = OzonPriceParser(headless=True)
        p.driver = mock_driver
        p.wait = MagicMock()
        # Mock find_element to raise NoSuchElementException (no "out of stock" element)
        from selenium.common.exceptions import NoSuchElementException
        mock_driver.find_element.side_effect = NoSuchElementException("not found")
        return p


def test_get_price_success(parser):
    mock_price_element = MagicMock()
    mock_price_element.text = "2 458 ₽"
    parser.wait.until.return_value = [mock_price_element]
    price = parser.get_price("https://example.com")
    assert price == 2458.0


def test_get_price_no_price(parser):
    parser.wait.until.side_effect = Exception("No element")
    price = parser.get_price("https://example.com")
    assert price is None


def test_get_price_multiple_selectors(parser):
    # First selector returns "Цена: 3 200 ₽", second returns "2 458 ₽"
    # The code picks the first element with "₽" in it
    mock_elements_first = [MagicMock(text="Цена: 3 200 ₽")]
    mock_elements_second = [MagicMock(text="2 458 ₽")]
    
    # First call returns the first element, second call returns the second
    call_count = [0]
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_elements_first
        return mock_elements_second
    
    parser.wait.until.side_effect = side_effect
    price = parser.get_price("https://example.com")
    # The code returns the FIRST price found with "₽" symbol
    assert price == 3200.0