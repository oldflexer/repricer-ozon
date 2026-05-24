import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import gc
import sqlite3
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.db import SQLiteRepository
from core.entities import ProductInfo, StrategyInterval, PricingData, PriceCalculationResult

def test_database_operations():
    tmp_dir = tempfile.mkdtemp()
    db_path = Path(tmp_dir) / "test.db"

    try:
        repo = SQLiteRepository(db_path)

        # Проверка таблиц (в product есть real_customer_price)
        with repo._get_connection() as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            assert "product" in tables
            assert "product_strategy" in tables
            assert "product_price_history" in tables
            assert "product_marginality_history" in tables
            # Проверка колонок в product
            cols = [row[1] for row in conn.execute("PRAGMA table_info(product)")]
            assert "real_customer_price" in cols
            # Проверка колонок в product_price_history
            cols = [row[1] for row in conn.execute("PRAGMA table_info(product_price_history)")]
            assert "real_price" in cols
        print(" ✅ Таблицы созданы корректно с новыми колонками")

        # Добавление товара с real_customer_price
        product = ProductInfo(sku="001", product_name="Test", min_price=200.0, cost_price=150.0,
                              product_id=10, offer_id="off1", real_customer_price=2300.0)
        repo.upsert_product(product)
        all_products = repo.get_all_products()
        assert len(all_products) == 1
        assert all_products[0].sku == "001"
        assert all_products[0].real_customer_price == 2300.0
        print(" ✅ Товар с real_customer_price сохранён")

        # Тест update_real_customer_price
        repo.update_real_customer_price("001", 2400.0)
        updated = repo.get_all_products()[0]
        assert updated.real_customer_price == 2400.0
        print(" ✅ update_real_customer_price работает")

        # Сохранение стратегий
        intervals = [StrategyInterval(start="00:00", end="12:00", strategy_type=1, percent=5.0),
                     StrategyInterval(start="12:00", end="23:59", strategy_type=3, percent=0.0)]
        repo.set_strategies("001", intervals)
        strats = repo.get_strategies("001")
        assert len(strats) == 2
        print(" ✅ Стратегии сохранены и загружены")

        # Сохранение истории цен с real_price
        pricing = PricingData(
            product_id=10,
            price=500.0,
            old_price=600.0,
            marketing_seller_price=480.0,
            net_price=400.0,
            min_price=400.0,
            external_index_data_price=490.0,
            external_index_data_index=0.8,
            ozon_index_data_price=470.0,
            ozon_index_data_index=0.82,
            self_marketplaces_index_data_price=480.0,
            self_marketplaces_index_data_index=0.81
        )
        result = PriceCalculationResult(
            sku="001",
            target_min_price=450.0,
            strategy_price=470.0,
            target_strategy_price=520.0,
            result_target_price=520.0,
            marginality=0.2,
            log_details={"discount_coef": 0.9}
        )
        repo.save_price_history("001", pricing, result, real_price=2400.0)
        # Проверяем, что real_price сохранилась
        hist = repo.get_price_history("001")
        assert len(hist) == 1
        assert hist[0]["customer_price"] == 2400.0  # должно быть real_price
        print(" ✅ История цен с real_price сохранена и правильно читается")

        # Старая запись без real_price (должна вычисляться через discount_coef)
        repo.save_price_history("001", pricing, result)  # без real_price
        hist = repo.get_price_history("001")
        assert len(hist) == 2
        # последняя запись без real_price: customer_price = result_target_price * discount_coef
        assert hist[-1]["customer_price"] == 520.0 * 0.9
        print(" ✅ История без real_price корректно вычисляется")

        repo.save_marginality("001", 0.2, 0.18, 0.19)
        avg_week = repo.get_average_marginality("001", 7)
        assert avg_week == 0.2

        last_run = repo.get_last_run_time()
        assert isinstance(last_run, datetime)

        del repo
        gc.collect()
        try:
            conn = sqlite3.connect(str(db_path))
            conn.close()
        except Exception:
            pass

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("✅ Все тесты базы данных пройдены успешно!")

if __name__ == "__main__":
    test_database_operations()