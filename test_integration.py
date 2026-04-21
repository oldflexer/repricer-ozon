import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from src.main import Repricer

@pytest.mark.asyncio
async def test_repricer_dry_run():
    with patch('src.main.DataLoader') as mock_loader, \
         patch('src.main.OzonParser') as mock_parser, \
         patch('src.main.OzonApiClient') as mock_api, \
         patch('src.main.Database') as mock_db:
        
        mock_loader.return_value.load.return_value = [{
            'offer_id': '001',
            'product_name': 'Test',
            'cost_price': 100,
            'min_price': 200,
            'current_price': 300,
            'strategy': 3,
            'strategy_percent': 0,
            'schedule': None,
            'competitor_urls': ['http://test.com']
        }]
        mock_parser.return_value.__aenter__.return_value.get_prices.return_value = [250.0]
        mock_db.return_value.get_average_margin.return_value = 20.0
        
        repricer = Repricer(dry_run=True)
        stats = await repricer.run()
        assert stats['prices_updated'] == 1