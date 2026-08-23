"""
Сервис расчёта целевой цены и маржинальности товара.
"""

from datetime import datetime, time

from config.settings import TIMEZONE
from core.entities import PriceCalculationResult, PricingData, StrategyInterval
from core.enums import StrategyType
from infrastructure.logger import logger


class PriceCalculationService:
    def __init__(self, default_coefficient: float = 0.5) -> None:
        self.default_coefficient = default_coefficient

    def calculate(self, sku: str, pricing: PricingData, rip: float, intervals: list[StrategyInterval], competitor_min_price: float | None = None, real_customer_price: float | None = None) -> PriceCalculationResult:
        index_prices: list[float] = []
        index_data: list[float] = []
        approx_real_price: float | None = None
        discount_coef = self.default_coefficient
        discount_coef_source = "default_env"

        if real_customer_price is not None and real_customer_price > 0 and pricing.marketing_seller_price and pricing.marketing_seller_price > 0:
            discount_coef = real_customer_price / pricing.marketing_seller_price
            discount_coef_source = "real_customer_price"
            logger.info(f"SKU {sku}: discount_coef = {discount_coef:.4f} (source: {discount_coef_source})")
        elif pricing.marketing_seller_price and pricing.marketing_seller_price > 0:
            if pricing.external_index_data_index and pricing.external_index_data_index != 0 and pricing.external_index_data_price is not None:
                index_prices.append(pricing.external_index_data_price)
                index_data.append(pricing.external_index_data_index)
            if pricing.ozon_index_data_index and pricing.ozon_index_data_index != 0 and pricing.ozon_index_data_price is not None:
                index_prices.append(pricing.ozon_index_data_price)
                index_data.append(pricing.ozon_index_data_index)
            if pricing.self_marketplaces_index_data_index and pricing.self_marketplaces_index_data_index != 0 and pricing.self_marketplaces_index_data_price is not None:
                index_prices.append(pricing.self_marketplaces_index_data_price)
                index_data.append(pricing.self_marketplaces_index_data_index)
            if index_prices and index_data:
                approx_index_price = sum(index_prices) / len(index_prices)
                approx_index_data = sum(index_data) / len(index_data)
                if approx_index_price and approx_index_data:
                    approx_real_price = approx_index_price * approx_index_data
            if approx_real_price is not None:
                discount_coef = approx_real_price / pricing.marketing_seller_price
                discount_coef_source = "indexes"
                logger.info(f"SKU {sku}: discount_coef = {discount_coef:.4f} (source: {discount_coef_source})")
        else:
            logger.info(f"SKU {sku}: discount_coef = {discount_coef:.4f} (source: {discount_coef_source})")

        target_min_price = rip / discount_coef if discount_coef else rip
        now = datetime.now(TIMEZONE).time()
        logger.info(f"SKU {sku}: текущее время (по TIMEZONE) = {now}, интервалов: {[(i.start, i.end, i.strategy_type, i.percent) for i in intervals]}")
        active_interval: StrategyInterval | None = None
        for interval in intervals:
            start_h, start_m = map(int, interval.start.split(":"))
            end_h, end_m = map(int, interval.end.split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            now_min = now.hour * 60 + now.minute
            if start_min <= end_min:
                if start_min <= now_min < end_min:
                    active_interval = interval
                    break
            else:
                if now_min >= start_min or now_min < end_min:
                    active_interval = interval
                    break
        if active_interval is None:
            logger.warning(f"SKU {sku}: нет активного интервала стратегии, используем RIP")
            strategy_type = StrategyType.EQUAL
            strategy_percent = 0.0
            base_price = target_min_price
            source = "no_active_interval"
        else:
            strategy_type = active_interval.strategy_type
            strategy_percent = active_interval.percent
            logger.info(f"SKU {sku}: активная стратегия = {strategy_type.name} ({strategy_percent}%), интервал {active_interval.start}-{active_interval.end}")
            if competitor_min_price is not None and competitor_min_price > 0:
                base_price = competitor_min_price
                source = "competitor"
            elif pricing.ozon_index_data_price is not None and pricing.ozon_index_data_price > 0:
                base_price = pricing.ozon_index_data_price
                source = "ozon_index"
            else:
                base_price = target_min_price
                source = "target_min_price"
        if strategy_type == StrategyType.BELOW:
            strategy_price = base_price * (1 - strategy_percent / 100)
        elif strategy_type == StrategyType.ABOVE:
            strategy_price = base_price * (1 + strategy_percent / 100)
        else:
            strategy_price = target_min_price
        target_strategy_price = max(strategy_price, target_min_price)
        result_target_price = target_strategy_price
        reason = f"strategy={strategy_type.name}, base={source}"
        # Расчёт комиссий: процент от цены + фиксированные суммы
        # FBO комиссии
        fbo_sales_commission = result_target_price * pricing.sales_percent_fbo / 100
        fbo_deliv_to_customer_amount = pricing.fbo_deliv_to_customer_amount
        fbo_direct_flow_avg = (pricing.fbo_direct_flow_trans_min_amount + pricing.fbo_direct_flow_trans_max_amount) / 2
        fbo_return_flow_amount = pricing.fbo_return_flow_amount
        fbo_total = fbo_sales_commission + fbo_deliv_to_customer_amount + fbo_direct_flow_avg + fbo_return_flow_amount
        # FBS комиссии
        fbs_sales_commission = result_target_price * pricing.sales_percent_fbs / 100
        fbs_deliv_to_customer_amount = pricing.fbs_deliv_to_customer_amount
        fbs_direct_flow_avg = (pricing.fbs_direct_flow_trans_min_amount + pricing.fbs_direct_flow_trans_max_amount) / 2
        fbs_first_mile_avg = (pricing.fbs_first_mile_min_amount + pricing.fbs_first_mile_max_amount) / 2
        fbs_return_flow_amount = pricing.fbs_return_flow_amount
        fbs_total = fbs_sales_commission + fbs_deliv_to_customer_amount + fbs_direct_flow_avg + fbs_first_mile_avg + fbs_return_flow_amount
        total_costs = (fbs_total + fbo_total) / 2 + pricing.net_price
        real_price = result_target_price * discount_coef
        marginality_real_price = real_customer_price if real_customer_price is not None else real_price
        marginality = (marginality_real_price - total_costs) / marginality_real_price if marginality_real_price > 0 else 0.0
        log_details = {"approx_real_price": approx_real_price, "discount_coef": discount_coef, "discount_coef_source": discount_coef_source, "default_coef_used": discount_coef == self.default_coefficient, "target_min_price": target_min_price, "strategy_type": strategy_type.value, "strategy_type_name": strategy_type.name, "strategy_price": strategy_price, "target_strategy_price": target_strategy_price, "result_target_price": result_target_price, "real_price": real_price, "marginality_real_price": marginality_real_price, "real_customer_price": real_customer_price, "ozon_index_data_price": pricing.ozon_index_data_price, "competitor_min_price": competitor_min_price, "base_price": base_price, "base_price_source": source, "intervals_used": len(intervals), "index_prices_count": len(index_prices), "reason": reason, "marginality_components": {"fbo_sales_commission": fbo_sales_commission, "fbo_deliv_to_customer": fbo_deliv_to_customer_amount, "fbo_direct_flow_avg": fbo_direct_flow_avg, "fbo_return_flow": fbo_return_flow_amount, "fbo_total": fbo_total, "fbs_sales_commission": fbs_sales_commission, "fbs_deliv_to_customer": fbs_deliv_to_customer_amount, "fbs_direct_flow_avg": fbs_direct_flow_avg, "fbs_first_mile_avg": fbs_first_mile_avg, "fbs_return_flow": fbs_return_flow_amount, "fbs_total": fbs_total, "net_price": pricing.net_price, "total_costs": total_costs}}
        logger.info(f"SKU {sku}: итоговая цена = {result_target_price} ₽, маржинальность = {marginality:.2%}, причина: {reason}")
        return PriceCalculationResult(sku=sku, target_min_price=target_min_price, strategy_price=strategy_price, target_strategy_price=target_strategy_price, result_target_price=result_target_price, marginality=marginality, log_details=log_details)

def calculate_old_price(price: float, manual_old_price: float | None = None, multiplier: float = 1.5, round_to: int = 100) -> int:
    if manual_old_price is not None and manual_old_price > price * multiplier:
        return int(round(manual_old_price))
    old = price * multiplier
    return int((old + round_to - 1) // round_to * round_to)