"""
Тесты для парсинга цен конкурентов.

Проверяют:
- успешный парсинг цены,
- обработку ошибок при неудачном парсинге,
- dry-run режим (не записывает данные в Excel).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.use_cases.parse_competitor_prices import ParseCompetitorPricesUseCase


@pytest.mark.asyncio
async def test_parse_price_with_retry_success():
    """Тест успешного парсинга цены."""
    mock_parser = MagicMock()
    mock_parser.get_price.return_value = 1500.0

    use_case = ParseCompetitorPricesUseCase(parser=mock_parser)
    price = use_case._parse_price_with_retry("http://test.com")
    assert price == 1500.0
    assert mock_parser.get_price.call_count == 1


@pytest.mark.asyncio
async def test_parse_price_with_retry_fails():
    """Тест, когда парсинг не удаётся."""
    mock_parser = MagicMock()
    mock_parser.get_price.return_value = None

    use_case = ParseCompetitorPricesUseCase(parser=mock_parser)
    with patch("time.sleep"):
        price = use_case._parse_price_with_retry("http://test.com")
        assert price is None
        assert mock_parser.get_price.call_count == 2
        assert mock_parser.restart.call_count == 1


@pytest.mark.asyncio
async def test_update_prices_dry_run(tmp_path):
    """Тест dry-run режима (не записывает в Excel)."""
    # Создаём тестовый Excel-файл
    df = pd.DataFrame({"SKU": ["123"], "Конкурент 1": ["https://ozon.ru/1"], "Цена 1": [None]})
    excel_path = tmp_path / "test.xlsx"
    df.to_excel(excel_path, index=False)

    # Мокаем путь к Excel
    from config.settings import settings

    with patch.object(type(settings), "data_file_path", new_callable=PropertyMock) as mock_path:
        mock_path.return_value = excel_path

        # Создаём UseCase и мокаем парсинг
        use_case = ParseCompetitorPricesUseCase()
        with patch.object(use_case, "_parse_price_with_retry", return_value=999.0):
            stats = await use_case.execute(dry_run=True)
            assert stats["updated"] == 1
            # Проверяем, что Excel не был изменён (dry-run)
            df_after = pd.read_excel(excel_path)
            assert pd.isna(df_after.loc[0, "Цена 1"])


@pytest.mark.asyncio
async def test_update_prices_real_run(tmp_path):
    """Тест реального запуска (с записью в Excel)."""
    # Создаём тестовый Excel-файл
    df = pd.DataFrame({"SKU": ["123"], "Конкурент 1": ["https://ozon.ru/1"], "Цена 1": [None]})
    excel_path = tmp_path / "test.xlsx"
    df.to_excel(excel_path, index=False)

    # Мокаем путь к Excel
    from config.settings import settings

    with patch.object(type(settings), "data_file_path", new_callable=PropertyMock) as mock_path:
        mock_path.return_value = excel_path

        # Мокаем только wait_for_excel_available, но НЕ save_safely (чтобы проверить реальную запись)
        with patch(
            "core.use_cases.parse_competitor_prices.wait_for_excel_available", return_value=True
        ):
            use_case = ParseCompetitorPricesUseCase()
            with patch.object(use_case, "_parse_price_with_retry", return_value=999.0):
                stats = await use_case.execute(dry_run=False)
                assert stats["updated"] == 1
                # Проверяем, что в Excel записалась цена
                df_after = pd.read_excel(excel_path)
                assert df_after.loc[0, "Цена 1"] == 999.0


@pytest.mark.asyncio
async def test_update_prices_file_not_found(tmp_path):
    """Тест, когда файл не найден."""
    from config.settings import settings

    with patch.object(type(settings), "data_file_path", new_callable=PropertyMock) as mock_path:
        mock_path.return_value = tmp_path / "nonexistent.xlsx"

        use_case = ParseCompetitorPricesUseCase()
        stats = await use_case.execute(dry_run=False)
        assert stats == {"updated": 0, "errors": 0, "skipped": 0}

