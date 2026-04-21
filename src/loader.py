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
        # 'schedule' больше не используется, теперь парсим из отдельных столбцов
    }

    COMPETITOR_COLUMNS_COUNT = 5
    SCHEDULE_INTERVALS_COUNT = 4  # Количество возможных временных интервалов

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

        # 4. Расписание: формируем JSON из отдельных столбцов для интервалов
        product['schedule'] = self._parse_schedule_from_columns(row, columns)

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

    def _parse_schedule_from_columns(self, row: pd.Series, columns: pd.Index) -> Optional[str]:
        """
        Собирает расписание из столбцов вида:
        Промежуток 1, Стратеги 1, Процент 1, ... до 4-го интервала.
        Возвращает JSON-строку с массивом интервалов.
        """
        intervals = []
        for i in range(1, self.SCHEDULE_INTERVALS_COUNT + 1):
            # Ищем колонки для i-го интервала
            time_col = self._find_column(columns, [f'промежуток {i}', f'промежуток{i}', f'интервал {i}'])
            strategy_col = self._find_column(columns, [f'стратеги {i}', f'стратегия {i}', f'strategy_{i}'])
            percent_col = self._find_column(columns, [f'процент {i}', f'percent_{i}'])

            if not time_col:
                continue  # Если нет времени начала, интервал не задан

            time_val = row.get(time_col)
            if pd.isna(time_val) or not str(time_val).strip():
                continue

            time_range = str(time_val).strip()
            # Ожидаемый формат: "09:00-12:00"
            if '-' not in time_range:
                logger.warning(f"Неверный формат промежутка '{time_range}', ожидается 'ЧЧ:ММ-ЧЧ:ММ'")
                continue

            start, end = time_range.split('-', 1)
            start = start.strip()
            end = end.strip()

            strategy_val = row.get(strategy_col) if strategy_col else None
            percent_val = row.get(percent_col) if percent_col else None

            try:
                strategy = int(float(strategy_val)) if pd.notna(strategy_val) else 3
            except (ValueError, TypeError):
                strategy = 3

            try:
                percent = float(percent_val) if pd.notna(percent_val) else 0.0
            except (ValueError, TypeError):
                percent = 0.0

            intervals.append({
                'start': start,
                'end': end,
                'strategy': strategy,
                'percent': percent
            })

        if intervals:
            return json.dumps(intervals, ensure_ascii=False)
        return None

    def _find_column(self, columns: pd.Index, candidates: List[str]) -> Optional[str]:
        """Находит первую подходящую колонку из списка кандидатов."""
        for cand in candidates:
            if cand in columns:
                return cand
        return None

    # Старый метод _parse_schedule больше не используется, оставлен для совместимости
    def _parse_schedule(self, raw: Optional[str]) -> Optional[str]:
        """Устаревший метод, оставлен для обратной совместимости (если вдруг есть столбец 'Расписание')."""
        if not raw:
            return None
        raw = raw.strip()
        if raw.startswith('['):
            try:
                json.loads(raw)
                return raw
            except json.JSONDecodeError:
                return None
        # Можно добавить парсинг старого текстового формата, но сейчас не требуется
        return None

    def update_product_in_file(self, offer_id: str, updates: Dict[str, Any]) -> bool:
        """
        Обновляет поля товара в Excel-файле.
        updates: словарь с ключами, соответствующими колонкам:
            'current_price', 'margin', 'margin_week', 'margin_month'
        """
        try:
            from openpyxl import load_workbook
            wb = load_workbook(self.file_path)
            ws = wb.active
            if ws is None:
                logger.error("Не удалось получить активный лист из Excel-файла")
                return False

            header_row = 1
            col_map = {}
            target_columns = {
                'current_price': ['ваша цена', 'current_price', 'price'],
                'margin': ['маржа', 'margin'],
                'margin_week': ['маржа за неделю', 'margin_week'],
                'margin_month': ['маржа за месяц', 'margin_month'],
            }
            for field, synonyms in target_columns.items():
                for col_idx, cell in enumerate(ws[header_row], start=1):
                    if cell.value and str(cell.value).lower().strip() in synonyms:
                        col_map[field] = col_idx
                        break

            sku_col = None
            for col_idx, cell in enumerate(ws[header_row], start=1):
                if cell.value and str(cell.value).lower().strip() in ['sku', 'артикул', 'offer_id']:
                    sku_col = col_idx
                    break
            if sku_col is None:
                logger.error("Не найдена колонка 'SKU'")
                return False

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

            for field, col_idx in col_map.items():
                value = updates.get(field)
                if value is not None:
                    if field.startswith('margin'):
                        value = round(float(value), 2)
                    ws.cell(target_row, col_idx, value=value)

            wb.save(self.file_path)
            logger.info(f"Обновлены поля {list(updates.keys())} для {offer_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления Excel: {e}")
            return False