import re

# Read the file
with open('infrastructure/excel_loader.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the indentation issue with _parse_strategy_value
content = content.replace(
    '''    @staticmethod
        def _parse_strategy_value(value) -> StrategyType:''',
    '''    @staticmethod
    def _parse_strategy_value(value) -> StrategyType:'''
)

# Fix the if not intervals block indentation
content = content.replace(
    '''            if not intervals:
                            warnings.append(
                                f"SKU {sku}: не задано ни одного интервала стратегии, "
                                "используется стратегия по умолчанию 'Равная'"
                            )
                            intervals = [
                                StrategyInterval(start="00:00", end="23:59", strategy_type=StrategyType.EQUAL, percent=0.0)
                            ]''',
    '''            if not intervals:
                warnings.append(
                    f"SKU {sku}: не задано ни одного интервала стратегии, "
                    "используется стратегия по умолчанию 'Равная'"
                )
                intervals = [
                    StrategyInterval(start="00:00", end="23:59", strategy_type=StrategyType.EQUAL, percent=0.0)
                ]'''
)

# Fix the strategy_col/percent_col indentation
content = content.replace(
    '''            strategy_col = self._find_column(columns, [f"стратегия {i}", f"стратеги {i}"])
                        strategy_val = row.get(strategy_col) if strategy_col else None
                        strategy = self._parse_strategy_value(strategy_val)

                        percent_col = self._find_column(columns, [f"процент {i}", f"percent_{i}"])
                        percent = 0.0
                        if percent_col:
                            percent_val = row.get(percent_col)
                            if pd.notna(percent_val):
                                try:
                                    percent = float(percent_val)
                                    if strategy in (StrategyType.BELOW, StrategyType.ABOVE) and (percent < 0 or percent > 100):
                                        warnings.append(
                                            f"Интервал {i}: процент {percent} выходит за пределы 0-100, используется 0"
                                        )
                                        percent = 0.0
                                except Exception:
                                    warnings.append(
                                        f"Интервал {i}: процент '{percent_val}' не число, используется 0"
                                    )

                        intervals.append(
                            StrategyInterval(
                                start=start, end=end, strategy_type=strategy, percent=percent
                            )
                        )''',
    '''            strategy_col = self._find_column(columns, [f"стратегия {i}", f"стратеги {i}"])
            strategy_val = row.get(strategy_col) if strategy_col else None
            strategy = self._parse_strategy_value(strategy_val)

            percent_col = self._find_column(columns, [f"процент {i}", f"percent_{i}"])
            percent = 0.0
            if percent_col:
                percent_val = row.get(percent_col)
                if pd.notna(percent_val):
                    try:
                        percent = float(percent_val)
                        if strategy in (StrategyType.BELOW, StrategyType.ABOVE) and (percent < 0 or percent > 100):
                            warnings.append(
                                f"Интервал {i}: процент {percent} выходит за пределы 0-100, используется 0"
                            )
                            percent = 0.0
                    except Exception:
                        warnings.append(
                            f"Интервал {i}: процент '{percent_val}' не число, используется 0"
                        )

            intervals.append(
                StrategyInterval(
                    start=start, end=end, strategy_type=strategy, percent=percent
                )
            )'''
)

# Write back
with open('infrastructure/excel_loader.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed!')