import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.use_cases.update_price_timer import UpdatePriceTimerUseCase
from scripts.actions_update_price_timer import parse_product_ids


@pytest.mark.asyncio
async def test_update_price_timer_success():
    """Тест успешного обновления таймера."""
    mock_api = AsyncMock()
    mock_api.update_price_timer.return_value = {
        123: {"success": True, "error": None},
        456: {"success": True, "error": None},
    }

    use_case = UpdatePriceTimerUseCase(mock_api)
    stats = await use_case.execute(product_ids=[123, 456])

    assert stats == {"success": 2, "failed": 0}
    mock_api.update_price_timer.assert_called_once_with([123, 456])


@pytest.mark.asyncio
async def test_update_price_timer_partial_failure():
    """Тест частичной ошибки."""
    mock_api = AsyncMock()
    mock_api.update_price_timer.return_value = {
        123: {"success": True, "error": None},
        456: {"success": False, "error": "Таймер не найден"},
    }

    use_case = UpdatePriceTimerUseCase(mock_api)
    stats = await use_case.execute(product_ids=[123, 456])

    assert stats == {"success": 1, "failed": 1}


@pytest.mark.asyncio
async def test_update_price_timer_empty_list():
    """Тест пустого списка product_ids."""
    mock_api = AsyncMock()
    use_case = UpdatePriceTimerUseCase(mock_api)
    stats = await use_case.execute(product_ids=[])

    assert stats == {"success": 0, "failed": 0}
    mock_api.update_price_timer.assert_not_called()


def test_parse_product_ids():
    """Тест парсинга строки product_ids."""
    assert parse_product_ids("123,456,789") == [123, 456, 789]
    assert parse_product_ids("123, 456, 789") == [123, 456, 789]
    assert parse_product_ids("") == []
    assert parse_product_ids("123,,456") == [123, 456]
