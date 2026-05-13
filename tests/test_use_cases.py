import sys
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.use_cases import RepricingUseCase
from core.entities import ProductInfo, PricingData
from core.services import PriceCalculationService

def test_execute_dry_run():
    repo = MagicMock()
    repo.get_all_products.return_value = []
    api = MagicMock()
    notifier = MagicMock()
    loader = MagicMock()
    loader.load.return_value = []
    calc = PriceCalculationService()
    use_case = RepricingUseCase(repo, api, notifier, calc, loader)
    stats = use_case.execute(dry_run=True)
    assert stats['products_loaded'] == 0

def test_execute_full():
    # Более детальный тест с подготовленными данными
    ...