import logging
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.loader import DataLoader

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_load_products():
    """Тест загрузки товаров из таблицы products.xlsx"""
    
    # Путь к файлу данных относительно корня проекта (tests/ -> родитель -> data/products.xlsx)
    data_file = Path(__file__).parent.parent / 'data' / 'products.xlsx'
    
    if not data_file.exists():
        print(f"❌ Файл {data_file} не найден!")
        print("   Поместите файл products.xlsx в папку data/")
        return
    
    loader = DataLoader(data_file)
    products = loader.load()
    
    print(f"\n📦 Загружено товаров: {len(products)}\n")
    
    for idx, product in enumerate(products, 1):
        print(f"=== Товар #{idx} ===")
        # Теперь поле называется 'sku'
        print(f"SKU: {product.get('sku')}")
        print(f"Название: {product.get('product_name')}")
        print(f"Себестоимость: {product.get('cost_price')} ₽")
        print(f"Мин. цена: {product.get('min_price')} ₽")
        print(f"Текущая цена: {product.get('current_price')} ₽")
        # Поля strategy и strategy_percent больше нет в product, теперь intervals
        intervals = product.get('intervals', [])
        print(f"Интервалы стратегий: {intervals}")
        
        urls = product.get('competitor_urls', [])
        print(f"Ссылок на конкурентов: {len(urls)}")
        for i, url in enumerate(urls, 1):
            print(f"  {i}. {url}")
        print()

if __name__ == "__main__":
    test_load_products()