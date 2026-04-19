import asyncio
import logging
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_FILE
from src.loader import DataLoader
from src.parser import OzonParser
from src.calculator import PriceCalculator, MarginCalculator
from src.ozon_api import OzonApiClient
from src.notifier import MaxNotifier
from src.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / 'repricer.log', mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class Repricer:
    """Главный класс репрайсера"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.db = Database()
        self.loader = DataLoader(DATA_FILE)
        self.calculator = PriceCalculator()
        self.margin_calc = MarginCalculator(self.db)
        self.api_client = OzonApiClient()
        self.notifier = MaxNotifier(chat_id=None)

    async def run(self) -> Dict:
        stats = {
            'products_loaded': 0,
            'prices_parsed': 0,
            'prices_updated': 0,
            'errors': []
        }

        logger.info(f"=== Запуск репрайсера {'(DRY-RUN)' if self.dry_run else ''} ===")

        # 1. Загрузка товаров
        products = self.loader.load()
        stats['products_loaded'] = len(products)
        if not products:
            logger.warning("Нет товаров для обработки")
            if not self.dry_run:
                self.notifier.notify_critical_event("Нет товаров в таблице или ошибка загрузки")
            return stats

        for product in products:
            self.db.upsert_product(product)

        # 2. Парсинг цен
        logger.info(f"Парсинг цен для {len(products)} товаров")
        products_with_prices = []

        async with OzonParser() as parser:
            for product in products:
                urls = product.get('competitor_urls', [])
                if not urls:
                    logger.info(f"Товар {product['offer_id']}: нет ссылок на конкурентов, пропускаем")
                    continue

                prices = await parser.get_prices(urls)
                valid_prices = [p for p in prices if p is not None]
                stats['prices_parsed'] += len(valid_prices)

                logger.info(f"Товар {product['offer_id']}: получено {len(valid_prices)}/{len(urls)} цен")

                products_with_prices.append({
                    'product': product,
                    'competitor_prices': valid_prices,
                    'raw_prices': prices
                })

        # 3. Расчёт и отправка
        updates_for_ozon = []
        margin_updates = []

        for item in products_with_prices:
            product = item['product']
            competitor_prices = item['competitor_prices']

            target_price = self.calculator.calculate_target_price(
                competitor_prices=competitor_prices,
                base_strategy=product.get('strategy', 3),
                base_percent=product.get('strategy_percent', 0.0),
                min_price=product.get('min_price', 0.0),
                schedule=product.get('schedule')
            )

            cost_price = product.get('cost_price', 0.0)
            current_margin = self.margin_calc.calculate_margin(target_price, cost_price)

            avg_margin_week = self.db.get_average_margin(product['offer_id'], 7)
            avg_margin_month = self.db.get_average_margin(product['offer_id'], 30)

            logger.info(
                f"Товар {product['offer_id']}: target={target_price:.2f}, "
                f"margin={current_margin:.2f}%, "
                f"week_avg={avg_margin_week or 'N/A'}%, month_avg={avg_margin_month or 'N/A'}%"
            )

            updates_for_ozon.append({
                'offer_id': str(product['offer_id']),
                'price': f"{target_price:.2f}",
                'old_price': f"{product.get('current_price', target_price):.2f}",
                'min_price': f"{product.get('min_price', 0.0):.2f}"
            })

            margin_updates.append({
                'offer_id': product['offer_id'],
                'target_price': target_price,
                'margin': current_margin,
                'competitor_prices': item['raw_prices']
            })

        # 4. Отправка (или пропуск в dry-run)
        if updates_for_ozon:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Пропущена отправка {len(updates_for_ozon)} цен в Ozon")
                # В dry-run всё равно сохраняем историю как "успех"
                for item in margin_updates:
                    self.db.save_price_record(
                        item['offer_id'],
                        item['target_price'],
                        item['margin'],
                        item['competitor_prices']
                    )
                
                for item in margin_updates:
                    offer_id = item['offer_id']
                    target_price = item['target_price']
                    # Обновляем Excel
                    self.loader.update_current_price_in_file(offer_id, target_price)

                stats['prices_updated'] = len(updates_for_ozon)
            else:
                logger.info(f"Отправка {len(updates_for_ozon)} цен в Ozon")
                success = self.api_client.update_prices(updates_for_ozon)
                if success:
                    stats['prices_updated'] = len(updates_for_ozon)
                    for item in margin_updates:
                        self.db.save_price_record(
                            item['offer_id'],
                            item['target_price'],
                            item['margin'],
                            item['competitor_prices']
                        )

                    for item in margin_updates:
                        offer_id = item['offer_id']
                        target_price = item['target_price']
                        # Обновляем Excel
                        self.loader.update_current_price_in_file(offer_id, target_price)

                else:
                    stats['errors'].append("Ошибка при отправке цен в Ozon API")
                    if not self.dry_run:
                        self.notifier.notify_critical_event("Не удалось обновить цены в Ozon")
        else:
            logger.warning("Нет данных для отправки в Ozon")

        # 5. Уведомления
        if not self.dry_run:
            self.notifier.notify_cycle_complete(
                updated_count=stats['prices_updated'],
                errors=stats['errors']
            )

        logger.info(f"=== Завершено. Обновлено цен: {stats['prices_updated']} ===")
        return stats


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Тестовый прогон без отправки в Ozon и уведомлений')
    args = parser.parse_args()

    repricer = Repricer(dry_run=args.dry_run)
    await repricer.run()


def run_sync():
    asyncio.run(main())


if __name__ == "__main__":
    run_sync()