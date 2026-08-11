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

    def calculate(  # noqa: PLR0912, PLR0915, PLR0913, PLR0917
        self,
        sku: str,
        pricing: PricingData,
        rip: float,
        intervals: list[StrategyInterval],
        competitor_min_price: float | None = None,
        real_customer_price: float | None = None,
    ) -> PriceCalculationResult:
        # --- 1. Расчёт коэффициента дисконта ---
        index_prices: list[float] = []
        approx_real_price: float | None = None
        discount_coef = self.default_coefficient

        # Приоритет: реальная цена покупателя из БД (актуальная из шаблона)
        if (
            real_customer_price is not None
            and real_customer_price > 0
            and pricing.marketing_seller_price
            and pricing.marketing_seller_price > 0
        ):
            discount_coef = real_customer_price / pricing.marketing_seller_price
            discount_coef_source = "real_customer_price"
            logger.info(f"SKU {sku}: discount_coef из real_customer_price = {discount_coef:.4f}")
        else:
            # Расчёт через индексы (старая логика)
            index_data: list[float] = []
            approx_index_price: float | None = None
            approx_index_data: float | None = None

            if pricing.external_index_data_index and pricing.external_index_data_index != 0 and pricing.external_index_data_price is not None:
                index_prices.append(pricing.external_index_data_price)
                index_data.append(pricing.external_index_data_index)
            if pricing.ozon_index_data_index and pricing.ozon_index_data_index != 0 and pricing.ozon_index_data_price is not None:
                index_prices.append(pricing.ozon_index_data_price)
                index_data.append(pricing.ozon_index_data_index)
            if (
                pricing.self_marketplaces_index_data_index
                and pricing.self_marketplaces_index_data_index != 0
                and pricing.self_marketplaces_index_data_price is not None
            ):
                index_prices.append(pricing.self_marketplaces_index_data_price)
                index_data.append(pricing.self_marketplaces_index_data_index)

            if index_prices and index_data:
                approx_index_price = sum(index_prices) / len(index_prices)
                approx_index_data = sum(index_data) / len(index_data)

            if approx_index_price and approx_index_data:
                approx_real_price = approx_index_price * approx_index_data
            else:
                approx_real_price = None

            if (
                approx_real_price is not None
                and pricing.marketing_seller_price
                and pricing.marketing_seller_price > 0
            ):
                discount_coef = approx_real_price / pricing.marketing_seller_price
                discount_coef_source = "indexes"
            else:
                discount_coef = self.default_coefficient
                discount_coef_source = "default"
            logger.info(f"SKU {sku}: discount_coef из индексов = {discount_coef:.4f}")

        target_min_price = rip / discount_coef if discount_coef else rip

        # --- 2. Определение активного интервала стратегии ---
        now = datetime.now(TIMEZONE).time()
        logger.info(
            f"SKU {sku}: текущее время (по TIMEZONE) = {now}, "
            f"интервалов: {[(i.start, i.end, i.strategy_type, i.percent) for i in intervals]}"
        )

        def time_in_interval(t: time, start: time, end: time) -> bool:
            if start <= end:
                return start <= t <= end
            return t >= start or t <= end

        active = next(
            (inv for inv in intervals if time_in_interval(now, inv.start_time, inv.end_time)),
            None,
        )

        if active:
            strategy_type = active.strategy_type
            percent = active.percent
            logger.info(
                f"SKU {sku}: активный интервал {active.start}-{active.end}, "
                f"стратегия {strategy_type}, процент {percent}"
            )
        else:
            strategy_type = StrategyType.EQUAL
            percent = 0.0
            logger.info(
                f"SKU {sku}: активный интервал не найден, "
                "используется стратегия по умолчанию (Равная, EQUAL)"
            )

        # --- 3. Применение стратегии ---
        if strategy_type == StrategyType.EQUAL:
            result_target_price = target_min_price
            strategy_price = None
            target_strategy_price = None
            reason = "стратегия 'Равная'"
            logger.info(f"SKU {sku}: стратегия 'Равная', результат = {result_target_price:.0f}")
        else:
            base_price = None
            source = None
            if competitor_min_price is not None and competitor_min_price > 0:
                base_price = competitor_min_price
                source = "цена конкурента"
            elif pricing.ozon_index_data_price and pricing.ozon_index_data_price != 0:
                base_price = pricing.ozon_index_data_price
                source = "индекс Ozon"

            if base_price is not None:
                if strategy_type == StrategyType.BELOW:
                    strategy_price = base_price * (1 - percent / 100)
                elif strategy_type == StrategyType.ABOVE:
                    strategy_price = base_price * (1 + percent / 100)
                else:
                    strategy_price = base_price

                target_strategy_price = (
                    strategy_price / discount_coef if discount_coef else strategy_price
                )
                result_target_price = target_strategy_price
                reason = (
                    f"стратегия {'Ниже' if strategy_type == StrategyType.BELOW else 'Выше'} "
                    f"(база = {source}, {base_price:.0f} ₽, процент = {percent})"
                )
                logger.info(
                    f"SKU {sku}: base_price = {base_price:.0f} ({source}), "
                    f"strategy_price = {strategy_price:.0f}, "
                    f"target_strategy_price = {target_strategy_price:.0f}, "
                    f"result_target_price = {result_target_price:.0f}"
                )
            else:
                result_target_price = target_min_price
                strategy_price = None
                target_strategy_price = None
                reason = "базовая цена не найдена, стратегия проигнорирована"
                logger.warning(
                    f"SKU {sku}: базовая цена не найдена "
                    "(competitor_min_price и ozon_index_data_price отсутствуют), используется РИЦ"
                )

        result_target_price = round(result_target_price)

        # --- 4. Расчёт маржинальности ---
        fbo_sales_commission = result_target_price * (pricing.sales_percent_fbo / 100)
        fbo_deliv_to_customer_amount = pricing.fbo_deliv_to_customer_amount
        fbo_direct_flow_avg = (
            pricing.fbo_direct_flow_trans_min_amount + pricing.fbo_direct_flow_trans_max_amount
        ) / 2
        fbo_return_flow_amount = pricing.fbo_return_flow_amount
        fbo_total = (
            fbo_sales_commission
            + fbo_deliv_to_customer_amount
            + fbo_direct_flow_avg
            + fbo_return_flow_amount
        )

        fbs_sales_commission = result_target_price * (pricing.sales_percent_fbs / 100)
        fbs_deliv_to_customer_amount = pricing.fbs_deliv_to_customer_amount
        fbs_direct_flow_avg = (
            pricing.fbs_direct_flow_trans_min_amount + pricing.fbs_direct_flow_trans_max_amount
        ) / 2
        fbs_first_mile_avg = (
            pricing.fbs_first_mile_min_amount + pricing.fbs_first_mile_max_amount
        ) / 2
        fbs_return_flow_amount = pricing.fbs_return_flow_amount

        fbs_total = (
            fbs_sales_commission
            + fbs_deliv_to_customer_amount
            + fbs_direct_flow_avg
            + fbs_first_mile_avg
            + fbs_return_flow_amount
        )

        total_costs = (fbs_total + fbo_total) / 2 + pricing.net_price

        real_price = result_target_price * discount_coef

        marginality = (real_price - total_costs) / real_price if real_price > 0 else 0.0

        log_details = {
            "approx_real_price": approx_real_price,
            "discount_coef": discount_coef,
            "discount_coef_source": discount_coef_source,
            "default_coef_used": discount_coef == self.default_coefficient,
            "target_min_price": target_min_price,
            "strategy_type": strategy_type.value,
            "strategy_type_name": strategy_type.name,
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
                "fbo_sales_commission": fbo_sales_commission,
                "fbo_deliv_to_customer": fbo_deliv_to_customer_amount,
                "fbo_direct_flow_avg": fbo_direct_flow_avg,
                "fbo_return_flow": fbo_return_flow_amount,
                "fbo_total": fbo_total,
                "fbs_sales_commission": fbs_sales_commission,
                "fbs_deliv_to_customer": fbs_deliv_to_customer_amount,
                "fbs_direct_flow_avg": fbs_direct_flow_avg,
                "fbs_first_mile_avg": fbs_first_mile_avg,
                "fbs_return_flow": fbs_return_flow_amount,
                "fbs_total": fbs_total,
                "net_price": pricing.net_price,
                "total_costs": total_costs,
            },
        }

        logger.info(
            f"SKU {sku}: итоговая цена = {result_target_price} ₽, "
            f"маржинальность = {marginality:.2%}, причина: {reason}"
        )

        return PriceCalculationResult(
            sku=sku,
            target_min_price=target_min_price,
            strategy_price=strategy_price,
            target_strategy_price=target_strategy_price,
            result_target_price=result_target_price,
            marginality=marginality,
            log_details=log_details,
        )


def calculate_old_price(
    price: float,
    manual_old_price: float | None = None,
    multiplier: float = 1.5,
    round_to: int = 100,
) -> int:
    if manual_old_price is not None and manual_old_price > price * multiplier:
        return int(round(manual_old_price))
    old = price * multiplier
    return int((old + round_to - 1) // round_to * round_to)
