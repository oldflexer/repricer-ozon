"""
Бизнес-правила ценообразования Ozon (Domain Rules).

Инкапсулирует все правила и ограничения, накладываемые Ozon API,
в едином месте для лёгкого изменения и тестирования.
"""

from dataclasses import dataclass
from decimal import Decimal

from core.domain.value_objects import DiscountCoefficient, Money, Percentage


@dataclass(frozen=True, slots=True)
class OzonPricingRules:
    """
    Правила ценообразования Ozon.

    Все магические числа и бизнес-ограничения собраны здесь.
    """

    # Минимальное отношение min_price к price (правило Ozon: min_price >= price * 0.5)
    min_price_ratio: Decimal = Decimal("0.5")

    # Множитель для расчёта старой цены (old_price = price * multiplier)
    old_price_multiplier: Decimal = Decimal("1.5")

    # Шаг округления старой цены (в рублях)
    old_price_round_step: int = 100

    # Коэффициент дисконта по умолчанию (если нет индексов и реальной цены)
    default_discount_coef: DiscountCoefficient = DiscountCoefficient.from_ratio("0.5")

    # Флаг управления эластичным бустингом через цену
    manage_elastic_boosting: bool = False

    # Пауза после обновления цен перед запросом актуальных цен (секунды)
    wait_after_update_seconds: int = 10

    # Количество интервалов стратегий в расписании
    schedule_intervals_count: int = 4

    # Префикс колонки цены конкурента в Excel
    competitor_price_column_prefix: str = "Цена"

    # Префикс колонки URL конкурента в Excel
    competitor_url_column_prefix: str = "Ссылка"

    # Максимальное количество конкурентов
    max_competitors: int = 5

    # Настройки батчинга API
    api_batch_size: int = 100
    api_batch_delay: float = 0.5
    api_max_retries: int = 3
    api_http_timeout: float = 30.0

    # Настройки парсера
    parser_retries: int = 3
    parser_request_delay_min: float = 2.0
    parser_request_delay_max: float = 5.0
    parser_lock_timeout: int = 300

    # Настройки очистки БД
    cleanup_months: int = 3
    cleanup_days_threshold: int = 1

    def validate_min_price(self, price: Money, min_price: Money) -> Money:
        """
        Валидирует и при необходимости корректирует min_price согласно правилу Ozon.

        Правило: min_price >= price * min_price_ratio

        Args:
            price: Устанавливаемая цена
            min_price: Минимальная цена из Excel/стратегии

        Returns:
            Скорректированная min_price (если была ниже допустимого минимума)
        """
        min_allowed = price * self.min_price_ratio
        return min_price.max(min_allowed)

    def calculate_old_price(self, price: Money, manual_old_price: Money | None = None) -> Money:
        """
        Рассчитывает старую цену (цена до скидки).

        Логика:
        1. Если задана ручная старая цена И она > price * multiplier -> используем её
        2. Иначе: price * multiplier, округлённый вверх до old_price_round_step рублей

        Args:
            price: Текущая цена
            manual_old_price: Ручная старая цена из Excel (опционально)

        Returns:
            Старая цена для отправки в Ozon
        """
        if manual_old_price is not None and manual_old_price > price * self.old_price_multiplier:
            return manual_old_price

        calculated = price * self.old_price_multiplier
        return calculated.round_to(self.old_price_round_step)

    def calculate_target_min_price(self, rip: Money, discount_coef: DiscountCoefficient) -> Money:
        """
        Рассчитывает целевую минимальную цену (target_min_price = RIP / discount_coef).

        Args:
            rip: РИЦ (рекомендованная интернет-цена / минимальная цена из Excel)
            discount_coef: Коэффициент дисконта

        Returns:
            Целевая минимальная цена для маркетинговой цены
        """
        return rip / discount_coef.value

    def apply_strategy_below(self, base_price: Money, percent: Percentage) -> Money:
        """Стратегия 'Ниже': base_price * (1 - percent)."""
        return base_price * (Decimal("1") - percent.ratio)

    def apply_strategy_above(self, base_price: Money, percent: Percentage) -> Money:
        """Стратегия 'Выше': base_price * (1 + percent)."""
        return base_price * (Decimal("1") + percent.ratio)

    def apply_strategy_equal(self, target_min_price: Money) -> Money:
        """Стратегия 'Равная': возвращает target_min_price как есть."""
        return target_min_price

    @classmethod
    def from_settings(cls, settings) -> "OzonPricingRules":
        """Создаёт экземпляр из объекта настроек приложения."""
        return cls(
            min_price_ratio=Decimal(str(settings.COEFFICIENT_OZON))
            if hasattr(settings, "COEFFICIENT_OZON")
            else Decimal("0.5"),
            old_price_multiplier=Decimal(str(getattr(settings, "OLD_PRICE_MULTIPLIER", 1.5))),
            old_price_round_step=getattr(settings, "PRICE_ROUND_UP_TO", 100),
            default_discount_coef=DiscountCoefficient.from_ratio(
                str(getattr(settings, "COEFFICIENT_OZON", 0.5))
            ),
            manage_elastic_boosting=getattr(settings, "MANAGE_ELASTIC_BOOSTING", False),
            wait_after_update_seconds=getattr(settings, "WAIT_AFTER_UPDATE_SECONDS", 10),
            schedule_intervals_count=getattr(settings, "SCHEDULE_INTERVALS_COUNT", 4),
            competitor_price_column_prefix=getattr(
                settings, "COMPETITOR_PRICE_COLUMN_PREFIX", "Цена"
            ),
            competitor_url_column_prefix=getattr(
                settings, "COMPETITOR_URL_COLUMN_PREFIX", "Ссылка"
            ),
            max_competitors=getattr(settings, "MAX_COMPETITORS", 5),
            api_batch_size=getattr(settings, "API_BATCH_SIZE", 100),
            api_batch_delay=getattr(settings, "API_BATCH_DELAY", 0.5),
            api_max_retries=getattr(settings, "API_MAX_RETRIES", 3),
            api_http_timeout=getattr(settings, "API_HTTP_TIMEOUT", 30.0),
            parser_retries=getattr(settings, "PARSER_RETRIES", 3),
            parser_request_delay_min=getattr(settings, "PARSER_REQUEST_DELAY_MIN", 2.0),
            parser_request_delay_max=getattr(settings, "PARSER_REQUEST_DELAY_MAX", 5.0),
            parser_lock_timeout=getattr(settings, "PARSER_LOCK_TIMEOUT", 300),
            cleanup_months=getattr(settings, "CLEANUP_MONTHS", 3),
            cleanup_days_threshold=getattr(settings, "CLEANUP_DAYS_THRESHOLD", 1),
        )


# Singleton instance для использования в домене
_pricing_rules: OzonPricingRules | None = None


def get_pricing_rules() -> OzonPricingRules:
    """Возвращает глобальный экземпляр правил (ленивая инициализация)."""
    global _pricing_rules
    if _pricing_rules is None:
        from config.settings import settings

        _pricing_rules = OzonPricingRules.from_settings(settings)
    return _pricing_rules


def set_pricing_rules(rules: OzonPricingRules) -> None:
    """Устанавливает глобальные правила (для тестов)."""
    global _pricing_rules
    _pricing_rules = rules
