import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Any
import logging
import json
import re

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
        'competitor_urls': ['конкурент', 'ссылки_конкурентов'],
        'strategy': ['стратегия', 'strategy'],
        'strategy_percent': ['процент', 'percent', 'strategy_percent'],
        'schedule': ['расписание', 'schedule', 'intervals'],
    }

    # Количество колонок с конкурентами (Конкурент 1 ... Конкурент 5)
    COMPETITOR_COLUMNS_COUNT = 5

    def __init__(self, file_path: Path):
        self.file_path = file_path

    def load(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            logger.error(f"Файл {self.file_path} не найден")
            return []

        if self.file_path.suffix.lower() != '.xlsx':
            logger.error(f"Неподдерживаемый формат файла: {self.file_path.suffix}. Используйте .xlsx")
            return []

        # Читаем с указанием, что все столбцы - объекты, чтобы сохранить строки
        df = pd.read_excel(self.file_path, engine='openpyxl', dtype=str)
        # Удаляем возможные пробелы в названиях колонок
        df.columns = df.columns.str.lower().str.strip()

        # Дополнительно для SKU убираем пробелы
        for sku_col in ['sku', 'артикул', 'article', 'id', 'offer_id']:
            if sku_col in df.columns:
                df[sku_col] = df[sku_col].str.strip()
                break

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

        # 1. Простые поля через маппинг
        for std_name, synonyms in self.COLUMN_MAPPING.items():
            if std_name in ('competitor_urls', 'schedule'):
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

        # 3. Ссылки конкурентов
        competitor_urls = []
        for i in range(1, self.COMPETITOR_COLUMNS_COUNT + 1):
            col_candidates = [f'конкурент {i}', f'конкурент{i}', f'конкурент_{i}']
            for col in col_candidates:
                if col in columns:
                    url = row.get(col)
                    if pd.notna(url) and str(url).strip():
                        competitor_urls.append(str(url).strip())
                    break
        product['competitor_urls'] = competitor_urls

        # 4. Расписание: преобразуем в JSON, если задано в текстовом формате
        schedule_raw = None
        for syn in self.COLUMN_MAPPING['schedule']:
            if syn in columns:
                val = row.get(syn)
                if pd.notna(val):
                    schedule_raw = str(val).strip()
                    break
        product['schedule'] = self._parse_schedule(schedule_raw)

        # 5. Числовые поля
        for field in ['cost_price', 'min_price', 'current_price', 'strategy_percent']:
            val = product.get(field)
            if val is not None:
                try:
                    product[field] = float(val)
                except (ValueError, TypeError):
                    logger.warning(f"Не удалось преобразовать {field}='{val}' в число для {product['offer_id']}")

        # 6. Стратегия по умолчанию
        if product.get('strategy') is None:
            product['strategy'] = 3
        else:
            try:
                product['strategy'] = int(product['strategy'])
            except (ValueError, TypeError):
                product['strategy'] = 3

        if product.get('strategy_percent') is None:
            product['strategy_percent'] = 0.0

        return product

    def _parse_schedule(self, raw: Optional[str]) -> Optional[str]:
        """
        Преобразует расписание в JSON-строку для PriceCalculator.
        Поддерживает три формата:
        1) JSON-строка (начинается с '[') – возвращается как есть.
        2) Текстовый формат старого образца: "00:00 1 10 10:00 2 5 20:00 3"
        3) Человеко-читаемый формат с явными интервалами:
        "09:00-12:00:2:5; 13:00-17:00:1:3" (разделители ';' или ',')
        """
        if not raw:
            return None

        raw = raw.strip()
        if not raw:
            return None

        # 1) JSON
        if raw.startswith('['):
            try:
                json.loads(raw)
                return raw
            except json.JSONDecodeError:
                logger.warning(f"Некорректный JSON в расписании: {raw}")
                return None

        # 2) Явные интервалы с дефисом и двоеточиями
        # Шаблон: ЧЧ:ММ-ЧЧ:ММ:стратегия:процент
        if '-' in raw and ':' in raw:
            intervals = []
            # Разделяем по ';' или ','
            for part in re.split(r'[;,]\s*', raw):
                part = part.strip()
                if not part:
                    continue
                # Ожидаем формат: start-end:strategy:percent
                m = re.match(r'(\d{1,2}:\d{2})-(\d{1,2}:\d{2}):(\d):(\d+(?:\.\d+)?)', part)
                if m:
                    intervals.append({
                        'start': m.group(1),
                        'end': m.group(2),
                        'strategy': int(m.group(3)),
                        'percent': float(m.group(4))
                    })
                else:
                    logger.warning(f"Не удалось распознать интервал '{part}' в расписании")
            if intervals:
                return json.dumps(intervals, ensure_ascii=False)

        # 3) Старый формат: "00:00 1 10 10:00 2 5 20:00 3"
        parts = raw.split()
        if len(parts) % 3 == 0:
            intervals = []
            for i in range(0, len(parts), 3):
                time_str = parts[i]
                try:
                    strategy = int(parts[i+1])
                    percent = float(parts[i+2])
                except ValueError:
                    logger.warning(f"Ошибка преобразования стратегии/процента в '{parts[i:i+3]}'")
                    return None
                intervals.append({'start': time_str, 'strategy': strategy, 'percent': percent})

            # Устанавливаем конец для каждого интервала
            for i in range(len(intervals)):
                if i + 1 < len(intervals):
                    intervals[i]['end'] = intervals[i+1]['start']
                else:
                    intervals[i]['end'] = '23:59'
            return json.dumps(intervals, ensure_ascii=False)

        logger.warning(f"Не удалось распарсить расписание: {raw}")
        return None

    def update_current_price_in_file(self, offer_id: str, new_price: float) -> bool:
        try:
            from openpyxl import load_workbook
            wb = load_workbook(self.file_path)
            ws = wb.active
            if ws is None:
                logger.error("Не удалось получить активный лист из Excel-файла")
                return False

            header_row = 1
            # Найдём колонку "Ваша цена"
            current_price_col = None
            for col_idx, cell in enumerate(ws[header_row], start=1):
                if cell.value and str(cell.value).lower().strip() in ['ваша цена', 'current_price', 'price']:
                    current_price_col = col_idx
                    break
            if current_price_col is None:
                logger.error("Не найдена колонка 'Ваша цена'")
                return False

            # Найдём колонку SKU
            sku_col = None
            for col_idx, cell in enumerate(ws[header_row], start=1):
                if cell.value and str(cell.value).lower().strip() in ['sku', 'артикул', 'offer_id']:
                    sku_col = col_idx
                    break
            if sku_col is None:
                logger.error("Не найдена колонка 'SKU'")
                return False

            # Ищем строку с нужным SKU
            target_row = None
            target_sku_int = None
            try:
                target_sku_int = int(offer_id)
            except ValueError:
                pass

            for row_idx in range(2, ws.max_row + 1):
                sku_cell = ws.cell(row_idx, sku_col)
                cell_value = sku_cell.value
                if cell_value is None:
                    continue
                cell_str = str(cell_value).strip()
                if cell_str == offer_id:
                    target_row = row_idx
                    break
                if target_sku_int is not None:
                    try:
                        if int(float(cell_str)) == target_sku_int:
                            target_row = row_idx
                            break
                    except (ValueError, TypeError):
                        pass

            if target_row is None:
                logger.warning(f"SKU {offer_id} не найден в файле")
                return False

            ws.cell(target_row, current_price_col, value=new_price)
            wb.save(self.file_path)
            logger.info(f"Обновлена 'Ваша цена' для {offer_id} на {new_price}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления Excel: {e}")
            return False