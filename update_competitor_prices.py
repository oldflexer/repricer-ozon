import random
from pathlib import Path
import time
import pandas as pd
import logging
from infrastructure.ozon_parser import OzonPriceParser
from config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_COMPETITORS = 5

def update_prices(excel_path: Path):
    """Обновляет цены конкурентов в Excel-файле."""
    if not excel_path.exists():
        logger.error(f"Файл {excel_path} не найден")
        return

    df = pd.read_excel(excel_path, engine='openpyxl')
    # Убедимся, что колонки есть
    price_cols = [f'Цена конкурента {i}' for i in range(1, MAX_COMPETITORS + 1)]

    # Добавляем колонки для цен, если их нет
    for col in price_cols:
        if col not in df.columns:
            df[col] = None

    parser = OzonPriceParser(headless=True)
    try:
        for idx, row in df.iterrows():
            for i in range(1, MAX_COMPETITORS + 1):
                url = row.get(f'Конкурент {i}')
                if pd.isna(url) or not url:
                    continue
                # Проверяем, не обновляли ли уже цену в этом запуске (кэш в памяти)
                # Если хотим обновлять всегда, можно убрать проверку
                price_col = f'Цена конкурента {i}'
                if pd.notna(row.get(price_col)):
                    # уже есть цена, пропускаем (можно перезаписывать, если нужно)
                    continue
                logger.info(f"Парсинг цены для SKU {row.get('SKU')}, конкурент {i}...")
                price = parser.get_price(url)
                if price is not None:
                    df.at[idx, price_col] = price
                else:
                    df.at[idx, price_col] = None
                    logger.warning(f"Не удалось получить цену для {url}")
                # Задержка между запросами
                time.sleep(random.uniform(2, 4))
    finally:
        parser.close()

    # Сохраняем изменения
    df.to_excel(excel_path, index=False, engine='openpyxl')
    logger.info(f"Файл {excel_path} обновлён.")

if __name__ == '__main__':
    # Для каждого магазина можно запускать отдельно
    # Например, для airglass:
    # update_prices(Path(__file__).parent / 'data' / 'products_airglass.xlsx')
    # update_prices(Path(__file__).parent / 'data' / 'products_amiato.xlsx')
    pass