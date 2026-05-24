import logging
from typing import Dict, Any, List
from .entities import ProductInfo, PriceCalculationResult
from .repository import IProductRepository
from .services import PriceCalculationService

logger = logging.getLogger(__name__)


class RepricingUseCase:
    def __init__(self, repository: IProductRepository, api_client, mail_notifier,
                 calculator: PriceCalculationService, loader):
        self.repo = repository
        self.api = api_client
        self.notifier = mail_notifier
        self.calc = calculator
        self.loader = loader

    def execute(self, dry_run: bool = False) -> Dict[str, Any]:
        stats = {'products_loaded': 0, 'prices_updated': 0, 'errors': []}

        # 1. Загрузка товаров из Excel
        products = self.loader.load()
        stats['products_loaded'] = len(products)
        if not products:
            logger.warning("Нет товаров для обработки")
            self.notifier.notify_cycle_complete(updated_count=0, errors=None)
            return stats

        # 2. Получение product_id через API для всех SKU
        sku_list = [p.sku for p in products]
        product_map = self.api.get_product_ids_by_skus(sku_list)
        for p in products:
            info = product_map.get(p.sku, {})
            p.product_id = info.get('product_id')
            p.offer_id = info.get('offer_id')
            if info.get('product_name'):
                p.product_name = info.get('product_name')
            self.repo.upsert_product(p)
            if p.product_name:
                self.loader.update_product_in_file(p.sku, {'product_name': p.product_name})

        # 3. Сохранение стратегий
        for p in products:
            strategies = self.loader.get_strategy_intervals(p)
            self.repo.set_strategies(p.sku, strategies)

        # 4. Получение цен через API (с батчингом)
        valid_ids = [p.product_id for p in products if p.product_id]
        prices_list = self.api.get_product_prices(valid_ids)
        prices_dict = {p.product_id: p for p in prices_list}

        # 5. Расчет цен и подготовка запросов на обновление
        updates_for_ozon = []
        for product in products:
            pricing = prices_dict.get(product.product_id)
            if not pricing:
                continue
            intervals = self.repo.get_strategies(product.sku)
            result = self.calc.calculate(product.sku, pricing, product.min_price, intervals)

            self.repo.save_price_history(product.sku, pricing, result)

            avg_week = self.repo.get_average_marginality(product.sku, 7)
            marginality_week = avg_week if avg_week is not None else result.marginality
            avg_month = self.repo.get_average_marginality(product.sku, 30)
            marginality_month = avg_month if avg_month is not None else result.marginality
            self.repo.save_marginality(product.sku, result.marginality, marginality_week, marginality_month)

            discount_coef = result.log_details.get('discount_coef', 1.0)
            real_price = result.result_target_price * discount_coef
            current_price_excel = int(round(real_price))
            min_price_excel = int(round(product.min_price))

            # --- Логика old_price (различаем пусто, 0, число) ---
            old_price_for_api = None
            old_price_excel_update = None

            if product.old_price is not None:
                # В Excel есть значение (включая 0)
                old_price_for_api = int(round(product.old_price))
                # Не перезаписываем Excel
            else:
                # В Excel пусто – берём из API
                if pricing.old_price and pricing.old_price != 0:
                    old_price_for_api = int(round(pricing.old_price))
                    old_price_excel_update = old_price_for_api
                else:
                    old_price_for_api = None

            # Подготовка данных для обновления Excel
            excel_updates = {
                'current_price': current_price_excel,
                'min_price': min_price_excel,
                'margin': result.marginality,
                'margin_week': marginality_week,
                'margin_month': marginality_month
            }
            if old_price_excel_update is not None:
                excel_updates['old_price'] = old_price_excel_update
            # Если old_price_excel_update == None – поле old_price в Excel не трогаем

            self.loader.update_product_in_file(product.sku, excel_updates)

            # Минимальная цена для API с учётом коэффициента
            min_price_for_api = int(round(product.min_price / discount_coef)) if discount_coef else int(round(product.min_price))

            updates_for_ozon.append({
                'product_id': product.product_id,
                'offer_id': product.offer_id or '',
                'price': f"{int(round(result.result_target_price))}",
                'min_price': f"{min_price_for_api}",
                'net_price': f"{int(round(pricing.net_price))}" if pricing.net_price else None,
                'old_price': f"{old_price_for_api}" if old_price_for_api is not None else None,
            })

        # 6. Отправка в Ozon
        if not dry_run:
            success = self.api.update_prices(updates_for_ozon)
            if not success:
                stats['errors'].append("Ошибка при отправке цен в Ozon API")
        stats['prices_updated'] = len(updates_for_ozon)

        # 7. Уведомление
        self.notifier.notify_cycle_complete(
            updated_count=stats['prices_updated'],
            errors=stats['errors'] if stats['errors'] else None
        )

        logger.info(f"=== Завершено. Обновлено цен: {stats['prices_updated']} ===")
        return stats