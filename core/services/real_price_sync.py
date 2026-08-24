"""
Сервис для синхронизации реальных цен покупателя (FBS/FBO) со страницы управления ценами Ozon.

Новый алгоритм:
1. Авторизация через OzonSellerClient (профиль Chrome)
2. Переход на страницу управления ценами
3. Парсинг цен через OzonPricePageParser (Selenium/UC) - получаем product_id -> fbs_price
4. Парсинг шаблона через TemplateParser - получаем product_id -> SKU, RIP, комиссии, склад
5. Объединение по product_id
6. Сохранение в БД: real_customer_price (FBS), fbo_customer_price (FBO)

Fallback: если парсинг страницы цен не удался, используем старый метод через TemplateParser.calculate_real_price()
"""

import asyncio
import gc
import tempfile
import time
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from config.settings import settings
from infrastructure.db import SQLiteRepository
from infrastructure.logger import logger
from infrastructure.ozon_price_page_parser import (
    OzonPricePageParser,
    PriceData,
)
from infrastructure.ozon_seller import OzonSellerClient
from infrastructure.template_parser import TemplateParser

LOCK_FILE = str(Path(tempfile.gettempdir()) / "repricer_sync_template.lock")


def delete_file_with_retry(file_path: Path, max_attempts: int = 5, delay: float = 1.0) -> bool:
    """Удаляет файл с повторными попытками, если он занят."""
    for attempt in range(1, max_attempts + 1):
        try:
            file_path.unlink()
            logger.info(f"Файл {file_path} успешно удалён (попытка {attempt})")
            return True
        except PermissionError as e:
            logger.warning(f"Попытка {attempt}/{max_attempts}: файл занят ({e}), ждём {delay}с...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Неожиданная ошибка при удалении: {e}")
            return False
    logger.error(f"Не удалось удалить файл после {max_attempts} попыток")
    return False


class RealPriceSyncService:
    """
    Сервис для синхронизации реальных цен покупателя (FBS/FBO).
    """

    def __init__(self, output_dir: str = "download", headless: bool = False):
        self.output_dir = str(Path(output_dir).resolve())
        self.db_path = str(settings.database_path_path.resolve())
        self.headless = headless

    async def _download_template(self) -> Path | None:
        client = OzonSellerClient(headless=self.headless, download_dir=self.output_dir)
        try:
            logger.info("Начинаем скачивание шаблона...")
            if not client.navigate_to_prices():
                logger.error("Не удалось перейти на страницу управления ценами")
                return None
            downloaded = client.download_price_template(timeout=120)
            if downloaded:
                logger.info(f"Шаблон скачан: {downloaded}")
                return downloaded
            logger.error("Не удалось скачать шаблон")
            return None
        finally:
            client.close()

    def _parse_price_page(self, client: OzonSellerClient) -> list[PriceData] | None:
        try:
            logger.info("Запуск парсера страницы управления ценами...")
            parser = OzonPricePageParser(client.driver_manager)
            prices = parser.parse_all_prices()
            logger.info(f"Парсер вернул {len(prices)} цен")
            return prices
        except Exception as e:
            logger.error(f"Ошибка парсинга страницы цен: {e}")
            return None

    def _process_template(self, file_path: Path) -> dict:
        parser = TemplateParser(file_path)
        if not parser.load():
            logger.error("Не удалось загрузить файл шаблона")
            return {}

        results = parser.process()
        if not results:
            logger.warning("Шаблон не содержит данных")
            return {}

        product_map = {}
        for row in results:
            product_dict = row[0]  # results содержит tuples: (product_dict, real_price, sales_type)
            product_id = product_dict.get("product_id")
            if product_id:
                product_map[product_id] = {
                    "sku": product_dict.get("sku"),
                    "product_name": product_dict.get("product_name"),
                    "rip": product_dict.get("rip", 0.0),
                    "net_price": product_dict.get("net_price", 0.0),
                    "stock_fbs": product_dict.get("stock_fbs", 0),
                    "stock_fbo": product_dict.get("stock_fbo", 0),
                    "warehouse_id": product_dict.get("warehouse_id"),
                    "warehouse_name": product_dict.get("warehouse_name"),
                    "status": product_dict.get("status"),
                }

        logger.info(f"Из шаблона получено {len(product_map)} товаров с product_id")
        return product_map

    def _merge_and_save(
        self,
        price_page_data: list[PriceData],
        template_data: dict,
        dry_run: bool = False,
    ) -> dict:
        logger.info(f"Подключение к БД: {self.db_path}")
        repo = SQLiteRepository(Path(self.db_path))
        db_products = repo.get_all_products()
        sku_to_product = {p.sku: p for p in db_products}
        logger.info(f"Загружено {len(sku_to_product)} товаров из БД")

        stats = {
            "total": len(price_page_data),
            "updated": 0,
            "not_found": 0,
            "skipped": 0,
            "errors": 0,
        }

        for price_data in price_page_data:
            product_id = price_data.product_id

            template_info = template_data.get(product_id)
            if not template_info:
                logger.warning(f"Product ID {product_id} не найден в шаблоне")
                stats["not_found"] += 1
                continue

            sku = template_info["sku"]
            if not sku:
                logger.warning(f"Product ID {product_id} не имеет SKU в шаблоне")
                stats["not_found"] += 1
                continue

            db_product = sku_to_product.get(sku)
            if not db_product:
                logger.warning(f"SKU {sku} (product_id={product_id}) не найден в БД")
                stats["not_found"] += 1
                continue

            if dry_run:
                logger.info(
                    f"[DRY-RUN] SKU={sku}, product_id={product_id}, "
                    f"real_price={price_data.real_price}"
                )
                stats["updated"] += 1
                continue

            try:
                repo.update_real_customer_price(sku, price_data.real_price)
                stats["updated"] += 1
                logger.debug(f"Обновлён SKU={sku}: real_price={price_data.real_price}")
            except Exception as e:
                logger.error(f"Ошибка обновления SKU {sku}: {e}")
                stats["errors"] += 1

        return stats

    def _fallback_sync(self, file_path: Path, dry_run: bool = False) -> dict:
        logger.warning("Используется FALLBACK: синхронизация через TemplateParser")
        parser = TemplateParser(file_path)
        if not parser.load():
            logger.error("Не удалось загрузить файл для fallback")
            return {}

        results = parser.process()
        if not results:
            logger.warning("Нет результатов для fallback")
            return {}

        logger.info(f"Подключение к БД: {self.db_path}")
        repo = SQLiteRepository(Path(self.db_path))
        db_products = repo.get_all_products()
        sku_to_product = {p.sku: p for p in db_products}
        logger.info(f"Загружено {len(sku_to_product)} товаров из БД")

        stats = {
            "total": len(results),
            "updated": 0,
            "not_found": 0,
            "skipped": 0,
            "errors": 0,
        }

        for row in results:
            product_dict = row[0]  # results содержит tuples: (product_dict, real_price, sales_type)
            sku = product_dict.get("sku")
            real_price = row[1]  # Второй элемент - real_price

            if not sku or real_price is None:
                stats["skipped"] += 1
                continue

            db_product = sku_to_product.get(sku)
            if not db_product:
                stats["not_found"] += 1
                continue

            if dry_run:
                logger.info(f"[DRY-RUN] SKU={sku}, real_price={real_price}")
                stats["updated"] += 1
                continue

            try:
                repo.update_real_customer_price(sku, real_price)
                stats["updated"] += 1
            except Exception as e:
                logger.error(f"Ошибка обновления SKU {sku}: {e}")
                stats["errors"] += 1

        return stats

    def _cleanup_old_templates(self, output_path: Path) -> None:
        try:
            for file in output_path.glob("Шаблон для обновления цен_*.xlsx"):
                if delete_file_with_retry(file, max_attempts=3, delay=0.5):
                    logger.info(f"Удалён старый файл шаблона: {file}")
                else:
                    logger.warning(f"Не удалось удалить старый файл: {file}")
        except Exception as e:
            logger.warning(f"Ошибка при очистке старых файлов: {e}")

    async def _sync_real_prices_impl(
        self,
        dry_run: bool,
        keep_file: bool,
        force_delete: bool,
    ) -> dict[str, Any]:
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self._cleanup_old_templates(output_path)

        logger.info("=== Запуск синхронизации реальных цен (новый метод) ===")

        downloaded_file = await self._download_template()
        if not downloaded_file:
            logger.error("Скачивание шаблона не удалось")
            return {}

        template_data = self._process_template(downloaded_file)
        if not template_data:
            logger.warning("Шаблон пуст, пробуем fallback")
            return self._fallback_sync(downloaded_file, dry_run)

        client = OzonSellerClient(headless=self.headless, download_dir=self.output_dir)
        try:
            if not client.navigate_to_prices():
                logger.error("Не удалось перейти на страницу цен для парсинга")
                return self._fallback_sync(downloaded_file, dry_run)

            price_page_data = self._parse_price_page(client)
        finally:
            client.close()

        if not price_page_data:
            logger.warning("Парсинг страницы цен не дал результатов, пробуем fallback")
            return self._fallback_sync(downloaded_file, dry_run)

        stats = self._merge_and_save(price_page_data, template_data, dry_run)

        if not stats:
            logger.warning("Статистика пуста, пробуем fallback")
            return self._fallback_sync(downloaded_file, dry_run)

        logger.info(
            f"Статистика: всего={stats['total']}, "
            f"обновлено={stats['updated']}, "
            f"не найдено={stats['not_found']}, "
            f"пропущено={stats['skipped']}, "
            f"ошибок={stats['errors']}"
        )

        gc.collect()
        time.sleep(0.5)

        if dry_run:
            logger.info("Dry-run: файл не удалён")
            return stats

        should_delete = False
        delete_reason = ""

        if force_delete:
            should_delete = True
            delete_reason = "принудительное удаление (--force-delete)"
        elif keep_file:
            should_delete = False
            delete_reason = "файл сохранён (--keep-file)"
        elif stats["errors"] == 0:
            should_delete = True
            delete_reason = "успешная обработка без ошибок"
        else:
            should_delete = False
            delete_reason = f"обнаружены ошибки ({stats['errors']})"

        if should_delete:
            if delete_file_with_retry(downloaded_file):
                logger.info(f"Файл {downloaded_file} удалён: {delete_reason}")
            else:
                logger.error("Не удалось удалить файл после нескольких попыток")
        else:
            logger.info(f"Файл не удалён: {delete_reason}")

        logger.info("=== Синхронизация завершена ===")
        return stats

    def sync_real_prices(
        self,
        dry_run: bool = False,
        keep_file: bool = False,
        force_delete: bool = False,
        use_lock: bool = True,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.sync_real_prices_async(
                dry_run=dry_run,
                keep_file=keep_file,
                force_delete=force_delete,
                use_lock=use_lock,
            )
        )

    async def sync_real_prices_async(
        self,
        dry_run: bool = False,
        keep_file: bool = False,
        force_delete: bool = False,
        use_lock: bool = True,
    ) -> dict[str, Any]:
        if use_lock:
            lock = FileLock(LOCK_FILE, timeout=300)
            try:
                with lock:
                    return await self._sync_real_prices_impl(
                        dry_run=dry_run,
                        keep_file=keep_file,
                        force_delete=force_delete,
                    )
            except Timeout:
                logger.error("Не удалось получить лок для синхронизации (таймаут 5 мин)")
                return {}
        else:
            return await self._sync_real_prices_impl(
                dry_run=dry_run,
                keep_file=keep_file,
                force_delete=force_delete,
            )
