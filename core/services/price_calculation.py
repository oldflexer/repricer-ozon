import logging
from datetime import datetime, time
from typing import List, Optional
from config.settings import TIMEZONE
from core.entities import PriceCalculationResult, PricingData, StrategyInterval

logger = logging.getLogger(__name__)


class PriceCalculationService:
    def __init__(self, default_coefficient: float = 0.5):
        self.default_coefficient = default_coefficient

    def calculate(self, sku: str, pricing: PricingData, rip: float,
                  intervals: List[StrategyInterval],
                  competitor_min_price: Optional[float] = None) -> PriceCalculationResult:
        """
        Вычисляет целевую цену для отправки в Ozon и маржинальность.
        """
        # --- 1. Расчёт коэффициента дисконта ---
        index_prices = []
        index_data = []
        approx_index_price = None
        approx_index_data = None
        if pricing.external_index_data_index and pricing.external_index_data_index != 0:
            index_prices.append(pricing.external_index_data_price)
            index_data.append(pricing.external_index_data_index)
        if pricing.ozon_index_data_index and pricing.ozon_index_data_index != 0:
            index_prices.append(pricing.ozon_index_data_price)
            index_data.append(pricing.ozon_index_data_index)
        if pricing.self_marketplaces_index_data_index and pricing.self_marketplaces_index_data_index != 0:
            index_prices.append(pricing.self_marketplaces_index_data_price)
            index_data.append(pricing.self_marketplaces_index_data_index)

        if index_prices and index_data:
            approx_index_price = sum(index_prices) / len(index_prices)
            approx_index_data = sum(index_data) / len(index_data)

        if approx_index_price and approx_index_data:
            approx_real_price = approx_index_price * approx_index_data
        else:
            approx_real_price = None

        if approx_real_price is not None and pricing.marketing_seller_price and pricing.marketing_seller_price > 0:
            discount_coef = approx_real_price / pricing.marketing_seller_price
        else:
            discount_coef = self.default_coefficient

        target_min_price = rip / discount_coef if discount_coef else rip

        # --- 2. Определение активного интервала стратегии ---
        now = datetime.now(TIMEZONE).time()
        logger.info(
            f"SKU {sku}: текущее время (по TIMEZONE) = {now}, интервалов: {[(i.start, i.end, i.strategy_type, i.percent) for i in intervals]}"
        )

        def time_in_interval(t: time, start: time, end: time) -> bool:
            if start <= end:
                return start <= t <= end
            else:
                # интервал пересекает полночь
                return t >= start or t <= end

        active = next(
            (inv for inv in intervals if time_in_interval(now, inv.start_time, inv.end_time)),
            None
        )

        if active:
            strategy_type = active.strategy_type
            percent = active.percent
            logger.info(f"SKU {sku}: активный интервал {active.start}-{active.end}, стратегия {strategy_type}, процент {percent}")
        else:
            strategy_type = 3
            percent = 0.0
            logger.info(f"SKU {sku}: активный интервал не найден, используется стратегия по умолчанию (Равная, 3)")

        # --- 3. Применение стратегии ---
        if strategy_type == 3:
            result_target_price = target_min_price
            strategy_price = None
            target_strategy_price = None
            reason = "стратегия 'Равная'"
            logger.info(f"SKU {sku}: стратегия 'Равная', результат = {result_target_price:.0f}")
        else:
            # Стратегии 1 (Ниже) и 2 (Выше)
            base_price = None
            source = None
            if competitor_min_price is not None and competitor_min_price > 0:
                base_price = competitor_min_price
                source = "цена конкурента"
            elif pricing.ozon_index_data_price and pricing.ozon_index_data_price != 0:
                base_price = pricing.ozon_index_data_price
                source = "индекс Ozon"

            if base_price is not None:
                if strategy_type == 1:
                    strategy_price = base_price * (1 - percent / 100)
                elif strategy_type == 2:
                    strategy_price = base_price * (1 + percent / 100)
                else:
                    strategy_price = base_price
                target_strategy_price = strategy_price / discount_coef if discount_coef else strategy_price
                result_target_price = target_strategy_price
                reason = f"стратегия {'Ниже' if strategy_type == 1 else 'Выше'} (база = {source}, {base_price:.0f} ₽, процент = {percent})"
                logger.info(
                    f"SKU {sku}: base_price = {base_price:.0f} ({source}), "
                    f"strategy_price = {strategy_price:.0f}, target_strategy_price = {target_strategy_price:.0f}, "
                    f"result_target_price = {result_target_price:.0f}"
                )
            else:
                result_target_price = target_min_price
                strategy_price = None
                target_strategy_price = None
                reason = "базовая цена не найдена, стратегия проигнорирована"
                logger.warning(f"SKU {sku}: базовая цена не найдена (competitor_min_price и ozon_index_data_price отсутствуют), используется РИЦ")

        result_target_price = round(result_target_price)

        # --- 4. Расчёт маржинальности ---
        sales_commission = result_target_price * (pricing.sales_percent_fbs / 100)
        fbs_first_mile_avg = (pricing.fbs_first_mile_min_amount + pricing.fbs_first_mile_max_amount) / 2
        fbs_direct_flow_avg = (pricing.fbs_direct_flow_trans_min_amount + pricing.fbs_direct_flow_trans_max_amount) / 2
        fbs_total = sales_commission + fbs_first_mile_avg + fbs_direct_flow_avg + pricing.fbs_deliv_to_customer_amount + pricing.net_price
        fbo_direct_flow_avg = (pricing.fbo_direct_flow_trans_min_amount + pricing.fbo_direct_flow_trans_max_amount) / 2
        fbo_total = sales_commission + fbo_direct_flow_avg + pricing.fbo_deliv_to_customer_amount + pricing.net_price
        total_costs = (fbs_total + fbo_total) / 2
        if result_target_price > 0:
            marginality = (result_target_price - total_costs) / result_target_price
        else:
            marginality = 0.0

        real_price = result_target_price * discount_coef

        log_details = {
            "approx_real_price": approx_real_price,
            "discount_coef": discount_coef,
            "default_coef_used": approx_real_price is None,
            "target_min_price": target_min_price,
            "strategy_type": strategy_type,
            "strategy_price": strategy_price,
            "target_strategy_price": target_strategy_price,
            "result_target_price": result_target_price,
            "real_price": real_price,
            "ozon_index_data_price": pricing.ozon_index_data_price,
            "competitor_min_price": competitor_min_price,
            "intervals_used": len(intervals),
            "index_prices_count": len(index_prices),
            "reason": reason,
            "marginality_components": {
                "sales_commission": sales_commission,
                "fbo_direct_flow_avg": fbo_direct_flow_avg,
                "fbo_deliv_to_customer": pricing.fbo_deliv_to_customer_amount,
                "fbo_total": fbo_total,
                "fbs_first_mile_avg": fbs_first_mile_avg,
                "fbs_direct_flow_avg": fbs_direct_flow_avg,
                "fbs_deliv_to_customer": pricing.fbs_deliv_to_customer_amount,
                "fbs_total": fbs_total,
                "net_price": pricing.net_price,
                "total_costs": total_costs,
            }
        }

        logger.info(
            f"SKU {sku}: итоговая цена = {result_target_price} ₽, маржинальность = {marginality:.2%}, причина: {reason}"
        )

        return PriceCalculationResult(
            sku=sku,
            target_min_price=target_min_price,
            strategy_price=strategy_price,
            target_strategy_price=target_strategy_price,
            result_target_price=result_target_price,
            marginality=marginality,
            log_details=log_details
        )


def calculate_old_price(price: float, manual_old_price: Optional[float] = None,
                        multiplier: float = 1.5, round_to: int = 100) -> int:
    if manual_old_price is not None and manual_old_price > price * multiplier:
        return int(round(manual_old_price))
    old = price * multiplier
    return int((old + round_to - 1) // round_to * round_to)