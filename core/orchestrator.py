import asyncio
import logging
from typing import Dict, Any, List

from .entities import ProductInfo, PricingData
from .repository import IProductRepository
from .services import PriceCalculationService, calculate_old_price
from .mappers import build_price_update_request
from config.settings import settings

logger = logging.getLogger(__name__)


class PricingOrchestrator:
    def __init__(self, repository: IProductRepository, api_client, mail_notifier, loader):
        self.repo = repository
        self.api = api_client
        self.notifier = mail_notifier
        self.loader = loader
        self.calc = PriceCalculationService(default_coefficient=settings.COEFFICIENT_OZON)

    async def run(self, dry_run: bool = False) -> Dict[str, Any]:
        stats = {'products_loaded': 0, 'prices_updated': 0, 'errors': []}
        updates = []

        products = self.loader.load()
        stats['products_loaded'] = len(products)
        if not products:
            logger.warning("Нет товаров для обработки")
            self.notifier.send_detailed_report([], [], dry_run=dry_run)
            return stats

        sku_list = [p.sku for p in products]
        product_map = await self.api.get_product_ids_by_skus(sku_list)
        for p in products:
            info = product_map.get(p.sku, {})
            p.product_id = info.get('product_id')
            p.offer_id = info.get('offer_id')
            if info.get('product_name'):
                p.product_name = info.get('product_name')
            self.repo.upsert_product(p)
            if p.product_name:
                self.loader.update_product_in_file(p.sku, {'product_name': p.product_name})

        for p in products:
            strategies = self.loader.get_strategy_intervals(p)
            self.repo.set_strategies(p.sku, strategies)

        valid_ids = [p.product_id for p in products if p.product_id]
        prices_list = await self.api.get_product_prices(valid_ids)
        prices_dict = {p.product_id: p for p in prices_list}

        updates_for_ozon = []
        results_data = []

        for product in products:
            pricing = prices_dict.get(product.product_id)
            if not pricing:
                updates.append(self._error_update(product, "не удалось получить цены из API"))
                continue

            intervals = self.repo.get_strategies(product.sku)
            result = self.calc.calculate(product.sku, pricing, product.min_price, intervals)
            results_data.append((product, pricing, result))

            avg_week = self.repo.get_average_marginality(product.sku, 7)
            marginality_week = avg_week if avg_week is not None else result.marginality
            avg_month = self.repo.get_average_marginality(product.sku, 30)
            marginality_month = avg_month if avg_month is not None else result.marginality
            self.repo.save_marginality(product.sku, result.marginality, marginality_week, marginality_month)

            discount_coef = result.log_details.get('discount_coef', 1.0)
            real_price = result.result_target_price * discount_coef
            current_price_excel = int(round(real_price))
            min_price_excel = int(round(product.min_price))

            hist = self.repo.get_price_history(product.sku)
            old_customer_price = hist[-1].get('customer_price') if hist else None
            if old_customer_price is not None:
                old_customer_price = int(round(old_customer_price))

            updates.append(self._pending_update(product, old_customer_price, current_price_excel))

            old_price_for_api = calculate_old_price(
                price=result.result_target_price,
                manual_old_price=product.old_price,
                multiplier=settings.OLD_PRICE_MULTIPLIER,
                round_to=settings.PRICE_ROUND_UP_TO
            )
            old_price_excel_update = old_price_for_api

            excel_updates = {
                'current_price': current_price_excel,
                'min_price': min_price_excel,
                'margin': result.marginality,
                'margin_week': marginality_week,
                'margin_month': marginality_month,
                'old_price': old_price_excel_update
            }
            self.loader.update_product_in_file(product.sku, excel_updates)

            min_price_for_api = int(round(product.min_price / discount_coef)) if discount_coef else int(round(product.min_price))

            net_price_val = int(round(pricing.net_price)) if pricing.net_price else None
            
            req = build_price_update_request(
                product_id=product.product_id,
                price=int(round(result.result_target_price)),
                min_price=min_price_for_api,
                net_price=net_price_val,
                old_price=old_price_for_api,
                manage_elastic_boosting=settings.MANAGE_ELASTIC_BOOSTING
            )
            updates_for_ozon.append({
                'product_id': req.product_id,
                'offer_id': product.offer_id or '',
                'price': str(req.price),
                'min_price': str(req.min_price),
                'net_price': str(req.net_price) if req.net_price else None,
                'old_price': str(req.old_price) if req.old_price else None,
                'manage_elastic_boosting_through_price': req.manage_elastic_boosting_through_price
            })

        if not dry_run:
            update_results = await self.api.update_prices(updates_for_ozon)
        else:
            update_results = {}

        self._finalize_updates(updates, products, update_results, dry_run, stats)

        await self._save_history(results_data, updates, valid_ids, dry_run, update_results)

        stats['prices_updated'] = sum(1 for u in updates if u.get('status') == 'updated')
        self.notifier.send_detailed_report(updates, stats['errors'], dry_run=dry_run)

        logger.info(f"=== Завершено. Обновлено товаров: {stats['prices_updated']} ===")
        return stats

    def _error_update(self, product, reason):
        return {
            'sku': product.sku,
            'product_name': product.product_name or '',
            'old_price': None,
            'new_price': None,
            'status': 'error',
            'reason': reason
        }

    def _pending_update(self, product, old_price, new_price):
        return {
            'sku': product.sku,
            'product_name': product.product_name or '',
            'old_price': old_price,
            'new_price': new_price,
            'status': 'pending',
            'reason': None
        }

    def _finalize_updates(self, updates, products, update_results, dry_run, stats):
        for upd in updates:
            product = next((p for p in products if p.sku == upd['sku']), None)
            if product and product.product_id in update_results:
                res = update_results[product.product_id]
                if res['updated']:
                    upd['status'] = 'updated'
                    upd['reason'] = None
                else:
                    upd['status'] = 'error'
                    errors_str = ', '.join([e.get('message', str(e)) for e in res['errors']])
                    upd['reason'] = f"Ошибка API: {errors_str}"
                    stats['errors'].append(f"{upd['sku']}: {errors_str}")
            elif dry_run:
                upd['status'] = 'updated'
                upd['reason'] = 'dry-run (расчёт выполнен)'

    async def _save_history(self, results_data, updates, valid_ids, dry_run, update_results):
        if dry_run:
            for product, pricing, result in results_data:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
        else:
            if update_results:
                logger.info("Запрашиваем актуальные цены для получения real_price...")
                await asyncio.sleep(5)
                fresh_prices = await self.api.get_product_prices(valid_ids)
                fresh_dict = {p.product_id: p for p in fresh_prices}
                for product, pricing, result in results_data:
                    fresh = fresh_dict.get(product.product_id)
                    real_price_value = None
                    if fresh:
                        index_prices, index_data = [], []
                        if fresh.external_index_data_price and fresh.external_index_data_index and fresh.external_index_data_index != 0:
                            index_prices.append(fresh.external_index_data_price)
                            index_data.append(fresh.external_index_data_index)
                        if fresh.ozon_index_data_price and fresh.ozon_index_data_index and fresh.ozon_index_data_index != 0:
                            index_prices.append(fresh.ozon_index_data_price)
                            index_data.append(fresh.ozon_index_data_index)
                        if fresh.self_marketplaces_index_data_price and fresh.self_marketplaces_index_data_index and fresh.self_marketplaces_index_data_index != 0:
                            index_prices.append(fresh.self_marketplaces_index_data_price)
                            index_data.append(fresh.self_marketplaces_index_data_index)
                        if index_prices and index_data:
                            approx_index_price = sum(index_prices) / len(index_prices)
                            approx_index_data = sum(index_data) / len(index_data)
                            real_price_value = round(approx_index_price * approx_index_data)
                            logger.info(f"Товар {product.sku}: real_price={real_price_value}")
                        if real_price_value is not None:
                            self.repo.update_real_customer_price(product.sku, real_price_value)
                            self.repo.save_price_history(product.sku, pricing, result, real_price=real_price_value)
                            for u in updates:
                                if u['sku'] == product.sku:
                                    u['new_price'] = real_price_value
                                    break
                        else:
                            self.repo.save_price_history(product.sku, pricing, result, real_price=None)
                    else:
                        logger.warning(f"Товар {product.sku}: свежие цены не получены")
                        self.repo.save_price_history(product.sku, pricing, result, real_price=None)
            else:
                for product, pricing, result in results_data:
                    self.repo.save_price_history(product.sku, pricing, result, real_price=None)