import re

# Read the file
with open('core/services/price_calculation.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the active = next(...) block indentation
content = content.replace(
    '''        active = next(
                    (
                        inv
                        for inv in intervals
                        if time_in_interval(now, inv.start_time, inv.end_time)
                    ),
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
                if strategy_type == StrategyType.EQUAL:''',
    '''        active = next(
            (
                inv
                for inv in intervals
                if time_in_interval(now, inv.start_time, inv.end_time)
            ),
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
        if strategy_type == StrategyType.EQUAL:'''
)

# Fix the log_details block indentation
content = content.replace(
    '''        log_details = {
                    "approx_real_price": approx_real_price,
                    "discount_coef": discount_coef,
                    "default_coef_used": approx_real_price is None,
                    "target_min_price": target_min_price,
                    "strategy_type": strategy_type.value,  # Store int value for DB
                    "strategy_type_name": strategy_type.name,  # Store enum name for readability
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
                    },
                }''',
    '''        log_details = {
            "approx_real_price": approx_real_price,
            "discount_coef": discount_coef,
            "default_coef_used": approx_real_price is None,
            "target_min_price": target_min_price,
            "strategy_type": strategy_type.value,  # Store int value for DB
            "strategy_type_name": strategy_type.name,  # Store enum name for readability
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
            },
        }'''
)

# Write back
with open('core/services/price_calculation.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed!')