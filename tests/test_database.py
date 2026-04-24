import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import Database


def test_database_operations():
    print("Запуск тестов базы данных...")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)

        # Проверка создания таблиц
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert "products" in tables, "Таблица products не создана"
            assert "price_history" in tables, "Таблица price_history не создана"
        print(" ✅ Таблицы созданы корректно")

        # Добавление товара
        product = {
            "sku": "001",
            "product_name": "Test",
            "cost_price": 100,
            "min_price": 200,
            "current_price": 300,
        }
        db.upsert_product(product)
        products = db.get_all_products()
        assert len(products) == 1, f"Ожидался 1 товар, получено {len(products)}"
        assert products[0]['offer_id'] == '001', "SKU не совпадает"
        print(" ✅ Товар добавлен и прочитан")

        # Сохранение истории
        db.save_price_record("001", 250.0, 30.0)
        avg = db.get_average_margin("001", 7)
        assert avg == 30.0, f"Ожидалась средняя маржа 30.0, получено {avg}"
        print(" ✅ История цены сохранена и средняя маржа вычислена")

        last_run = db.get_last_run_time()
        assert last_run is not None, "Время последнего запуска не определено"
        print(" ✅ Время последнего запуска получено")

    print("Все тесты базы данных пройдены успешно!")


if __name__ == "__main__":
    test_database_operations()