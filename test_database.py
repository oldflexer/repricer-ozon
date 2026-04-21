import tempfile
from pathlib import Path
from src.database import Database

def test_database_operations():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        
        # Проверка создания таблиц
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "products" in tables
            assert "price_history" in tables
        
        # Добавление товара
        product = {
            "offer_id": "001",
            "product_name": "Test",
            "cost_price": 100,
            "min_price": 200,
            "current_price": 300,
            "strategy": 1,
            "strategy_percent": 5,
            "schedule": None,
            "competitor_urls": ["http://test.com"]
        }
        db.upsert_product(product)
        products = db.get_all_products()
        assert len(products) == 1
        assert products[0]['offer_id'] == '001'
        
        # Сохранение истории
        db.save_price_record("001", 250.0, 30.0, [100.0, None])
        avg = db.get_average_margin("001", 7)
        assert avg == 30.0
        
        last_run = db.get_last_run_time()
        assert last_run is not None