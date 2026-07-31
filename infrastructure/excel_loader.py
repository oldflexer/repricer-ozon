"""
Загрузчик данных из Excel-файла.

Реализует интерфейс ILoader: читает товары, стратегии, цены конкурентов,
обновляет ячейки в файле после расчёта.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config.settings import settings
from core.entities import PriceCalculationResult, ProductInfo, StrategyInterval
from core.repository import ILoader
from infrastructure.logger import logger


class ExcelLoader(ILoader):
    """
    Загрузчик данных из Excel-файла.

    Читает:
        - товары (SKU, себестоимость, РИЦ, старая цена),
        - цены конкурентов (до 5),
        - интервалы стратегий (до N, настраивается через SCHEDULE_INTERVALS_COUNT).

    После расчёта обновляет ячейки с ценами и маржинальностью,
    сохраняя форматирование через openpyxl.
    """

    # Маппинг названий колонок для обратной совместимости
    COLUMN_MAPPING = {
        "sku": ["sku", "артикул", "article"],
        "cost_price": ["себестоимость", "cost_price", "cost"],
        "min_price": ["цена риц"],
        "old_price": ["цена до скидки", "old_price", "старая цена"],
    }

    def __init__(self, file_path: Path) -> None:
        """
        Инициализирует загрузчик.

        Args:
            file_path: Путь к Excel-файлу.
        """
        self.file_path = file_path
        self._strategies: Dict[str, List[StrategyInterval]] = {}

    # ------------------------------------------------------------------
    # Реализация интерфейса ILoader
    # ------------------------------------------------------------------

    def load(self) -> Tuple[List[ProductInfo], List[str]]:
        """
        Загружает товары из Excel с валидацией.

        Returns:
            Кортеж (список товаров, список предупреждений/ошибок).

        Raises:
            Возвращает пустой список и сообщение об ошибке, если файл не найден,
            имеет неверный формат, отсутствует колонка SKU или есть дубликаты SKU.
        """
        if not self.file_path.exists():
            logger.error(f"Файл {self.file_path} не найден")
            return [], ["Файл Excel не найден"]

        if self.file_path.suffix.lower() != ".xlsx":
            logger.error(
                f"Неподдерживаемый формат: {self.file_path.suffix}. Используйте .xlsx"
            )
            return [], [f"Неподдерживаемый формат: {self.file_path.suffix}"]

        df = pd.read_excel(self.file_path, engine="openpyxl", dtype=str)
        df.columns = df.columns.str.lower().str.strip()

        # Поиск колонки SKU
        sku_col = None
        for col in ["sku", "артикул", "article", "id", "offer_id"]:
            if col in df.columns:
                sku_col = col
                break
        if sku_col is None:
            return [], [
                "Не найдена колонка SKU (ожидаются: sku, артикул, article, id, offer_id)"
            ]

        # Нормализация SKU для проверки дубликатов
        df["_sku_normalized"] = df[sku_col].astype(str).str.strip()
        duplicates = df[df["_sku_normalized"].duplicated(keep=False)][
            "_sku_normalized"
        ].unique()
        if len(duplicates) > 0:
            return [], [f"Обнаружены дубликаты SKU: {', '.join(duplicates)}"]

        products = []
        warnings = []
        self._strategies.clear()

        for i, (_, row) in enumerate(df.iterrows(), start=2):
            sku = str(row[sku_col]).strip()
            if not sku:
                warnings.append(f"Строка {i}: пропущен SKU")
                continue

            # Валидация себестоимости
            cost_price = self._get_float(
                row, df.columns, ["себестоимость", "cost_price", "cost"], 0.0
            )
            if cost_price <= 0:
                warnings.append(
                    f"SKU {sku}: себестоимость = {cost_price} <= 0, товар пропущен"
                )
                continue

            min_price = self._get_float(
                row, df.columns, ["цена риц", "min_price", "rip"], 0.0
            )

            # Чтение цен конкурентов (макс. 5)
            competitor_prices = []
            for j in range(1, settings.MAX_COMPETITORS + 1):
                price_col = f"Цена {j}"
                if price_col in df.columns:
                    val = row.get(price_col)
                    if pd.notna(val):
                        try:
                            price = float(val)
                            if price > 0:
                                competitor_prices.append(price)
                        except (ValueError, TypeError):
                            pass
            competitor_min_price = min(competitor_prices) if competitor_prices else None

            # Парсинг интервалов стратегий
            intervals, interval_warnings = self._parse_intervals_with_validation(
                row, df.columns
            )
            warnings.extend(interval_warnings)

            if not intervals:
                warnings.append(
                    f"SKU {sku}: не задано ни одного интервала стратегии, "
                    "используется стратегия по умолчанию 'Равная'"
                )
                intervals = [
                    StrategyInterval(start="00:00", end="23:59", strategy_type=3, percent=0.0)
                ]

            old_price_val = self._get_float(
                row, df.columns, ["цена до скидки", "old_price", "старая цена"], 0.0
            )
            old_price = old_price_val if old_price_val > 0 else None

            product = ProductInfo(
                sku=sku,
                product_name=None,
                cost_price=cost_price,
                min_price=min_price,
                current_price=0.0,
                old_price=old_price,
                competitor_min_price=competitor_min_price,
            )
            products.append(product)
            self._strategies[sku] = intervals

        logger.info(f"Загружено {len(products)} товаров, {len(warnings)} предупреждений")
        return products, warnings

    def get_strategy_intervals(self, product: ProductInfo) -> List[StrategyInterval]:
        """
        Возвращает интервалы стратегий для товара (из загруженных данных).

        Args:
            product: Объект товара (используется SKU).

        Returns:
            Список StrategyInterval (пустой, если не найдено).
        """
        return self._strategies.get(product.sku, [])

    def update_product_in_file(self, sku: str, updates: Dict[str, Any]) -> bool:
        """
        Обновляет данные товара в Excel-файле (точечное обновление ячеек).

        Args:
            sku: Артикул товара.
            updates: Словарь {поле: значение}.

        Returns:
            True в случае успеха, False при ошибке.
        """
        try:
            from openpyxl import load_workbook

            wb = load_workbook(self.file_path)
            ws = wb.active
            if ws is None:
                logger.error("Не удалось получить активный лист")
                return False

            header_row = 1
            col_map = {}
            target_columns = {
                "current_price": ["ваша цена", "current_price", "price"],
                "min_price": ["минимальная цена", "min_price", "min"],
                "old_price": ["цена до скидки", "old_price", "старая цена"],
                "margin": ["маржинальность", "маржа", "margin"],
                "margin_week": ["маржинальность за неделю", "margin_week"],
                "margin_month": ["маржинальность за месяц", "margin_month"],
                "product_name": ["название", "name", "товар", "product_name"],
            }

            # Определяем индексы колонок по заголовкам
            for field, synonyms in target_columns.items():
                for col_idx, cell in enumerate(ws[header_row], start=1):
                    if cell.value and str(cell.value).lower().strip() in synonyms:
                        col_map[field] = col_idx
                        break

            # Поиск колонки SKU
            sku_col = None
            for col_idx, cell in enumerate(ws[header_row], start=1):
                if cell.value and str(cell.value).lower().strip() in ["sku", "артикул", "offer_id"]:
                    sku_col = col_idx
                    break
            if sku_col is None:
                logger.error("Не найдена колонка 'SKU'")
                return False

            # Поиск строки с нужным SKU
            target_row = None
            for row_idx in range(2, ws.max_row + 1):
                sku_cell = ws.cell(row_idx, sku_col)
                cell_value = sku_cell.value
                if cell_value is None:
                    continue
                cell_str = str(cell_value).strip()
                if cell_str == str(sku):
                    target_row = row_idx
                    break
                try:
                    if int(float(cell_str)) == int(float(sku)):
                        target_row = row_idx
                        break
                except (ValueError, TypeError):
                    pass

            if target_row is None:
                logger.warning(f"SKU {sku} не найден в файле")
                return False

            # Обновляем ячейки
            for field, col_idx in col_map.items():
                value = updates.get(field)
                if value is not None:
                    if field.startswith("margin"):
                        value = round(float(value), 2)
                    ws.cell(target_row, col_idx, value=value)

            wb.save(self.file_path)
            logger.info(f"Обновлены поля {list(updates.keys())} для SKU {sku}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления Excel: {e}")
            return False

    # ------------------------------------------------------------------
    # Приватные вспомогательные методы
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_strategy_value(value) -> int:
        """
        Преобразует значение стратегии из Excel в числовой код.

        Поддерживает:
            - числа 1, 2, 3,
            - текстовые варианты: 'ниже', 'выше', 'равная',
            - любые регистры.

        Args:
            value: Значение из ячейки (строка, число, None).

        Returns:
            Код стратегии: 1 – ниже, 2 – выше, 3 – равна (по умолчанию).
        """
        if pd.isna(value):
            return 3
        try:
            num = int(float(value))
            if num in (1, 2, 3):
                return num
        except (ValueError, TypeError):
            pass

        str_val = str(value).strip().lower()
        if str_val in ("ниже", "ниже индекса", "1"):
            return 1
        elif str_val in ("выше", "выше индекса", "2"):
            return 2
        elif str_val in ("равная", "равно", "равна", "равен", "3"):
            return 3
        else:
            logger.warning(
                f"Неизвестное значение стратегии '{value}', используется 'Равная' (3)"
            )
            return 3

    def _parse_intervals_with_validation(
        self, row: pd.Series, columns: pd.Index
    ) -> Tuple[List[StrategyInterval], List[str]]:
        """
        Парсит интервалы стратегий из строки Excel с валидацией.

        Args:
            row: Строка DataFrame.
            columns: Индекс колонок (для поиска по имени).

        Returns:
            Кортеж (список StrategyInterval, список предупреждений).
        """
        intervals = []
        warnings = []

        for i in range(1, settings.SCHEDULE_INTERVALS_COUNT + 1):
            time_col = self._find_column(columns, [f"интервал {i}", f"промежуток {i}"])
            if not time_col:
                continue

            time_val = row.get(time_col)
            if pd.isna(time_val) or not str(time_val).strip():
                continue

            time_range = str(time_val).strip()
            if "-" not in time_range:
                warnings.append(
                    f"Интервал {i}: неверный формат '{time_range}', ожидается ЧЧ:ММ-ЧЧ:ММ"
                )
                continue

            start, end = time_range.split("-", 1)
            start, end = start.strip(), end.strip()

            # Простая проверка формата HH:MM
            if not (len(start) == 5 and start[2] == ":" and start[:2].isdigit() and start[3:].isdigit()):
                warnings.append(f"Интервал {i}: некорректное время начала '{start}'")
            if not (len(end) == 5 and end[2] == ":" and end[:2].isdigit() and end[3:].isdigit()):
                warnings.append(f"Интервал {i}: некорректное время окончания '{end}'")

            strategy_col = self._find_column(columns, [f"стратегия {i}", f"стратеги {i}"])
            strategy_val = row.get(strategy_col) if strategy_col else None
            strategy = self._parse_strategy_value(strategy_val)

            percent_col = self._find_column(columns, [f"процент {i}", f"percent_{i}"])
            percent = 0.0
            if percent_col:
                percent_val = row.get(percent_col)
                if pd.notna(percent_val):
                    try:
                        percent = float(percent_val)
                        if strategy in (1, 2) and (percent < 0 or percent > 100):
                            warnings.append(
                                f"Интервал {i}: процент {percent} выходит за пределы 0-100, используется 0"
                            )
                            percent = 0.0
                    except Exception:
                        warnings.append(
                            f"Интервал {i}: процент '{percent_val}' не число, используется 0"
                        )

            intervals.append(
                StrategyInterval(
                    start=start, end=end, strategy_type=strategy, percent=percent
                )
            )

        return intervals, warnings

    def _parse_row(self, row: pd.Series, columns: pd.Index) -> tuple[Optional[ProductInfo], List[StrategyInterval]]:
        """
        (Устаревший метод) Парсит строку Excel в объект ProductInfo и список интервалов.

        Оставлен для обратной совместимости; в текущей реализации не используется.
        """
        product_dict = {}
        for std_name, synonyms in self.COLUMN_MAPPING.items():
            value = None
            for syn in synonyms:
                if syn in columns:
                    val = row.get(syn)
                    if pd.notna(val):
                        value = val
                        break
            product_dict[std_name] = value

        if not product_dict.get("sku"):
            logger.warning("Пропущена строка без SKU")
            return None, []

        intervals = []
        for i in range(1, settings.SCHEDULE_INTERVALS_COUNT + 1):
            time_col = self._find_column(columns, [f"интервал {i}", f"промежуток {i}"])
            strategy_col = self._find_column(columns, [f"стратегия {i}", f"стратеги {i}"])
            percent_col = self._find_column(columns, [f"процент {i}", f"percent_{i}"])

            if not time_col:
                continue

            time_val = row.get(time_col)
            if pd.isna(time_val) or not str(time_val).strip():
                continue

            time_range = str(time_val).strip()
            if "-" not in time_range:
                logger.warning(f"Неверный формат интервала '{time_range}'")
                continue

            start, end = time_range.split("-", 1)
            start, end = start.strip(), end.strip()

            strategy_val = row.get(strategy_col) if strategy_col else None
            percent_val = row.get(percent_col) if percent_col else None

            strategy = self._parse_strategy_value(strategy_val)
            percent = 0.0
            if percent_val is not None and pd.notna(percent_val):
                try:
                    percent = float(percent_val)
                except (ValueError, TypeError):
                    percent = 0.0

            intervals.append(
                StrategyInterval(
                    start=start, end=end, strategy_type=strategy, percent=percent
                )
            )

        if not intervals:
            base_strategy_col = self._find_column(columns, ["стратегия", "strategy"])
            base_strategy_val = row.get(base_strategy_col) if base_strategy_col else None
            base_strategy = self._parse_strategy_value(base_strategy_val)
            base_percent_col = self._find_column(columns, ["процент", "percent"])
            base_percent = 0.0
            if base_percent_col:
                base_percent_val = row.get(base_percent_col)
                if base_percent_val is not None and pd.notna(base_percent_val):
                    try:
                        base_percent = float(base_percent_val)
                    except (ValueError, TypeError):
                        base_percent = 0.0
            intervals.append(
                StrategyInterval(
                    start="00:00", end="23:59",
                    strategy_type=base_strategy, percent=base_percent
                )
            )

        cost_price = 0.0
        if product_dict.get("cost_price") is not None:
            try:
                cost_price = float(product_dict["cost_price"])
            except Exception:
                pass

        min_price = 0.0
        if product_dict.get("min_price") is not None:
            try:
                min_price = float(product_dict["min_price"])
            except Exception:
                pass

        old_price = None
        if product_dict.get("old_price") is not None:
            try:
                old_price = float(product_dict["old_price"])
            except Exception:
                pass

        product = ProductInfo(
            sku=product_dict["sku"],
            product_name=None,
            cost_price=cost_price,
            min_price=min_price,
            current_price=0.0,
            old_price=old_price,
        )
        return product, intervals

    def _find_column(self, columns: pd.Index, candidates: List[str]) -> Optional[str]:
        """Ищет колонку по одному из возможных имён."""
        for cand in candidates:
            if cand in columns:
                return cand
        return None

    def _get_float(
        self, row: pd.Series, columns: pd.Index, candidates: List[str], default: float
    ) -> float:
        """Извлекает числовое значение из ячейки по имени колонки."""
        col = self._find_column(columns, candidates)
        if col:
            val = row.get(col)
            if pd.notna(val):
                try:
                    return float(val)
                except Exception:
                    pass
        return default

    def build_excel_updates(
        self,
        product: ProductInfo,
        result: PriceCalculationResult,
        marginality_week: float,
        marginality_month: float,
        old_price_update: Optional[int],
    ) -> Dict[str, Any]:
        """
        Формирует словарь обновлений для Excel на основе результатов расчёта.

        Args:
            product: Объект товара.
            result: Результат расчёта цены и маржинальности.
            marginality_week: Средняя маржинальность за неделю.
            marginality_month: Средняя маржинальность за месяц.
            old_price_update: Значение old_price для записи (или None).

        Returns:
            Словарь с полями: current_price, min_price, margin, margin_week,
            margin_month, old_price (если передан).
        """
        discount_coef = result.log_details.get("discount_coef", 1.0)
        real_price = result.result_target_price * discount_coef
        current_price_excel = int(round(real_price))
        min_price_excel = int(round(product.min_price))

        updates = {
            "current_price": current_price_excel,
            "min_price": min_price_excel,
            "margin": result.marginality,
            "margin_week": marginality_week,
            "margin_month": marginality_month,
        }
        if old_price_update is not None:
            updates["old_price"] = old_price_update
        return updates