import asyncio
import logging
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Set

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
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.db = Database()
        self.loader = DataLoader(DATA_FILE)
        self.calculator = PriceCalculator()
        self.margin_calc = MarginCalculator(self.db)
        self.api_client = OzonApiClient()
        self.notifier = MaxNotifier(chat_id=None)
        # Кэш для отслеживания уже сохранённых цен конкурентов в этом запуске
        self._saved_competitor_prices: Set[int] = set()

    async def run(self) -> Dict:
        stats = {
            'products_loaded': 0,
            'prices_parsed': 0,
            'prices_updated': 0,
            'errors': []
        }

        logger.info(f"=== Запуск репрайсера {'(DRY-RUN)' if self.dry_run else ''} ===")

        # 1. Загрузка товаров из Excel
        products = self.loader.load()
        stats['products_loaded'] = len(products)
        if not products:
            logger.warning("Нет товаров для обработки")
            if not self.dry_run:
                self.notifier.notify_critical_event("Нет товаров в таблице или ошибка загрузки")
            return stats

        # Сохраняем / обновляем товары и стратегии
        for p in products:
            self.db.upsert_product(p)
            self.db.set_strategies(p['offer_id'], p['intervals'])

        # 2. Парсинг реальной цены по SKU и цен конкурентов
        logger.info(f"Парсинг цен для {len(products)} товаров")
        products_data = []  # будет хранить {product, real_price, competitor_prices}

        async with OzonParser() as parser:
            for product in products:
                offer_id = product['offer_id']

                # 2a. Реальная цена нашего товара по прямой ссылке
                real_price = await parser.fetch_price_by_sku(offer_id)
                if real_price is None:
                    # Если не найдена, берём из таблицы
                    real_price = product.get('current_price')
                    logger.info(f"Товар {offer_id}: реальная цена не найдена, используем из таблицы: {real_price}")
                else:
                    logger.info(f"Товар {offer_id}: реальная цена = {real_price}")

                # 2b. Цены конкурентов
                urls = product.get('competitor_urls', [])
                comp_prices = []
                if urls:
                    results = await parser.get_prices(urls)
                    for idx, (price, prod_name, shop_name) in enumerate(results):
                        if price is not None:
                            comp_prices.append(price)
                        # Сохраняем конкурента и связь
                        comp_id = self.db.get_or_create_competitor(urls[idx], prod_name, shop_name)
                        self.db.link_product_competitor(offer_id, comp_id, idx + 1)
                        # Сохраняем цену конкурента только один раз за запуск
                        if price is not None and comp_id not in self._saved_competitor_prices:
                            self.db.save_competitor_price(comp_id, price)
                            self._saved_competitor_prices.add(comp_id)
                    logger.info(f"Товар {offer_id}: получено {len(comp_prices)}/{len(urls)} цен конкурентов")
                else:
                    logger.info(f"Товар {offer_id}: нет ссылок на конкурентов")

                products_data.append({
                    'product': product,
                    'real_price': real_price,
                    'competitor_prices': comp_prices,
                })

        # 3. Расчёт целевых цен
        updates_for_ozon = []
        margin_updates = []

        for item in products_data:
            product = item['product']
            competitor_prices = item['competitor_prices']
            real_price = item['real_price']
            min_price = product.get('min_price', 0.0)  # РРЦ

            intervals = product['intervals']

            target_price = self.calculator.calculate_target_price(
                competitor_prices=competitor_prices,
                intervals=intervals,
                min_price=min_price,
                real_price=real_price
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
                'min_price': f"{min_price:.2f}"
            })

            margin_updates.append({
                'offer_id': product['offer_id'],
                'target_price': target_price,
                'margin': current_margin,
            })

        # 4. Отправка в Ozon
        if updates_for_ozon:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Пропущена отправка {len(updates_for_ozon)} цен в Ozon")
                for item in margin_updates:
                    self.db.save_price_record(item['offer_id'], item['target_price'], item['margin'])
                    updates = {
                        'current_price': item['target_price'],
                        'margin': item['margin'],
                        'margin_week': self.db.get_average_margin(item['offer_id'], 7),
                        'margin_month': self.db.get_average_margin(item['offer_id'], 30),
                    }
                    self.loader.update_product_in_file(item['offer_id'], updates)
                stats['prices_updated'] = len(updates_for_ozon)
            else:
                logger.info(f"Отправка {len(updates_for_ozon)} цен в Ozon")
                success = self.api_client.update_prices(updates_for_ozon)
                if success:
                    stats['prices_updated'] = len(updates_for_ozon)
                    for item in margin_updates:
                        self.db.save_price_record(item['offer_id'], item['target_price'], item['margin'])
                        updates = {
                            'current_price': item['target_price'],
                            'margin': item['margin'],
                            'margin_week': self.db.get_average_margin(item['offer_id'], 7),
                            'margin_month': self.db.get_average_margin(item['offer_id'], 30),
                        }
                        self.loader.update_product_in_file(item['offer_id'], updates)
                else:
                    stats['errors'].append("Ошибка при отправке цен в Ozon API")
                    if not self.dry_run:
                        self.notifier.notify_critical_event("Не удалось обновить цены в Ozon")
        else:
            logger.warning("Нет данных для отправки в Ozon")

        if not self.dry_run:
            self.notifier.notify_cycle_complete(
                updated_count=stats['prices_updated'],
                errors=stats['errors']
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
    asyncio.run(main())


if __name__ == "__main__":
    run_sync()