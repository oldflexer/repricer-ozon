import asyncio
import logging
import sys
import argparse
from pathlib import Path
from typing import Dict, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_FILE
from src.loader import DataLoader
from src.database import Database
from src.competitors_parser import CompetitorsParser
from src.products_parser import ProductsParser
from src.pricemaker import PriceMaker
from src.price_updater import PriceUpdater
from src.mail_notifier import MailNotifier
from src.ozon_api import OzonApiClient

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'repricer.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class Repricer:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.db = Database()
        self.loader = DataLoader(DATA_FILE)
        self.notifier = MailNotifier()
        self.ozon_api = OzonApiClient()

    async def run(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            'products_loaded': 0,
            'competitor_prices_parsed': 0,
            'prices_updated': 0,
            'errors': []
        }

        logger.info(f"=== Запуск репрайсера {'(DRY-RUN)' if self.dry_run else ''} ===")

        # 1. Загрузка товаров из Excel
        try:
            products = self.loader.load()
        except Exception as e:
            logger.error(f"Критическая ошибка загрузки товаров: {e}")
            self.notifier.notify_critical_event(f"Ошибка загрузки товаров: {e}")
            stats['errors'].append(f"Загрузка товаров: {e}")
            return stats

        stats['products_loaded'] = len(products)
        if not products:
            logger.warning("Нет товаров для обработки")
            self.notifier.notify_critical_event("Нет товаров в таблице или ошибка загрузки")
            return stats

        # 1.1 Получаем product_id по SKU
        sku_list = [p['sku'] for p in products]
        product_map = self.ozon_api.get_product_ids_by_skus(sku_list)
        for p in products:
            info = product_map.get(p['sku'], {})
            p['product_id'] = info.get('product_id')
            p['offer_id'] = info.get('offer_id')

        # 1.2 Сохраняем товары и стратегии в БД
        for p in products:
            try:
                self.db.upsert_product(p)
                self.db.set_strategies(p['sku'], p['intervals'])
            except Exception as e:
                logger.error(f"Ошибка сохранения товара {p['sku']}: {e}")
                stats['errors'].append(f"Сохранение товара {p['sku']}: {e}")

        # 2. Парсинг наших товаров
        real_prices: Dict[str, Optional[float]] = {}
        try:
            products_parser = ProductsParser()
            real_prices = await products_parser.fetch_real_prices(products)
        except Exception as e:
            logger.error(f"Ошибка парсинга своих товаров: {e}")
            stats['errors'].append(f"Парсинг своих товаров: {e}")

        # 3. Парсинг конкурентов
        try:
            comp_parser = CompetitorsParser(self.db)
            comp_stats = await comp_parser.run(products)
            stats['competitor_prices_parsed'] = comp_stats.get('competitor_prices_parsed', 0)
            logger.info(f"Спарсено цен конкурентов: {stats['competitor_prices_parsed']}")
        except Exception as e:
            logger.error(f"Ошибка парсинга конкурентов: {e}")
            stats['errors'].append(f"Парсинг конкурентов: {e}")

        # 4. Расчёт цен
        try:
            pricemaker = PriceMaker(self.db)
            updates_for_ozon, margin_items = pricemaker.calculate(products, real_prices)
        except Exception as e:
            logger.error(f"Ошибка расчёта цен: {e}")
            stats['errors'].append(f"Расчёт цен: {e}")
            self.notifier.notify_critical_event(f"Ошибка расчёта цен: {e}")
            return stats

        # 5. Отправка и локальное сохранение
        try:
            updater = PriceUpdater(self.db, self.loader, dry_run=self.dry_run)
            price_stats = updater.update(updates_for_ozon, margin_items)
            stats['prices_updated'] = price_stats.get('prices_updated', 0)
            if price_stats.get('errors'):
                stats['errors'].extend(price_stats['errors'])
        except Exception as e:
            logger.error(f"Ошибка отправки/сохранения цен: {e}")
            stats['errors'].append(f"Отправка/сохранение: {e}")
            self.notifier.notify_critical_event(f"Ошибка отправки/сохранения: {e}")

        # 6. Итоговое уведомление
        self.notifier.notify_cycle_complete(
            updated_count=stats['prices_updated'],
            errors=stats['errors'] if stats['errors'] else None
        )

        logger.info(f"=== Завершено. Обновлено цен: {stats['prices_updated']} ===")
        return stats


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    repricer = Repricer(dry_run=args.dry_run)
    await repricer.run()


def run_sync():
    return asyncio.run(main())


if __name__ == "__main__":
    run_sync()