import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DataLoader:
    """Загрузка данных из Excel-файла с таблицей товаров"""

    # Маппинг стандартных имён полей на возможные названия колонок в таблице заказчика
    COLUMN_MAPPING = {
        'offer_id': ['sku', 'артикул', 'article', 'id', 'offer_id'],
        'product_name': ['название', 'name', 'товар', 'product_name'],
        'cost_price': ['себестоимость', 'cost_price', 'cost'],
        'min_price': ['минимальная цена', 'min_price', 'min'],
        'current_price': ['ваша цена', 'current_price', 'price'],
        'competitor_urls': ['конкурент', 'ссылки_конкурентов'],  # префикс для поиска колонок 1..5
        'strategy': ['стратегия', 'strategy'],
        'strategy_percent': ['процент', 'percent', 'strategy_percent'],
        'schedule': ['расписание', 'schedule', 'intervals'],
    }

    # Количество колонок с конкурентами (Конкурент 1 ... Конкурент 5)
    COMPETITOR_COLUMNS_COUNT = 5

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> List[Dict[str, Any]]:
        """
        Загружает таблицу и возвращает список словарей с нормализованными ключами.
        """
        if not self.file_path.exists():
            logger.error(f"Файл {self.file_path} не найден")
            return []

        # Определяем формат (поддерживаем только .xlsx)
        if self.file_path.suffix.lower() != '.xlsx':
            logger.error(f"Неподдерживаемый формат файла: {self.file_path.suffix}. Используйте .xlsx")
            return []

        df = pd.read_excel(self.file_path, engine='openpyxl')

        # Приводим названия колонок к нижнему регистру и убираем лишние пробелы
        df.columns = df.columns.str.lower().str.strip()

        products = []
        for _, row in df.iterrows():
            product = self._parse_row(row, df.columns)
            if product:
                products.append(product)

        logger.info(f"Загружено {len(products)} товаров")
        return products

    def _parse_row(self, row: pd.Series, columns: pd.Index) -> Optional[Dict[str, Any]]:
        """Парсит одну строку таблицы в словарь с нормализованными ключами."""
        product = {}

        # 1. Обрабатываем простые поля через маппинг
        for std_name, synonyms in self.COLUMN_MAPPING.items():
            if std_name == 'competitor_urls':
                continue  # обработаем отдельно
            value = None
            for syn in synonyms:
                if syn in columns:
                    val = row.get(syn)
                    if pd.notna(val):
                        value = val
                        break
            product[std_name] = value

        # 2. Обязательное поле offer_id
        if not product.get('offer_id'):
            logger.warning("Пропущена строка без SKU/offer_id")
            return None

        # 3. Собираем ссылки конкурентов из колонок "конкурент 1" ... "конкурент 5"
        competitor_urls = []
        for i in range(1, self.COMPETITOR_COLUMNS_COUNT + 1):
            # Ищем колонку с именем "конкурент N" или "конкурентN"
            col_candidates = [f'конкурент {i}', f'конкурент{i}', f'конкурент_{i}']
            for col in col_candidates:
                if col in columns:
                    url = row.get(col)
                    if pd.notna(url) and str(url).strip():
                        competitor_urls.append(str(url).strip())
                    break
        product['competitor_urls'] = competitor_urls

        # 4. Преобразуем числовые значения (если они есть)
        for field in ['cost_price', 'min_price', 'current_price', 'strategy_percent']:
            val = product.get(field)
            if val is not None:
                try:
                    product[field] = float(val)
                except (ValueError, TypeError):
                    logger.warning(f"Не удалось преобразовать {field}='{val}' в число для {product['offer_id']}")

        # 5. Если стратегия не указана, по умолчанию 3 (равная цена)
        if product.get('strategy') is None:
            product['strategy'] = 3
        else:
            try:
                product['strategy'] = int(product['strategy'])
            except (ValueError, TypeError):
                product['strategy'] = 3

        if product.get('strategy_percent') is None:
            product['strategy_percent'] = 0.0

        # 6. Расписание (schedule) оставляем как строку, если есть

        return product