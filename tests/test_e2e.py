"""
End-to-End tests for critical repricer paths.

Tests cover:
1. Full repricing cycle (dry-run -> calculate -> persist)
2. Competitor parsing flow (Excel -> parse -> update)
3. Own products parsing flow (DB -> parse -> update discount_coef)
4. Price calculation with all 3 discount_coef sources
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.domain.pricing_rules import OzonPricingRules
from core.entities import PricingData, ProductInfo
from core.use_cases import RepricingUseCase, RepricingUseCaseDependencies
from core.use_cases.parse_competitor_prices import ParseCompetitorPricesUseCase
from core.use_cases.parse_own_products import ParseOwnProductsUseCase
from core.pipeline.steps import ParseOwnProductsStep, LoadProductsStep, EnrichProductIdsStep, FetchPricingDataStep, CalculatePricesStep, PersistToExcelStep, SubmitPricesToOzonStep, SaveHistoryStep, SendReportStep, CleanupDatabaseStep
from core.services.price_calculation import PriceCalculationService
from infrastructure.db import SQLiteRepository
from infrastructure.excel_loader import ExcelLoader
from infrastructure.mail_notifier import MailNotifier


class MockOzonApiClient:
    """Mock Ozon API client for testing."""

    def __init__(self):
        self.products_map = {}
        self.prices_map = {}
        self.update_prices_called = False
        self.update_prices_args = None

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
        self.update_prices_called = True
        self.update_prices_args = prices_data
        result = {}
        for item in prices_data:
            result[item["product_id"]] = {"updated": True, "errors": []}
        return result

    async def close(self):
        pass

    async def get_actions(self):
        return []

    async def get_auto_add_products(
        self, action_id: int, auto_add_date: str, limit: int = 100, offset: int = 0
    ):
        return {"products": []}

    async def delete_auto_add_products(
        self, action_id: int, auto_add_date: str, product_ids: list[int]
    ):
        return {"product_ids": []}

    async def update_price_timer(self, product_ids: list[int]):
        return {pid: {"success": True, "error": None} for pid in product_ids}


def create_test_excel(tmp_path, products_data):
    """Create test Excel file with products data."""
    import pandas as pd
    df = pd.DataFrame(products_data)
    excel_path = tmp_path / "products.xlsx"
    df.to_excel(excel_path, index=False)
    return excel_path


def create_test_db(tmp_path):
    """Create test database."""
    db_path = tmp_path / "test.db"
    return SQLiteRepository(db_path)


def create_product_info(sku, product_id, offer_id, product_name, cost_price, min_price, **kwargs):
    """Create ProductInfo with defaults."""
    defaults = {
        "sku": sku,
        "product_id": product_id,
        "offer_id": offer_id,
        "product_name": product_name,
        "cost_price": cost_price,
        "min_price": min_price,
        "current_price": cost_price * 2,
        "old_price": cost_price * 1.5,
        "real_customer_price": None,
        "competitor_min_price": None,
        "discount_coef": None,
        "discount_coef_source": None,
        "discount_coef_updated_at": None,
    }
    defaults.update(kwargs)
    return ProductInfo(**defaults)


def create_pricing_data(product_id=1, marketing_seller_price=2500.0, **kwargs):
    """Create PricingData with defaults."""
    defaults = {
        "product_id": product_id,
        "price": 2500.0,
        "old_price": 3000.0,
        "marketing_seller_price": marketing_seller_price,
        "net_price": 1000.0,
        "min_price": 2000.0,
        "external_index_data_price": 2200.0,
        "external_index_data_index": 1.05,
        "ozon_index_data_price": 0,
        "ozon_index_data_index": 0,
        "self_marketplaces_index_data_price": 0,
        "self_marketplaces_index_data_index": 0,
        "sales_percent_fbs": 47,
        "acquiring": 0,
        "fbs_first_mile_min_amount": 10,
        "fbs_first_mile_max_amount": 30,
        "fbs_direct_flow_trans_min_amount": 89,
        "fbs_direct_flow_trans_max_amount": 377,
        "fbs_deliv_to_customer_amount": 25,
    }
    defaults.update(kwargs)
    return PricingData(**defaults)


class TestFullRepricingCycle:
    """Test full repricing cycle."""

    @pytest.mark.asyncio
    async def test_full_cycle_dry_run(self, tmp_path):
        """Test complete repricing cycle in dry-run mode."""
        excel_data = {
            "SKU": ["123", "456"],
            "Себестоимость": [1000, 1500],
            "Цена РИЦ": [2000, 2500],
            "Интервал 1": ["00:00-23:59", "00:00-23:59"],
            "Стратегия 1": [3, 3],  # BELOW
            "Процент 1": [5, 5],
        }
        excel_path = create_test_excel(tmp_path, excel_data)
        repo = create_test_db(tmp_path)
        loader = ExcelLoader(excel_path)
        notifier = MailNotifier()

        mock_api = MockOzonApiClient()
        mock_api.set_product("123", 1, "off123", "Product 1")
        mock_api.set_product("456", 2, "off456", "Product 2")

        pricing1 = create_pricing_data(1, marketing_seller_price=2500.0)
        pricing2 = create_pricing_data(2, marketing_seller_price=3000.0)
        mock_api.set_price(1, pricing1)
        mock_api.set_price(2, pricing2)

        parse_own_products_use_case = MagicMock(spec=ParseOwnProductsUseCase)
        parse_own_products_use_case.execute = AsyncMock(
            return_value={"updated": 0, "errors": 0, "skipped": 0}
        )

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
            parse_own_products_use_case=parse_own_products_use_case,
        )
        use_case = RepricingUseCase(deps)
        stats = await use_case.execute(dry_run=True)

        assert stats["products_loaded"] == 2
        assert stats["prices_updated"] == 2
        assert stats["errors"] == []

        products = repo.get_all_products()
        assert len(products) == 2

        # Verify history was saved
        for p in products:
            hist = repo.get_price_history(p.sku)
            assert len(hist) == 1
            assert "customer_price" in hist[0]

    @pytest.mark.asyncio
    async def test_full_cycle_with_price_update(self, tmp_path):
        """Test complete repricing cycle with actual price updates."""
        excel_data = {
            "SKU": ["123"],
            "Себестоимость": [1000],
            "Цена РИЦ": [2000],
            "Интервал 1": ["00:00-23:59"],
            "Стратегия 1": [3],
            "Процент 1": [5],
        }
        excel_path = create_test_excel(tmp_path, excel_data)
        repo = create_test_db(tmp_path)
        loader = ExcelLoader(excel_path)
        notifier = MailNotifier()

        mock_api = MockOzonApiClient()
        mock_api.set_product("123", 1, "off123", "Product 1")
        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        mock_api.set_price(1, pricing)

        parse_own_products_use_case = MagicMock(spec=ParseOwnProductsUseCase)
        parse_own_products_use_case.execute = AsyncMock(
            return_value={"updated": 0, "errors": 0, "skipped": 0}
        )

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
            parse_own_products_use_case=parse_own_products_use_case,
        )
        use_case = RepricingUseCase(deps)
        stats = await use_case.execute(dry_run=False)

        assert stats["products_loaded"] == 1
        assert stats["prices_updated"] == 1
        assert mock_api.update_prices_called


class TestCompetitorParsingFlow:
    """Test competitor parsing flow."""

    @pytest.mark.asyncio
    async def test_competitor_parsing_updates_excel(self, tmp_path):
        """Test competitor parsing updates Excel with new prices."""
        import pandas as pd
        from config import settings

        # Create Excel with competitor URLs (using correct column names from settings)
        excel_data = {
            "SKU": ["123", "456"],
            "Себестоимость": [1000, 1500],
            "Цена РИЦ": [2000, 2500],
            "Конкурент 1": ["https://ozon.ru/product/111/", "https://ozon.ru/product/222/"],
            "Цена 1": [0, 0],
        }
        excel_path = create_test_excel(tmp_path, excel_data)

        # Create mock parser and pass it to use case
        mock_parser = MagicMock()
        mock_parser.get_price.side_effect = [1500.0, 1800.0]  # New prices

        use_case = ParseCompetitorPricesUseCase(parser=mock_parser)

        # Patch settings.DATA_FILE to use test Excel file
        original_data_file = settings.DATA_FILE
        settings.DATA_FILE = str(excel_path)
        try:
            stats = await use_case.execute(dry_run=False)
        finally:
            settings.DATA_FILE = original_data_file

        assert stats["updated"] == 2
        assert stats["errors"] == 0

        # Verify Excel was updated
        df = pd.read_excel(excel_path)
        assert df.loc[0, "Цена 1"] == 1500.0
        assert df.loc[1, "Цена 1"] == 1800.0

    @pytest.mark.asyncio
    async def test_competitor_parsing_handles_errors(self, tmp_path):
        """Test competitor parsing handles errors gracefully."""
        import pandas as pd
        from config import settings

        excel_data = {
            "SKU": ["123", "456"],
            "Себестоимость": [1000, 1500],
            "Цена РИЦ": [2000, 2500],
            "Конкурент 1": ["https://ozon.ru/product/111/", "https://ozon.ru/product/222/"],
            "Цена 1": [0, 0],
        }
        excel_path = create_test_excel(tmp_path, excel_data)

        mock_parser = MagicMock()
        mock_parser.get_price.side_effect = [1500.0, None]  # Second fails

        use_case = ParseCompetitorPricesUseCase(parser=mock_parser)

        original_data_file = settings.DATA_FILE
        settings.DATA_FILE = str(excel_path)
        try:
            stats = await use_case.execute(dry_run=False)
        finally:
            settings.DATA_FILE = original_data_file

        assert stats["updated"] == 1
        assert stats["errors"] == 1

        df = pd.read_excel(excel_path)
        assert df.loc[0, "Цена 1"] == 1500.0
        assert df.loc[1, "Цена 1"] == 0  # Unchanged


class TestOwnProductsParsingFlow:
    """Test own products parsing flow."""

    @pytest.mark.asyncio
    async def test_own_products_parsing_updates_db(self, tmp_path):
        """Test own products parsing updates DB with real_customer_price and discount_coef."""
        repo = create_test_db(tmp_path)

        # Add products to DB
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))
        repo.upsert_product(create_product_info("456", 2, "off456", "Product 2", 1500.0, 2500.0))

        mock_api = MockOzonApiClient()
        mock_api.set_product("123", 1, "off123", "Product 1")
        mock_api.set_product("456", 2, "off456", "Product 2")

        # Pricing with marketing_seller_price
        pricing1 = create_pricing_data(1, marketing_seller_price=2500.0)
        pricing2 = create_pricing_data(2, marketing_seller_price=3000.0)
        mock_api.set_price(1, pricing1)
        mock_api.set_price(2, pricing2)

        with patch("infrastructure.ozon_competitor.OzonPriceParser") as mock_parser_class:
            mock_parser = MagicMock()
            # Return real_customer_price (e.g., 2000 for product with marketing_seller_price 2500)
            # discount_coef = 2000/2500 = 0.8
            mock_parser.get_price.side_effect = [2000.0, 2400.0]
            mock_parser_class.return_value = mock_parser

            use_case = ParseOwnProductsUseCase(
                product_repo=repo,
                api_client=mock_api,
            )
            stats = await use_case.execute(dry_run=False)

        assert stats["updated"] == 2
        assert stats["errors"] == 0

        # Verify DB was updated
        products = repo.get_all_products()
        for p in products:
            assert p.real_customer_price is not None
            assert p.discount_coef is not None
            assert p.discount_coef_source == "parsed"
            # discount_coef = real_customer_price / marketing_seller_price
            if p.sku == "123":
                assert abs(p.discount_coef - 0.8) < 0.01
            else:
                assert abs(p.discount_coef - 0.8) < 0.01

    @pytest.mark.asyncio
    async def test_own_products_parsing_skips_out_of_stock(self, tmp_path):
        """Test own products parsing skips out-of-stock products."""
        repo = create_test_db(tmp_path)
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))

        mock_api = MockOzonApiClient()
        mock_api.set_product("123", 1, "off123", "Product 1")
        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        mock_api.set_price(1, pricing)

        with patch("infrastructure.ozon_competitor.OzonPriceParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.get_price.return_value = -1.0  # Out of stock
            mock_parser_class.return_value = mock_parser

            use_case = ParseOwnProductsUseCase(
                product_repo=repo,
                api_client=mock_api,
            )
            stats = await use_case.execute(dry_run=False)

        assert stats["updated"] == 0
        assert stats["skipped"] == 1


class TestDiscountCoefPrioritization:
    """Test discount_coef prioritization logic (3 tiers)."""

    def test_priority_1_parsed_real_customer_price(self, tmp_path):
        """Test priority 1: parsed real_customer_price / marketing_seller_price."""
        repo = create_test_db(tmp_path)
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))

        # Set real_customer_price and discount_coef from parsing
        repo.update_real_customer_price("123", 2000.0)
        repo.update_discount_coef("123", 0.8, "parsed")

        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        calc = PriceCalculationService(OzonPricingRules())

        result = calc.calculate(
            sku="123",
            pricing=pricing,
            rip=2000.0,
            intervals=[],
            product_repo=repo,
        )

        # Should use parsed discount_coef (0.8)
        assert result.discount_coef == 0.8
        assert result.discount_coef_source == "parsed"

    def test_priority_2_historical_discount_coef(self, tmp_path):
        """Test priority 2: historical discount_coef from DB."""
        repo = create_test_db(tmp_path)
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))

        # Set only historical discount_coef (no real_customer_price)
        repo.update_discount_coef("123", 0.75, "historical")

        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        calc = PriceCalculationService(OzonPricingRules())

        result = calc.calculate(
            sku="123",
            pricing=pricing,
            rip=2000.0,
            intervals=[],
            product_repo=repo,
        )

        # Should use historical discount_coef (0.75)
        assert result.discount_coef == 0.75
        assert result.discount_coef_source == "historical"

    def test_priority_3_default_discount_coef(self, tmp_path):
        """Test priority 3: default discount_coef from settings."""
        repo = create_test_db(tmp_path)
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))

        # No discount_coef in DB at all
        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        calc = PriceCalculationService(OzonPricingRules())

        result = calc.calculate(
            sku="123",
            pricing=pricing,
            rip=2000.0,
            intervals=[],
            product_repo=repo,
        )

        # Should use default (0.5)
        assert result.discount_coef == 0.5
        assert result.discount_coef_source == "default"

    def test_parsed_takes_precedence_over_historical(self, tmp_path):
        """Test parsed discount_coef takes precedence over historical."""
        repo = create_test_db(tmp_path)
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))

        # Set both historical and parsed (parsed should win)
        repo.update_discount_coef("123", 0.6, "historical")
        repo.update_real_customer_price("123", 2000.0)
        repo.update_discount_coef("123", 0.8, "parsed")

        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        calc = PriceCalculationService(OzonPricingRules())

        result = calc.calculate(
            sku="123",
            pricing=pricing,
            rip=2000.0,
            intervals=[],
            product_repo=repo,
        )

        # Parsed should win
        assert result.discount_coef == 0.8
        assert result.discount_coef_source == "parsed"


class TestPipelineSteps:
    """Test individual pipeline steps."""

    @pytest.mark.asyncio
    async def test_parse_own_products_step_in_pipeline(self, tmp_path):
        """Test ParseOwnProductsStep executes in pipeline."""
        from core.pipeline.orchestrator import create_repricing_pipeline
        from core.pipeline.steps import PipelineContext

        repo = create_test_db(tmp_path)
        repo.upsert_product(create_product_info("123", 1, "off123", "Product 1", 1000.0, 2000.0))

        mock_api = MockOzonApiClient()
        mock_api.set_product("123", 1, "off123", "Product 1")
        pricing = create_pricing_data(1, marketing_seller_price=2500.0)
        mock_api.set_price(1, pricing)

        with patch("infrastructure.ozon_competitor.OzonPriceParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.get_price.return_value = 2000.0
            mock_parser_class.return_value = mock_parser

            # Create use case directly with repo and api_client
            parse_own_products_use_case = ParseOwnProductsUseCase(
                product_repo=repo,
                api_client=mock_api,
            )

            deps = RepricingUseCaseDependencies(
                product_repo=repo,
                history_repo=repo,
                analytics_repo=repo,
                marginality_repo=repo,
                maintenance_repo=repo,
                api_client=mock_api,
                mail_notifier=MailNotifier(),
                loader=ExcelLoader(tmp_path / "dummy.xlsx"),
                pricing_rules=OzonPricingRules(),
                parse_own_products_use_case=parse_own_products_use_case,
            )

            # Create pipeline with dry_run=True
            from core.pipeline.orchestrator import PipelineOrchestrator
            pipeline = PipelineOrchestrator(
                steps=[
                    ParseOwnProductsStep(deps.parse_own_products_use_case, True),
                    LoadProductsStep(deps.loader, deps.product_repo),
                    EnrichProductIdsStep(deps.api_client),
                    FetchPricingDataStep(deps.api_client),
                    CalculatePricesStep(deps.calculator or PriceCalculationService(deps.pricing_rules), deps.pricing_rules),
                    PersistToExcelStep(deps.loader, deps.pricing_rules),
                    SubmitPricesToOzonStep(deps.api_client, deps.pricing_rules),
                    SaveHistoryStep(
                        deps.product_repo, deps.history_repo, deps.analytics_repo, deps.marginality_repo
                    ),
                    SendReportStep(deps.mail_notifier),
                    CleanupDatabaseStep(deps.maintenance_repo),
                ]
            )
            context = PipelineContext(dry_run=True)

            # Execute pipeline
            await pipeline.execute(context)

            # Verify parse_own_products step ran
            products = repo.get_all_products()
            assert products[0].real_customer_price == 2000.0
            assert products[0].discount_coef_source == "parsed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])