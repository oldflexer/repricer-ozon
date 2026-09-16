import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.ozon_competitor import OzonPriceParser


@pytest.fixture
def parser():
    with patch("undetected_chromedriver.Chrome") as mock_driver_class:
        mock_driver = MagicMock()
        mock_driver_class.return_value = mock_driver
        p = OzonPriceParser()
        p.driver = mock_driver
        p.wait = MagicMock()
        # Mock find_element to raise NoSuchElementException (no "out of stock" element)
        from selenium.common.exceptions import NoSuchElementException

        mock_driver.find_element.side_effect = NoSuchElementException("not found")
        # Mock find_elements to return empty list for CAPTCHA/block detection
        mock_driver.find_elements.return_value = []
        return p


def test_get_price_success(parser):
    mock_price_element = MagicMock()
    mock_price_element.text = "2 458 ₽"
    # Use side_effect to handle the callable argument passed to wait.until()
    parser.wait.until.side_effect = lambda x: [mock_price_element]
    
    # Debug: check the parser state
    print(f"parser.driver: {parser.driver}")
    print(f"parser.wait: {parser.wait}")
    print(f"parser.wait.until.side_effect: {parser.wait.until.side_effect}")
    
    # Call get_price with debug
    import time
    start_time = time.time()
    
    price = None  # Initialize to avoid unbound variable
    
    if not parser._ensure_driver():
        print('_ensure_driver failed')
        assert False
    print('_ensure_driver ok')
    
    try:
        parser.driver.get("https://example.com")
        print('driver.get called')
        
        print('_detect_captcha_or_block:', parser._detect_captcha_or_block())
        print('_detect_product_ended:', parser._detect_product_ended())
        
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.common.by import By
        
        price_selectors = [
            'span[data-testid="price-price"]',
            "span.tsHeadline600Large",
            "span.pdp_b0h.tsHeadline600Large",
            "span.pdp_b0h.tsHeadline500Medium",
            'div[data-testid="price"] span',
            'span[class*="tsHeadline"]',
        ]
        
        price_element = None
        for selector in price_selectors:
            print(f'Trying selector: {selector}')
            try:
                elements = parser.wait.until(
                    ec.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                print(f'  Result: {elements}')
                for el in elements:
                    text = el.text.strip()
                    print(f'  Element text: {text}')
                    if '₽' in text:
                        price_element = el
                        print(f'  Found price element: {text}')
                        break
                if price_element:
                    break
            except Exception as e:
                print(f'  Exception: {e}')
                continue
        
        print(f'price_element after loop: {price_element}')
        
        if not price_element:
            print('No price element found!')
        else:
            raw_price = price_element.text.strip()
            print(f'raw_price: {raw_price}')
            cleaned = ''.join(c for c in raw_price if c.isdigit() or c in '.,')
            cleaned = cleaned.replace(',', '.')
            parts = cleaned.split('.')
            if len(parts) > 1:
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            price = float(cleaned)
            print(f'price: {price}')
        
    except Exception as e:
        print(f'Exception: {e}')
        import traceback
        traceback.print_exc()
    finally:
        duration = time.time() - start_time
        print(f'duration: {duration}')
    
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
        print(f'wait.until call #{call_count[0]}')
        if call_count[0] == 1:
            return mock_elements_first
        return mock_elements_second

    parser.wait.until.side_effect = side_effect
    
    import time
    start_time = time.time()
    
    price = None  # Initialize to avoid unbound variable
    
    if not parser._ensure_driver():
        print('_ensure_driver failed')
        assert False
    print('_ensure_driver ok')
    
    try:
        parser.driver.get("https://example.com")
        print('driver.get called')
        
        print('_detect_captcha_or_block:', parser._detect_captcha_or_block())
        print('_detect_product_ended:', parser._detect_product_ended())
        
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.common.by import By
        
        price_selectors = [
            'span[data-testid="price-price"]',
            "span.tsHeadline600Large",
            "span.pdp_b0h.tsHeadline600Large",
            "span.pdp_b0h.tsHeadline500Medium",
            'div[data-testid="price"] span',
            'span[class*="tsHeadline"]',
        ]
        
        price_element = None
        for selector in price_selectors:
            print(f'Trying selector: {selector}')
            try:
                elements = parser.wait.until(
                    ec.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                print(f'  Result: {elements}')
                for el in elements:
                    text = el.text.strip()
                    print(f'  Element text: {text}')
                    if '₽' in text:
                        price_element = el
                        print(f'  Found price element: {text}')
                        break
                if price_element:
                    break
            except Exception as e:
                print(f'  Exception: {e}')
                continue
        
        print(f'price_element after loop: {price_element}')
        
        if not price_element:
            print('No price element found!')
        else:
            raw_price = price_element.text.strip()
            print(f'raw_price: {raw_price}')
            cleaned = ''.join(c for c in raw_price if c.isdigit() or c in '.,')
            cleaned = cleaned.replace(',', '.')
            parts = cleaned.split('.')
            if len(parts) > 1:
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            price = float(cleaned)
            print(f'price: {price}')
        
    except Exception as e:
        print(f'Exception: {e}')
        import traceback
        traceback.print_exc()
    finally:
        duration = time.time() - start_time
        print(f'duration: {duration}')
    
    assert price == 3200.0
