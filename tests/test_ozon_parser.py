import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.ozon_parser import OzonPriceParser


@pytest.fixture
def parser():
    with patch('infrastructure.ozon_parser.uc.Chrome') as mock_driver:
        mock_driver.return_value = MagicMock()
        p = OzonPriceParser(headless=True)
        p.driver = mock_driver
        p.wait = MagicMock()
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
    mock_elements = [
        MagicMock(text="Цена: 3 200 ₽"),
        MagicMock(text="2 458 ₽"),
    ]
    parser.wait.until.return_value = mock_elements
    price = parser.get_price("https://example.com")
    assert price == 2458.0