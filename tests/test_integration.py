import sys
from pathlib import Path
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import Repricer


@patch('src.main.Database')
@patch('src.main.CompetitorsParser')
@patch('src.main.ProductsParser')
@patch('src.main.PriceMaker')
@patch('src.main.PriceUpdater')
@patch('src.main.MailNotifier')
@patch('src.main.OzonApiClient')
@patch('src.main.DataLoader')
async def test_repricer_dry_run(
    mock_loader_cls, mock_api_cls, mock_notifier_cls,
    mock_updater_cls, mock_pricemaker_cls,
    mock_prod_parser_cls, mock_comp_parser_cls, mock_db_cls
):
    # Настройка моков
    mock_loader = mock_loader_cls.return_value
    mock_loader.load.return_value = [{
        'sku': '001',
        'product_name': 'Test',
        'cost_price': 100,
        'min_price': 200,
        'current_price': 300,
        'intervals': [{'start': '00:00', 'end': '23:59', 'strategy': 3, 'percent': 0}],
        'competitor_urls': ['http://test.com'],
        'product_id': None,
        'offer_id': None,
    }]

    mock_db = mock_db_cls.return_value
    mock_db.get_average_margin.return_value = 20.0

    mock_api = mock_api_cls.return_value
    mock_api.get_product_ids_by_skus.return_value = {'001': {'product_id': 123, 'offer_id': '001'}}

    # Парсер товаров
    async def fetch_real_prices(products):
        return {'001': 250.0}
    mock_prod_parser = mock_prod_parser_cls.return_value
    mock_prod_parser.fetch_real_prices = fetch_real_prices

    # Парсер конкурентов
    async def comp_run(products):
        return {'competitor_prices_parsed': 1}
    mock_comp_parser = mock_comp_parser_cls.return_value
    mock_comp_parser.run = comp_run

    # PriceMaker
    def calculate(products, real_prices):
        updates = [{
            'product_id': 123,
            'offer_id': '',
            'price': '250.00',
            'old_price': '300.00',
            'min_price': '200.00'
        }]
        margin_items = [{'sku': '001', 'target_price': 250.0, 'margin': 20.0}]
        return updates, margin_items
    mock_pricemaker = mock_pricemaker_cls.return_value
    mock_pricemaker.calculate = calculate

    # PriceUpdater
    def update(updates, margins):
        return {'prices_updated': 1, 'errors': []}
    mock_updater = mock_updater_cls.return_value
    mock_updater.update = update

    # Notifier (мок)
    mock_notifier_cls.return_value

    # Запуск
    repricer = Repricer(dry_run=True)
    stats = await repricer.run()

    print(f"Результат: {stats}")
    assert stats['prices_updated'] == 1, f"Ожидалось 1 обновление, получено {stats['prices_updated']}"
    print("✅ Интеграционный тест пройден")


if __name__ == "__main__":
    asyncio.run(test_repricer_dry_run())