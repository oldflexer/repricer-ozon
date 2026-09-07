"""
UseCase для парсинга своих товаров для получения real_customer_price.

Аналог ParseCompetitorPricesUseCase, но:
- Вход: список своих SKU + URL (генерируется как https://www.ozon.ru/product/{SKU}/)
- Выход: обновление real_customer_price + discount_coef в БД
- Не трогает Excel-файл с ценами конкурентов
"""

import random
import time
from typing import Any

from config.settings import settings
from core.metrics import record_parser_retry
from core.protocols.api import IApiClient
from core.protocols.parser import OzonPriceParserProtocol
from core.protocols.repository import IProductRepository
from core.use_cases.base_parser import BaseParserUseCase
from infrastructure.logger import logger
from scripts.common import is_shutdown_requested


class ParseOwnProductsUseCase(BaseParserUseCase):
    """
    UseCase для парсинга своих товаров для получения real_customer_price.

    Использует OzonPriceParser для извлечения цен со страниц своих товаров.
    URL генерируется как: https://www.ozon.ru/product/{SKU}/
    """

    def __init__(
        self,
        parser: OzonPriceParserProtocol | None = None,
        product_repo: IProductRepository | None = None,
        api_client: IApiClient | None = None,
    ):
        """
        Инициализирует UseCase.

        Args:
            parser: Экземпляр парсера, реализующий OzonPriceParserProtocol
                    (опционально, будет создан при необходимости).
            product_repo: Репозиторий для обновления БД (опционально).
            api_client: Клиент Ozon API для получения marketing_seller_price (опционально).
        """
        self.parser = parser
        self.product_repo = product_repo
        self.api_client = api_client

    def _parse_price_with_retry(self, url: str) -> float | None:
        """
        Пытается получить цену по URL с повторными попытками.

        Args:
            url: URL страницы товара.

        Returns:
            Цена (float), -1.0 если товар закончился, None при ошибке.
        """
        # Ensure parser is initialized
        if self.parser is None:
            from infrastructure.ozon_competitor import OzonPriceParser
            self.parser = OzonPriceParser()

        for attempt in range(1, settings.PARSER_RETRIES + 1):
            if is_shutdown_requested():
                logger.info("Shutdown requested, stopping own product price parsing")
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
                record_parser_retry(attempt)
                logger.info(f"Перезапуск драйвера перед повторной попыткой {attempt + 1}...")
                try:
                    self.parser.restart()
                except Exception as restart_err:
                    logger.error(f"Не удалось перезапустить драйвер: {restart_err}")
                    return None
                time.sleep(random.uniform(2.0, 4.0))

        return None

    async def execute(self, dry_run: bool = False) -> dict[str, int]:
        """
        Запускает парсинг цен своих товаров.

        Args:
            dry_run: Если True, данные в БД не записываются.

        Returns:
            Словарь со статистикой: updated, errors, skipped.
        """
        # Lazy initialization of parser
        if self.parser is None:
            from infrastructure.ozon_competitor import OzonPriceParser
            self.parser = OzonPriceParser()

        if not self.product_repo:
            logger.error("Product repository not provided")
            return {"updated": 0, "errors": 0, "skipped": 0}

        if not self.api_client:
            logger.error("API client not provided - cannot fetch marketing_seller_price for discount_coef calculation")
            return {"updated": 0, "errors": 0, "skipped": 0}

        # Получаем все товары из БД
        products = self.product_repo.get_all_products()
        if not products:
            logger.warning("Нет товаров в БД для парсинга")
            return {"updated": 0, "errors": 0, "skipped": 0}

        # Получаем product_ids для запроса к API
        product_ids = [p.product_id for p in products if p.product_id is not None]
        if not product_ids:
            logger.warning("Нет product_id для запроса к API")
            return {"updated": 0, "errors": 0, "skipped": 0}

        # Загружаем pricing data из API (нужен marketing_seller_price)
        logger.info(f"Загрузка pricing data для {len(product_ids)} товаров...")
        pricing_list = await self.api_client.get_product_prices(product_ids)
        pricing_map = {p.product_id: p for p in pricing_list}

        stats = {"updated": 0, "errors": 0, "skipped": 0}

        try:
            for product in products:
                if is_shutdown_requested():
                    logger.info("Shutdown requested, stopping own product parsing")
                    break

                sku = product.sku
                url = f"https://www.ozon.ru/product/{sku}/"

                logger.info(f"Парсинг своего товара SKU {sku}...")
                price = self._parse_price_with_retry(url)

                if price == -1.0:
                    stats["skipped"] += 1
                    logger.info(f"SKU {sku}: товар закончился, пропускаем")
                    continue

                if price is not None:
                    # Обновляем real_customer_price в БД
                    self.product_repo.update_real_customer_price(sku, price)

                    # Вычисляем и обновляем discount_coef
                    if product.product_id and product.product_id in pricing_map:
                        pricing = pricing_map[product.product_id]
                        if pricing.marketing_seller_price and pricing.marketing_seller_price > 0:
                            discount_coef = price / pricing.marketing_seller_price
                            if 0.01 < discount_coef < 1.0:  # sanity check
                                self.product_repo.update_discount_coef(sku, discount_coef, 'parsed')
                                logger.info(f"SKU {sku}: discount_coef = {discount_coef:.4f} (source: parsed)")

                    stats["updated"] += 1
                    logger.info(f"SKU {sku}: real_customer_price = {price} ₽")
                else:
                    stats["errors"] += 1
                    logger.warning(f"SKU {sku}: ошибка парсинга")

                time.sleep(
                    random.uniform(
                        settings.PARSER_REQUEST_DELAY_MIN,
                        settings.PARSER_REQUEST_DELAY_MAX,
                    )
                )

        except Exception:
            logger.exception("Критическая ошибка во время парсинга своих товаров")
        finally:
            self.parser.close()

        if is_shutdown_requested():
            logger.info("Graceful shutdown: saving partial results before exit")

        logger.info(
            f"=== Парсинг своих товаров завершён. "
            f"Обновлено: {stats['updated']}, ошибок: {stats['errors']}, пропущено: {stats['skipped']} ==="
        )
        return stats