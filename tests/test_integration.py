import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.domain.pricing_rules import OzonPricingRules
from core.entities import PricingData
from core.use_cases import RepricingUseCase, RepricingUseCaseDependencies
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.mail_notifier import MailNotifier


class MockOzonApiClient:
    def __init__(self):
        self.products_map = {}
        self.prices_map = {}

    def set_product(self, sku, product_id, offer_id, product_name):
        self.products_map[sku] = {
            "product_id": product_id,
            "offer_id": offer_id,
            "product_name": product_name,
        }

    def set_price(self, product_id, price_data):
        self.prices_map[product_id] = price_data

    async def get_product_ids_by_skus(self, skus):
        result = {}
        for sku in skus:
            if sku in self.products_map:
                result[sku] = self.products_map[sku]
        return result

    async def get_product_prices(self, product_ids):
        result = []
        for pid in product_ids:
            if pid in self.prices_map:
                result.append(self.prices_map[pid])
        return result

    async def update_prices(self, prices_data):
        result = {}
        for item in prices_data:
            result[item["product_id"]] = {"updated": True, "errors": []}
        return result

    async def close(self):
        pass

    async def get_actions(self) -> list[dict]:
        return []

    async def get_auto_add_products(
        self, action_id: int, auto_add_date: str, limit: int = 100, offset: int = 0
    ) -> dict:
        return {"products": []}

    async def delete_auto_add_products(
        self, action_id: int, auto_add_date: str, product_ids: list[int]
    ) -> dict:
        return {"product_ids": []}

    async def update_price_timer(self, product_ids: list[int]) -> dict[int, dict]:
        return {pid: {"success": True, "error": None} for pid in product_ids}


@pytest.mark.asyncio
async def test_full_cycle_dry_run(tmp_path):
    import pandas as pd

    excel_data = {
        "SKU": ["123"],
        "Себестоимость": [1000],
        "Цена РИЦ": [2000],
        "Интервал 1": ["00:00-23:59"],
        "Стратегия 1": [3],
        "Процент 1": [0],
    }
    df = pd.DataFrame(excel_data)
    excel_path = tmp_path / "products.xlsx"
    df.to_excel(excel_path, index=False)

    db_path = tmp_path / "test.db"
    repo = SQLiteRepository(db_path)

    loader = ExcelLoader(excel_path)
    notifier = MailNotifier()

    mock_api = MockOzonApiClient()
    mock_api.set_product("123", 1, "off123", "Test Product")

    pricing = PricingData(
        product_id=1,
        price=2500.0,
        old_price=3000.0,
        marketing_seller_price=2500.0,
        net_price=1000.0,
        min_price=2000.0,
        external_index_data_price=2200.0,
        external_index_data_index=1.05,
        ozon_index_data_price=0,
        ozon_index_data_index=0,
        self_marketplaces_index_data_price=0,
        self_marketplaces_index_data_index=0,
        sales_percent_fbs=47,
        acquiring=0,
        fbs_first_mile_min_amount=10,
        fbs_first_mile_max_amount=30,
        fbs_direct_flow_trans_min_amount=89,
        fbs_direct_flow_trans_max_amount=377,
        fbs_deliv_to_customer_amount=25,
    )
    mock_api.set_price(1, pricing)

    deps = RepricingUseCaseDependencies(
        product_repo=repo,
        history_repo=repo,
        analytics_repo=repo,
        marginality_repo=repo,
        maintenance_repo=repo,
        api_client=mock_api,
        mail_notifier=notifier,
        loader=loader,
        pricing_rules=OzonPricingRules(),
    )
    use_case = RepricingUseCase(deps)
    stats = await use_case.execute(dry_run=True)

    assert stats["products_loaded"] == 1
    assert stats["prices_updated"] == 1
    assert stats["errors"] == []

    products = repo.get_all_products()
    assert len(products) == 1
    assert products[0].sku == "123"
    hist = repo.get_price_history("123")
    assert len(hist) == 1
    assert "customer_price" in hist[0]
