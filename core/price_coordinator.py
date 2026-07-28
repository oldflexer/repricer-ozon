import asyncio
from typing import Dict, Any, List, Optional, Callable
from core.entities import ProductInfo, PricingData, PriceCalculationResult, StrategyInterval
from core.services import PriceCalculationService, calculate_old_price
from core.mappers import build_price_update_request
from core.repository import IProductRepository
from config.settings import settings
from infrastructure.logger import logger


class MarginCalculator:
    """Выделенная логика расчёта маржинальности на основе комиссий."""
    @staticmethod
    def calculate_marginality(result_target_price: float, pricing: PricingData) -> float:
        sales_commission = result_target_price * (pricing.sales_percent_fbs / 100)
        fbs_first_mile_avg = (pricing.fbs_first_mile_min_amount + pricing.fbs_first_mile_max_amount) / 2
        fbs_direct_flow_avg = (pricing.fbs_direct_flow_trans_min_amount + pricing.fbs_direct_flow_trans_max_amount) / 2
        fbs_total = sales_commission + fbs_first_mile_avg + fbs_direct_flow_avg + pricing.fbs_deliv_to_customer_amount + pricing.net_price
        fbo_direct_flow_avg = (pricing.fbo_direct_flow_trans_min_amount + pricing.fbo_direct_flow_trans_max_amount) / 2
        fbo_total = sales_commission + fbo_direct_flow_avg + pricing.fbo_deliv_to_customer_amount + pricing.net_price
        total_costs = (fbs_total + fbo_total) / 2
        if result_target_price > 0:
            return (result_target_price - total_costs) / result_target_price
        return 0.0


class PriceUpdateCoordinator:
    """
    Управляет полным потоком репрайсинга: загрузка, получение данных, расчёт, отправка, сохранение.
    Не содержит деталей реализации (делегирует репозиторию, API, загрузчику, нотификатору).
    """
    def __init__(self, repository: IProductRepository, api_client, loader, notifier,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None):
        self.repo = repository
        self.api = api_client
        self.loader = loader
        self.notifier = notifier
        self.progress_callback = progress_callback
        self.calc = PriceCalculationService(default_coefficient=settings.COEFFICIENT_OZON)

    async def run(self, dry_run: bool = False) -> Dict[str, Any]:
        stats = {'products_loaded': 0, 'prices_updated': 0, 'errors': [], 'warnings': []}
        updates = []

        # Проверка доступности Excel перед загрузкой (аналогично парсеру)
        from infrastructure.file_utils import wait_for_excel_available
        if not wait_for_excel_available(settings.DATA_FILE_PATH):
            logger.error("Excel-файл занят другим процессом, репрайсинг отменён")
            self.notifier.send_detailed_report([], ["Excel-файл занят"], dry_run=dry_run)
            return stats

        # 1. Загрузка Excel с валидацией
        if self.progress_callback:
            self.progress_callback(0, 1, "Загрузка Excel...")
        products, warnings = self.loader.load()
        stats['products_loaded'] = len(products)
        stats['warnings'] = warnings
        if not products:
            self.notifier.send_detailed_report([], stats['errors'], dry_run=dry_run)
            return stats

        # 2. Получение product_id и названий
        if self.progress_callback:
            self.progress_callback(0, 1, "Получение product_id из Ozon...")
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

        # 3. Сохранение стратегий
        for p in products:
            strategies = self.loader.get_strategy_intervals(p)
            self.repo.set_strategies(p.sku, strategies)

        # 4. Получение текущих цен и индексов
        if self.progress_callback:
            self.progress_callback(0, 1, "Получение текущих цен и индексов...")
        valid_ids = [p.product_id for p in products if p.product_id]
        prices_list = await self.api.get_product_prices(valid_ids)
        prices_dict = {p.product_id: p for p in prices_list}

        updates_for_ozon = []
        results_data = []
        total = len(products)

        # 5. Обработка каждого товара
        for idx, product in enumerate(products):
            if self.progress_callback:
                self.progress_callback(idx+1, total, f"Обработка {product.sku}...")

            pricing = prices_dict.get(product.product_id)
            if not pricing:
                updates.append(self._error_update(product, "не удалось получить цены из API"))
                continue

            intervals = self.repo.get_strategies(product.sku)
            result = self.calc.calculate(
                product.sku,
                pricing,
                product.min_price,
                intervals,
                competitor_min_price=product.competitor_min_price
            )
            results_data.append((product, pricing, result))

            avg_week = self.repo.get_average_marginality(product.sku, 7)
            marginality_week = avg_week if avg_week is not None else result.marginality
            avg_month = self.repo.get_average_marginality(product.sku, 30)
            marginality_month = avg_month if avg_month is not None else result.marginality
            self.repo.save_marginality(product.sku, result.marginality, marginality_week, marginality_month)

            discount_coef = result.log_details.get('discount_coef', 1.0)
            real_price = result.result_target_price * discount_coef
            current_price_excel = int(round(real_price))

            hist = self.repo.get_price_history(product.sku)
            old_customer_price = hist[-1].get('customer_price') if hist else None
            if old_customer_price is not None:
                old_customer_price = int(round(old_customer_price))

            updates.append(self._pending_update(product, old_customer_price, current_price_excel))

            old_price_for_api = calculate_old_price(
                price=result.result_target_price,
                manual_old_price=None,
                multiplier=settings.OLD_PRICE_MULTIPLIER,
                round_to=settings.PRICE_ROUND_UP_TO
            )

            excel_updates = self.loader.build_excel_updates(
                product, result, marginality_week, marginality_month, old_price_for_api
            )

            self.loader.update_product_in_file(product.sku, excel_updates)

            # Определяем минимальную цену для API
            if result.strategy_price is not None:
                # Если стратегия была применена, устанавливаем min_price = price
                min_price_for_api = int(round(result.result_target_price))
            else:
                # Иначе используем РИЦ / discount_coef
                min_price_for_api = int(round(product.min_price / discount_coef)) if discount_coef else int(round(product.min_price))

            # Правило Ozon: min_price >= price * 0.5 (оставляем как страховку)
            price_for_api = int(round(result.result_target_price))
            min_allowed = int(price_for_api * 0.5)
            if min_price_for_api < min_allowed:
                old_min = min_price_for_api
                min_price_for_api = min_allowed
                logger.warning(f"SKU {product.sku}: min_price скорректирован с {old_min} до {min_price_for_api} (правило Ozon 50%)")

            net_price_val = int(round(product.cost_price)) if product.cost_price else pricing.net_price

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

        # 6. Отправка цен в Ozon (если не dry-run)
        if not dry_run:
            if self.progress_callback:
                self.progress_callback(total, total, "Отправка цен в Ozon...")
            update_results = await self.api.update_prices(updates_for_ozon)
        else:
            update_results = {}

        # 7. Финальное обновление статусов
        self._finalize_updates(updates, products, update_results, dry_run, stats)

        # 8. Сохранение истории цен (с получением real_price, если нужно)
        await self._save_history(results_data, updates, valid_ids, dry_run, update_results)

        stats['prices_updated'] = sum(1 for u in updates if u.get('status') == 'updated')
        self.notifier.send_detailed_report(updates, stats['errors'], dry_run=dry_run)

        # 9. Автоочистка БД
        deleted = self.repo.auto_cleanup_if_needed(months=3, days_threshold=1)
        if deleted:
            logger.info(f"Автоматическая очистка БД: удалено {deleted} старых записей")

        logger.info(f"=== Завершено. Обновлено товаров: {stats['prices_updated']} ===")
        return stats

    # --- Вспомогательные методы (скопированы из старого Orchestrator) ---
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
                await asyncio.sleep(10)
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
                            self.repo.save_daily_aggregates(product.sku, pricing, result, real_price=real_price_value)
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
                    self.repo.save_daily_aggregates(product.sku, pricing, result, real_price=None)