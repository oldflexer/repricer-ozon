"""
Сервис для синхронизации реальных цен из шаблона Ozon.
Скачивает шаблон, парсит, вычисляет real_price и обновляет БД.
"""

import asyncio
import gc
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from filelock import FileLock, Timeout

from config.settings import settings
from infrastructure.db import SQLiteRepository
from infrastructure.ozon_seller import OzonSellerClient
from infrastructure.template_parser import TemplateParser
from infrastructure.logger import logger


LOCK_FILE = os.path.join(tempfile.gettempdir(), "repricer_sync_template.lock")


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
    Сервис для синхронизации реальных цен из шаблона Ozon.
    """

    def __init__(self, output_dir: str = "download", headless: bool = False):
        self.output_dir = output_dir
        self.headless = headless

    async def _download_template(self) -> Optional[Path]:
        """Скачивает шаблон цен из панели Ozon."""
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
            else:
                logger.error("Не удалось скачать шаблон")
                return None
        finally:
            client.close()

    def _process_template(self, file_path: Path, dry_run: bool = False) -> dict:
        """Обрабатывает шаблон: парсинг, расчёт, обновление БД."""
        parser = TemplateParser(file_path)
        if not parser.load():
            logger.error("Не удалось загрузить файл")
            return {}

        results = parser.process()
        if not results:
            logger.warning("Нет результатов для обновления")
            return {}

        repo = SQLiteRepository(settings.DATABASE_PATH_PATH)
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

        for product_data, real_price, sales_type in results:
            sku = product_data.get("sku")
            if not sku:
                stats["skipped"] += 1
                continue

            if real_price is None:
                logger.warning(f"SKU {sku}: цена не рассчитана, пропускаем")
                stats["skipped"] += 1
                continue

            if sku not in sku_to_product:
                logger.warning(f"SKU {sku} не найден в БД, пропускаем")
                stats["not_found"] += 1
                continue

            if dry_run:
                logger.info(f"DRY-RUN: SKU {sku} -> real_price = {real_price:.2f} (тип: {sales_type})")
                stats["updated"] += 1
                continue

            try:
                repo.update_real_customer_price(sku, real_price)
                logger.info(f"✅ SKU {sku}: обновлена real_price = {real_price:.2f}")
                stats["updated"] += 1
            except Exception as e:
                logger.error(f"❌ SKU {sku}: ошибка обновления: {e}")
                stats["errors"] += 1

        return stats

    async def sync_real_prices_async(
        self,
        dry_run: bool = False,
        keep_file: bool = False,
        force_delete: bool = False,
        use_lock: bool = True,
    ) -> Dict[str, Any]:
        """
        Асинхронная синхронизация реальных цен из шаблона Ozon.
        Возвращает статистику.
        """
        if use_lock:
            lock = FileLock(LOCK_FILE, timeout=settings.PARSER_LOCK_TIMEOUT)
            try:
                with lock.acquire(timeout=settings.PARSER_LOCK_TIMEOUT):
                    return await self._sync_real_prices_impl(
                        dry_run, keep_file, force_delete
                    )
            except Timeout:
                logger.error(
                    f"Не удалось получить блокировку за {settings.PARSER_LOCK_TIMEOUT} секунд. "
                    "Синхронизация пропущена."
                )
                return {}
        else:
            return await self._sync_real_prices_impl(
                dry_run, keep_file, force_delete
            )

    async def _sync_real_prices_impl(
        self,
        dry_run: bool,
        keep_file: bool,
        force_delete: bool,
    ) -> Dict[str, Any]:
        """Реализация синхронизации (без блокировки)."""
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        logger.info("=== Запуск синхронизации цен из шаблона ===")

        # 1. Скачивание
        downloaded_file = await self._download_template()
        if not downloaded_file:
            logger.error("Скачивание не удалось")
            return {}

        # 2. Обработка
        stats = self._process_template(downloaded_file, dry_run=dry_run)

        if not stats:
            logger.warning("Статистика пуста, возможно, файл не содержит данных")
            if force_delete and not keep_file:
                if delete_file_with_retry(downloaded_file):
                    logger.info("Файл удалён принудительно (нет данных)")
            return stats

        # 3. Вывод статистики в лог
        logger.info(
            f"Статистика: всего={stats['total']}, "
            f"обновлено={stats['updated']}, "
            f"не найдено={stats['not_found']}, "
            f"пропущено={stats['skipped']}, "
            f"ошибок={stats['errors']}"
        )

        # 4. Освобождение ресурсов перед удалением
        gc.collect()
        time.sleep(0.5)

        # 5. Удаление файла
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
        elif stats['errors'] == 0:
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
    ) -> Dict[str, Any]:
        """Синхронная обёртка."""
        return asyncio.run(
            self.sync_real_prices_async(
                dry_run=dry_run,
                keep_file=keep_file,
                force_delete=force_delete,
                use_lock=use_lock,
            )
        )