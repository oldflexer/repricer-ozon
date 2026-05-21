import time
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
        updates = []   # для детализированного отчёта

        # 1. Загрузка товаров из Excel
        products = self.loader.load()
        stats['products_loaded'] = len(products)
        if not products:
            logger.warning("Нет товаров для обработки")
            self.notifier.send_detailed_report([], [], dry_run=dry_run)
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

        # 4. Получение цен через API
        valid_ids = [p.product_id for p in products if p.product_id]
        prices_list = self.api.get_product_prices(valid_ids)
        prices_dict = {p.product_id: p for p in prices_list}

        # 5. Расчет цен, подготовка запросов и данных для истории
        updates_for_ozon = []
        results_data = []   # (product, pricing, result)
        for product in products:
            pricing = prices_dict.get(product.product_id)
            if not pricing:
                updates.append({
                    'sku': product.sku,
                    'product_name': product.product_name or '',
                    'old_price': None,
                    'new_price': None,
                    'status': 'error',
                    'reason': 'не удалось получить цены из API'
                })
                continue

            intervals = self.repo.get_strategies(product.sku)
            result = self.calc.calculate(product.sku, pricing, product.min_price, intervals)
            results_data.append((product, pricing, result))

            # Сохраняем маржинальность
            avg_week = self.repo.get_average_marginality(product.sku, 7)
            marginality_week = avg_week if avg_week is not None else result.marginality
            avg_month = self.repo.get_average_marginality(product.sku, 30)
            marginality_month = avg_month if avg_month is not None else result.marginality
            self.repo.save_marginality(product.sku, result.marginality, marginality_week, marginality_month)

            discount_coef = result.log_details.get('discount_coef', 1.0)
            real_price = result.result_target_price * discount_coef
            current_price_excel = int(round(real_price))
            min_price_excel = int(round(product.min_price))

            # Получаем предыдущую цену из истории (только для отчёта)
            hist = self.repo.get_price_history(product.sku)
            old_customer_price = hist[-1].get('customer_price') if hist else None
            if old_customer_price is not None:
                old_customer_price = int(round(old_customer_price))

            # Предварительный статус: 'pending' – будет обновлён после ответа API
            updates.append({
                'sku': product.sku,
                'product_name': product.product_name or '',
                'old_price': old_customer_price,
                'new_price': current_price_excel,
                'status': 'pending',
                'reason': None
            })

            # --- Логика old_price, округление вверх до сотен ---
            price_for_old = result.result_target_price
            old_price_calculated = price_for_old * 1.5
            old_price_calculated = int((old_price_calculated + 99) // 100 * 100)
            old_price_for_api = old_price_calculated
            old_price_excel_update = old_price_for_api

            # Подготовка данных для Excel
            excel_updates = {
                'current_price': current_price_excel,
                'min_price': min_price_excel,
                'margin': result.marginality,
                'margin_week': marginality_week,
                'margin_month': marginality_month
            }
            if old_price_excel_update is not None:
                excel_updates['old_price'] = old_price_excel_update
            self.loader.update_product_in_file(product.sku, excel_updates)

            # Минимальная цена для API
            min_price_for_api = int(round(product.min_price / discount_coef)) if discount_coef else int(round(product.min_price))

            updates_for_ozon.append({
                'product_id': product.product_id,
                'offer_id': product.offer_id or '',
                'price': f"{int(round(result.result_target_price))}",
                'min_price': f"{min_price_for_api}",
                'net_price': f"{int(round(pricing.net_price))}" if pricing.net_price else None,
                'old_price': f"{old_price_for_api}" if old_price_for_api is not None else None,
                'manage_elastic_boosting_through_price': False
            })

        # 6. Отправка в Ozon (только если не dry-run)
        if not dry_run:
            update_results = self.api.update_prices(updates_for_ozon)
        else:
            update_results = {}

        # 7. Обновляем статусы в updates на основе ответа API
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
                # В dry-run считаем, что отправка прошла бы успешно
                upd['status'] = 'updated'
                upd['reason'] = 'dry-run (расчёт выполнен)'
            else:
                # Товар не был отправлен (не было pricing или другой ошибки) – статус уже error
                pass

        # 8. Сохранение истории цен (один раз за цикл)
        if dry_run:
            for product, pricing, result in results_data:
                self.repo.save_price_history(product.sku, pricing, result, real_price=None)
        else:
            # Если отправка была, то после неё запрашиваем индексы для real_price
            if update_results:  # были отправлены цены
                logger.info("Запрашиваем актуальные цены для получения real_price...")
                time.sleep(5)
                fresh_prices = self.api.get_product_prices(valid_ids)
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
                            # Обновляем new_price в отчёте (для единообразия)
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
                # Отправка не удалась (или не было отправки) – сохраняем без real_price
                for product, pricing, result in results_data:
                    self.repo.save_price_history(product.sku, pricing, result, real_price=None)

        # 9. Подсчитываем количество успешно обновлённых товаров
        stats['prices_updated'] = sum(1 for u in updates if u.get('status') == 'updated')

        # 10. Уведомление
        self.notifier.send_detailed_report(updates, stats['errors'], dry_run=dry_run)

        logger.info(f"=== Завершено. Обновлено товаров (успешно отправлено): {stats['prices_updated']} ===")
        return stats