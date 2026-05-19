import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.loader import DataLoader
from core.entities import ProductInfo, StrategyInterval

logging.basicConfig(level=logging.INFO)

def test_load_products():
    data_file = Path(__file__).parent.parent / 'data' / 'products.xlsx'
    if not data_file.exists():
        print(f"❌ Файл {data_file} не найден, пропускаем тест.")
        return

    loader = DataLoader(data_file)
    products = loader.load()
    print(f"\n📦 Загружено товаров: {len(products)}\n")

    for idx, product in enumerate(products, 1):
        assert isinstance(product, ProductInfo)
        print(f"=== Товар #{idx} ===")
        print(f"SKU: {product.sku}")
        # product_name не загружается из Excel – должно быть None
        assert product.product_name is None
        print(f"Название: {product.product_name} (будет получено из API)")
        print(f"Себестоимость: {product.cost_price} ₽")
        print(f"Мин. цена (РИЦ): {product.min_price} ₽")
        print(f"Текущая цена (не загружается): {product.current_price}")
        intervals = loader.get_strategy_intervals(product)
        assert all(isinstance(inv, StrategyInterval) for inv in intervals)
        print(f"Интервалы стратегий: {intervals}")
        print()

if __name__ == "__main__":
    test_load_products()