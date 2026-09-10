"""
Unit tests for excel_loader.py
"""

from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from core.entities import ProductInfo
from core.enums import StrategyType
from infrastructure.excel_loader import ExcelLoader


class TestExcelLoader:
    """Tests for ExcelLoader class."""

    @pytest.fixture
    def mock_file_path(self, tmp_path):
        """Create a temporary file path."""
        return tmp_path / "test_products.xlsx"

    @pytest.fixture
    def loader(self, mock_file_path):
        """Create ExcelLoader instance with mock file."""
        return ExcelLoader(mock_file_path)

    def test_init(self, loader, mock_file_path):
        """Test initialization."""
        assert loader.file_path == mock_file_path
        assert loader._strategies == {}

    def test_load_file_not_found(self, loader):
        """Test load() when file doesn't exist."""
        products, warnings = loader.load()
        assert products == []
        assert "Файл Excel не найден" in warnings[0]

    def test_load_unsupported_format(self, loader, tmp_path):
        """Test load() with unsupported format."""
        loader.file_path = tmp_path / "test.csv"
        loader.file_path.touch()
        products, warnings = loader.load()
        assert products == []
        assert "Неподдерживаемый формат" in warnings[0]

    @patch("infrastructure.excel_loader.pd.read_excel")
    def test_load_no_sku_column(self, mock_read_excel, loader, tmp_path):
        """Test load() when SKU column is missing."""
        loader.file_path.touch()
        mock_df = pd.DataFrame({"name": ["Product 1"]})
        mock_read_excel.return_value = mock_df

        products, warnings = loader.load()
        assert products == []
        assert any("SKU" in w for w in warnings)

    @patch("infrastructure.excel_loader.pd.read_excel")
    def test_load_duplicate_sku(self, mock_read_excel, loader, tmp_path):
        """Test load() with duplicate SKUs."""
        loader.file_path.touch()
        mock_df = pd.DataFrame({"sku": ["SKU1", "SKU1"], "себестоимость": [100, 100]})
        mock_read_excel.return_value = mock_df

        products, warnings = loader.load()
        assert products == []
        assert any("дубликаты SKU" in w for w in warnings)

    @patch("infrastructure.excel_loader.pd.read_excel")
    def test_load_success(self, mock_read_excel, loader, tmp_path):
        """Test successful load with valid data."""
        loader.file_path.touch()
        # Patch the setting to match the lowercased column names
        with patch("infrastructure.excel_loader.settings") as mock_settings:
            mock_settings.COMPETITOR_PRICE_COLUMN_PREFIX = "цена"
            mock_settings.MAX_COMPETITORS = 5
            mock_settings.SCHEDULE_INTERVALS_COUNT = 4

            mock_df = pd.DataFrame(
                {
                    "sku": ["SKU1", "SKU2"],
                    "себестоимость": [100.0, 200.0],
                    "цена риц": [150.0, 250.0],
                    "цена 1": [180.0, 280.0],
                    "интервал 1": ["00:00-23:59", "00:00-23:59"],
                    "стратегия 1": [3, 3],
                }
            )
            mock_read_excel.return_value = mock_df

            products, warnings = loader.load()
            assert len(products) == 2
            assert products[0].sku == "SKU1"
            assert products[0].cost_price == 100.0
            assert products[0].min_price == 150.0
            assert products[0].competitor_min_price == 180.0

    @patch("infrastructure.excel_loader.pd.read_excel")
    def test_load_zero_cost_price(self, mock_read_excel, loader, tmp_path):
        """Test load() skips products with zero/negative cost price."""
        loader.file_path.touch()
        mock_df = pd.DataFrame(
            {
                "sku": ["SKU1", "SKU2"],
                "себестоимость": [100.0, 0.0],
                "цена риц": [150.0, 250.0],
            }
        )
        mock_read_excel.return_value = mock_df

        products, warnings = loader.load()
        assert len(products) == 1
        assert products[0].sku == "SKU1"
        assert any("себестоимость" in w and "SKU2" in w for w in warnings)

    @patch("infrastructure.excel_loader.Path.exists")
    def test_update_product_in_file_not_found(self, mock_exists, loader):
        """Test update_product_in_file when SKU not found."""
        mock_exists.return_value = True

        # We need to patch openpyxl.load_workbook since it's imported locally in the method
        with patch("openpyxl.load_workbook") as mock_load_workbook:
            mock_ws = MagicMock()
            mock_ws.max_row = 2

            header_cells = [Mock(value="sku"), Mock(value="name"), Mock(value="ваша цена")]
            data_cells = [Mock(value="OTHER"), Mock(value="Product"), Mock(value=None)]

            def iter_rows(min_row=1, max_row=None, values_only=False):
                if min_row == 1:
                    return iter(header_cells)
                return iter(data_cells)

            mock_ws.iter_rows = iter_rows
            mock_ws.cell = Mock(
                side_effect=lambda row, col: (
                    header_cells[col - 1] if row == 1 else data_cells[col - 1]
                )
            )

            mock_wb = MagicMock()
            mock_wb.active = mock_ws
            mock_load_workbook.return_value = mock_wb

            result = loader.update_product_in_file("SKU1", {"current_price": 100})
            assert result is False

    def test_parse_strategy_value(self):
        """Test _parse_strategy_value with various inputs."""
        assert ExcelLoader._parse_strategy_value(1) == StrategyType.BELOW
        assert ExcelLoader._parse_strategy_value(2) == StrategyType.ABOVE
        assert ExcelLoader._parse_strategy_value(3) == StrategyType.EQUAL
        assert ExcelLoader._parse_strategy_value("ниже") == StrategyType.BELOW
        assert ExcelLoader._parse_strategy_value("выше") == StrategyType.ABOVE
        assert ExcelLoader._parse_strategy_value("равная") == StrategyType.EQUAL
        assert ExcelLoader._parse_strategy_value("НИЖЕ") == StrategyType.BELOW
        assert ExcelLoader._parse_strategy_value(None) == StrategyType.EQUAL
        assert ExcelLoader._parse_strategy_value("unknown") == StrategyType.EQUAL

    def test_find_column(self, loader):
        """Test _find_column finds correct column."""
        columns = pd.Index(["sku", "себестоимость", "цена риц", "интервал 1"])
        assert loader._find_column(columns, ["sku", "артикул"]) == "sku"
        assert loader._find_column(columns, ["cost"]) is None
        assert loader._find_column(columns, ["цена риц", "min_price"]) == "цена риц"

    def test_get_float(self, loader):
        """Test _get_float extracts float values."""
        row = pd.Series({"a": "100.5", "b": "abc", "c": None})
        columns = pd.Index(["a", "b", "c"])

        assert loader._get_float(row, columns, ["a"], 0.0) == 100.5
        assert loader._get_float(row, columns, ["b"], 0.0) == 0.0
        assert loader._get_float(row, columns, ["c"], 0.0) == 0.0
        assert loader._get_float(row, columns, ["missing"], 42.0) == 42.0

    def test_build_excel_updates(self, loader):
        """Test build_excel_updates creates correct dict."""
        product = ProductInfo(sku="SKU1", cost_price=100, min_price=150, old_price=200)

        class MockResult:
            result_target_price = 180.0
            marginality = 25.5
            log_details = {"discount_coef": 0.9}

        result = MockResult()
        updates = loader.build_excel_updates(
            product, result, marginality_week=24.0, marginality_month=23.5, old_price_update=190
        )

        assert updates["current_price"] == 162
        assert updates["min_price"] == 150
        assert updates["margin"] == 25.5
        assert updates["margin_week"] == 24.0
        assert updates["margin_month"] == 23.5
        assert updates["old_price"] == 190


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
