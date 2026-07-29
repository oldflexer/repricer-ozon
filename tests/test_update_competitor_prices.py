import sys
from pathlib import Path
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.parser import update_prices, parse_price_with_retry


def test_parse_price_with_retry_success():
    mock_parser = MagicMock()
    mock_parser.get_price.return_value = 1500.0
    price = parse_price_with_retry(mock_parser, "http://test.com")
    assert price == 1500.0
    assert mock_parser.get_price.call_count == 1


def test_parse_price_with_retry_fails():
    mock_parser = MagicMock()
    mock_parser.get_price.return_value = None
    with patch('time.sleep'):
        price = parse_price_with_retry(mock_parser, "http://test.com")
        assert price is None
        assert mock_parser.get_price.call_count == 2
        assert mock_parser.restart.call_count == 1


def test_update_prices_dry_run(tmp_path):
    df = pd.DataFrame({
        'SKU': ['123'],
        'Конкурент 1': ['https://ozon.ru/1'],
        'Цена 1': [None]
    })
    excel_path = tmp_path / 'test.xlsx'
    df.to_excel(excel_path, index=False)

    with patch('update_competitor_prices.settings.DATA_FILE_PATH', excel_path):
        with patch('update_competitor_prices.parse_price_with_retry') as mock_parse:
            mock_parse.return_value = 999.0
            stats = update_prices(dry_run=True)
            assert stats['updated'] == 1
            df_after = pd.read_excel(excel_path)
            assert pd.isna(df_after.loc[0, 'Цена 1'])