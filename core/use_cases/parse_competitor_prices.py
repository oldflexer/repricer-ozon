"""
UseCase для парсинга цен конкурентов с Ozon.

Читает Excel-файл, для каждого товара и каждого конкурента (до MAX_COMPETITORS)
загружает страницу товара и извлекает цену с помощью Selenium (undetected-chromedriver).

Обновляет колонки Цена 1..N в Excel-файле точечно, сохраняя форматирование.
"""

import contextlib
import random
import time
from typing import Any

import numpy as np
import pandas as pd

from config.settings import settings
from core.use_cases.base_parser import BaseParserUseCase
from infrastructure.file_utils import save_safely, wait_for_excel_available
from infrastructure.logger import logger
from infrastructure.ozon_competitor import OzonPriceParser
from scripts.common import is_shutdown_requested


class ParseCompetitorPricesUseCase(BaseParserUseCase):
    """
    UseCase для парсинга цен конкурентов.

    Использует OzonPriceParser (Selenium) для извлечения цен со страниц товаров.
    """

    def __init__(self, parser: OzonPriceParser | None = None):
        """
        Инициализирует UseCase.

        Args:
            parser: Экземпляр OzonPriceParser (опционально, будет создан при необходимости).
        """
        self.parser = parser or OzonPriceParser()

    def _parse_price_with_retry(self, url: str) -> float | None:
        """
        Пытается получить цену по URL с повторными попытками.

        Args:
            url: URL страницы товара.

        Returns:
            Цена (float), -1.0 если товар закончился, None при ошибке.
        """
        for attempt in range(1, settings.PARSER_RETRIES + 1):
            if is_shutdown_requested():
                logger.info("Shutdown requested, stopping price parsing")
                return None

            try:
                price = self.parser.get_price(url)
                if price == -1.0:
                    return -1.0
                if price is not None and price > 0:
                    return price
                logger.warning(
                    f"Попытка {attempt}/{settings.PARSER_RETRIES}: цена не получена для {url}"
                )
            except Exception as e:
                logger.error(
                    f"Попытка {attempt}/{settings.PARSER_RETRIES}: ошибка парсинга {url}: {e}"
                )

            if attempt < settings.PARSER_RETRIES:
                logger.info(f"Перезапуск драйвера перед повторной попыткой {attempt + 1}...")
                try:
                    self.parser.restart()
                except Exception as restart_err:
                    logger.error(f"Не удалось перезапустить драйвер: {restart_err}")
                    return None
                time.sleep(random.uniform(2.0, 4.0))

        return None

    async def execute(self, dry_run: bool = False) -> dict[str, int]:  # noqa: PLR0912, PLR0915
        """
        Запускает парсинг цен конкурентов.

        Args:
            dry_run: Если True, данные в Excel не записываются.

        Returns:
            Словарь со статистикой: updated, errors, skipped.
        """
        excel_path = settings.data_file_path

        if not excel_path.exists():
            logger.error(f"Файл не найден: {excel_path}")
            return {"updated": 0, "errors": 0, "skipped": 0}

        if not wait_for_excel_available(excel_path):
            return {"updated": 0, "errors": 0, "skipped": 0}

        try:
            df = pd.read_excel(excel_path, engine="openpyxl")
            df.columns = df.columns.str.strip().str.lower()
        except Exception as e:
            logger.error(f"Не удалось прочитать Excel: {e}")
            return {"updated": 0, "errors": 0, "skipped": 0}

        # Определяем индексы колонок для каждого конкурента
        url_prefix = settings.COMPETITOR_URL_COLUMN_PREFIX.lower()
        price_prefix = settings.COMPETITOR_PRICE_COLUMN_PREFIX.lower()

        col_indices = {}
        for i in range(1, settings.MAX_COMPETITORS + 1):
            url_col_name = f"{url_prefix} {i}"
            price_col_name = f"{price_prefix} {i}"
            if url_col_name in df.columns and price_col_name in df.columns:
                url_loc = df.columns.get_loc(url_col_name)
                price_loc = df.columns.get_loc(price_col_name)
                # get_loc can return int, slice, or ndarray - handle all cases
                def _to_int(loc: Any) -> int:
                    if isinstance(loc, int):
                        return loc
                    if isinstance(loc, slice):
                        return loc.start if loc.start is not None else 0
                    if isinstance(loc, (list, tuple, np.ndarray)):
                        return int(loc[0]) if len(loc) > 0 else 0
                    return int(loc)
                url_idx = _to_int(url_loc)
                price_idx = _to_int(price_loc)
                col_indices[i] = {
                    "url_col": url_idx + 1,  # 1-based для openpyxl
                    "price_col": price_idx + 1,
                }

        if not col_indices:
            logger.error(f"Не найдены колонки '{url_prefix} N' / '{price_prefix} N' в файле.")
            return {"updated": 0, "errors": 0, "skipped": 0}

        stats = {"updated": 0, "errors": 0, "skipped": 0}
        excel_updates: dict[tuple[int, int], float] = {}

        try:
            for row_num, (_, row) in enumerate(df.iterrows(), start=2):
                if is_shutdown_requested():
                    logger.info("Shutdown requested, stopping row processing")
                    break

                sku = row.get("SKU") or row.get("sku") or f"row_{row_num}"

                for i in range(1, settings.MAX_COMPETITORS + 1):
                    if is_shutdown_requested():
                        break

                    cols = col_indices.get(i)
                    if not cols:
                        stats["skipped"] += 1
                        continue

                    url = row.get(f"{url_prefix} {i}")
                    if pd.isna(url) or not str(url).strip():
                        stats["skipped"] += 1
                        continue

                    logger.info(f"Парсинг SKU {sku}, конкурент {i}...")
                    new_price = self._parse_price_with_retry(str(url))
                    if new_price == -1.0:
                        stats["skipped"] += 1
                        logger.info(f"SKU {sku}, конкурент {i}: товар закончился, пропускаем")
                        continue
                    if new_price is not None:
                        excel_updates[(row_num, cols["price_col"])] = new_price
                        stats["updated"] += 1
                        logger.info(f"SKU {sku}, конкурент {i}: {new_price} ₽")
                    else:
                        stats["errors"] += 1
                        old_price = row.get(f"{price_prefix} {i}")
                        old_display = f"{old_price} ₽" if pd.notna(old_price) else "нет данных"
                        logger.warning(
                            f"SKU {sku}, конкурент {i}: ошибка парсинга. "
                            f"Оставлена прежняя цена: {old_display}"
                        )

                    time.sleep(
                        random.uniform(
                            settings.PARSER_REQUEST_DELAY_MIN,
                            settings.PARSER_REQUEST_DELAY_MAX,
                        )
                    )

        except Exception:
            logger.exception("Критическая ошибка во время парсинга. Сохраняем то, что успели.")
        finally:
            self.parser.close()

        if is_shutdown_requested():
            logger.info("Graceful shutdown: saving partial results before exit")

        if not dry_run:
            if excel_updates:
                if wait_for_excel_available(excel_path):
                    with contextlib.suppress(Exception):
                        save_safely(excel_updates, excel_path)
                else:
                    logger.error("Файл стал недоступен перед сохранением. Данные не сохранены.")
            elif stats["updated"] == 0:
                logger.info("Нет обновлённых цен — файл не перезаписывается.")
        else:
            logger.info("Dry-run режим. Данные в Excel не записаны.")

        return stats
