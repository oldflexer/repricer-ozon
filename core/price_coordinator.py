"""
Координатор репрайсинга – управляет полным циклом обновления цен.

Содержит логику загрузки товаров из Excel, получения данных из Ozon API,
расчёта целевых цен, отправки обновлений и сохранения истории.
"""

from collections.abc import Callable
from typing import Any

from config.settings import settings
from core.entities import ProductInfo
from core.mappers import build_price_update_request
from core.repository import IProductRepository
from core.services import HistoryService, PriceCalculationService, calculate_old_price
from infrastructure.logger import logger


class PriceUpdateCoordinator:
    """
    Управляет полным потоком репрайсинга.

    Шаги:
        1. Проверка доступности Excel-файла.
        2. Загрузка товаров из Excel.
        3. Получение product_id, offer_id, названий из Ozon API.
        4. Сохранение стратегий в БД.
        5. Получение текущих цен, индексов и комиссий из API.
        6. Для каждого товара: расчёт целевой цены, маржинальности,
           обновление Excel и формирование запроса на обновление.
        7. Отправка цен в Ozon (если не dry-run).
        8. Обновление статусов и сохранение истории цен.
        9. Автоматическая очистка устаревших записей в БД.
        10. Отправка email-отчёта.
    """

    def __init__(
        self,
        repository: IProductRepository,
        api_client,
        loader,
        notifier,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        """
        Инициализирует координатор.

        Args:
            repository: Репозиторий для работы с БД.
            api_client: Клиент Ozon API.
            loader: Загрузчик данных из Excel.
            notifier: Сервис уведомлений (email).
            progress_callback: Опциональный колбэк для отображения прогресса (в UI).
        """
        self.repo = repository
        self.api = api_client
        self.loader = loader
        self.notifier = notifier
        self.progress_callback = progress_callback
        self.calc = PriceCalculationService(default_coefficient=settings.COEFFICIENT_OZON)
        self.history_service = HistoryService(repository)

    async def run(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Запускает полный цикл репрайсинга.

        Args:
            dry_run: Если True, цены не отправляются в Ozon (только расчёт и логирование).

        Returns:
            Словарь со статистикой:
                - products_loaded: количество загруженных товаров.
                - prices_updated: количество успешно обновлённых товаров.
                - errors: список ошибок.
                - warnings: список предупреждений.
        """
        stats = {"products_loaded": 0, "prices_updated": 0, "errors": [], "warnings": []}
        updates = []

        # Проверка доступности Excel
        from infrastructure.file_utils import wait_for_excel_available

        if not wait_for_excel_available(settings.DATA_FILE_PATH):
            logger.error("Excel-файл занят другим процессом, репрайсинг отменён")
            self.notifier.send_detailed_report([], ["Excel-файл занят"], dry_run=dry_run)
            return stats

        # 1. Загрузка Excel
        if self.progress_callback:
            self.progress_callback(0, 1, "Загрузка Excel...")
        products, warnings = self.loader.load()
        stats["products_loaded"] = len(products)
        stats["warnings"] = warnings
        if not products:
            self.notifier.send_detailed_report([], stats["errors"], dry_run=dry_run)
            return stats

        # 2. Получение product_id и названий
        if self.progress_callback:
            self.progress_callback(0, 1, "Получение product_id из Ozon...")
        sku_list = [p.sku for p in products]
        product_map = await self.api.get_product_ids_by_skus(sku_list)
        for p in products:
            info = product_map.get(p.sku, {})
            p.product_id = info.get("product_id")
            p.offer_id = info.get("offer_id")
            if info.get("product_name"):
                p.product_name = info.get("product_name")
            self.repo.upsert_product(p)
            if p.product_name:
                self.loader.update_product_in_file(p.sku, {"product_name": p.product_name})

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
                self.progress_callback(idx + 1, total, f"Обработка {product.sku}...")

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
                competitor_min_price=product.competitor_min_price,
                real_customer_price=product.real_customer_price,
            )
            results_data.append((product, pricing, result))

            avg_week = self.repo.get_average_marginality(product.sku, 7)
            marginality_week = avg_week if avg_week is not None else result.marginality
            avg_month = self.repo.get_average_marginality(product.sku, 30)
            marginality_month = avg_month if avg_month is not None else result.marginality
            self.repo.save_marginality(
                product.sku, result.marginality, marginality_week, marginality_month
            )

            discount_coef = result.log_details.get("discount_coef", 1.0)
            real_price = result.result_target_price * discount_coef
            current_price_excel = int(round(real_price))

            hist = self.repo.get_price_history(product.sku)
            old_customer_price = hist[-1].get("customer_price") if hist else None
            if old_customer_price is not None:
                old_customer_price = int(round(old_customer_price))

            updates.append(self._pending_update(product, old_customer_price, current_price_excel))

            old_price_for_api = calculate_old_price(
                price=result.result_target_price,
                manual_old_price=None,
                multiplier=settings.OLD_PRICE_MULTIPLIER,
                round_to=settings.PRICE_ROUND_UP_TO,
            )

            excel_updates = self.loader.build_excel_updates(
                product, result, marginality_week, marginality_month, old_price_for_api
            )
            self.loader.update_product_in_file(product.sku, excel_updates)

            # Определяем минимальную цену для API
            if result.strategy_price is not None:
                min_price_for_api = int(round(result.result_target_price))
            else:
                min_price_for_api = (
                    int(round(product.min_price / discount_coef))
                    if discount_coef
                    else int(round(product.min_price))
                )

            # Правило Ozon: min_price >= price * 0.5
            price_for_api = int(round(result.result_target_price))
            min_allowed = int(price_for_api * 0.5)
            if min_price_for_api < min_allowed:
                old_min = min_price_for_api
                min_price_for_api = min_allowed
                logger.warning(
                    f"SKU {product.sku}: min_price скорректирован с {old_min} до {min_price_for_api} "
                    "(правило Ozon 50%)"
                )

            net_price_val = (
                int(round(product.cost_price)) if product.cost_price else pricing.net_price
            )

            req = build_price_update_request(
                product_id=product.product_id,
                price=int(round(result.result_target_price)),
                min_price=min_price_for_api,
                net_price=net_price_val,
                old_price=old_price_for_api,
                manage_elastic_boosting=settings.MANAGE_ELASTIC_BOOSTING,
            )
            updates_for_ozon.append(
                {
                    "product_id": req.product_id,
                    "offer_id": product.offer_id or "",
                    "price": str(req.price),
                    "min_price": str(req.min_price),
                    "net_price": str(req.net_price) if req.net_price else None,
                    "old_price": str(req.old_price) if req.old_price else None,
                    "manage_elastic_boosting_through_price": req.manage_elastic_boosting_through_price,
                }
            )

        # 6. Отправка цен
        if not dry_run:
            if self.progress_callback:
                self.progress_callback(total, total, "Отправка цен в Ozon...")
            update_results = await self.api.update_prices(updates_for_ozon)
        else:
            update_results = {}

        # 7. Финальное обновление статусов
        self._finalize_updates(updates, products, update_results, dry_run, stats)

        # 8. Сохранение истории цен
        await self.history_service.save_history(results_data, updates, dry_run, update_results)

        stats["prices_updated"] = sum(1 for u in updates if u.get("status") == "updated")
        self.notifier.send_detailed_report(updates, stats["errors"], dry_run=dry_run)

        # 9. Автоочистка БД (используем настройки)
        deleted = self.repo.auto_cleanup_if_needed(
            months=settings.CLEANUP_MONTHS,
            days_threshold=settings.CLEANUP_DAYS_THRESHOLD,
        )
        if deleted:
            logger.info(f"Автоматическая очистка БД: удалено {deleted} старых записей")

        logger.info(f"=== Завершено. Обновлено товаров: {stats['prices_updated']} ===")
        return stats

    # ------------------------------------------------------------------
    # Вспомогательные приватные методы
    # ------------------------------------------------------------------

    def _error_update(self, product: ProductInfo, reason: str) -> dict[str, Any]:
        """Формирует запись об ошибке для отчёта."""
        return {
            "sku": product.sku,
            "product_name": product.product_name or "",
            "old_price": None,
            "new_price": None,
            "status": "error",
            "reason": reason,
        }

    def _pending_update(
        self, product: ProductInfo, old_price: float | None, new_price: float
    ) -> dict[str, Any]:
        """Формирует запись о pending-обновлении (перед отправкой)."""
        return {
            "sku": product.sku,
            "product_name": product.product_name or "",
            "old_price": old_price,
            "new_price": new_price,
            "status": "pending",
            "reason": None,
        }

    def _finalize_updates(
        self,
        updates: list[dict[str, Any]],
        products: list[ProductInfo],
        update_results: dict[int, dict],
        dry_run: bool,
        stats: dict[str, Any],
    ) -> None:
        """
        Обновляет статусы записей после ответа API (или dry-run).

        Args:
            updates: Список записей об обновлениях.
            products: Список товаров.
            update_results: Результаты от API (product_id -> {updated, errors}).
            dry_run: Флаг сухого запуска.
            stats: Словарь статистики (для добавления ошибок).
        """
        for upd in updates:
            product = next((p for p in products if p.sku == upd["sku"]), None)
            if product and product.product_id in update_results:
                res = update_results[product.product_id]
                if res["updated"]:
                    upd["status"] = "updated"
                    upd["reason"] = None
                else:
                    upd["status"] = "error"
                    errors_str = ", ".join([e.get("message", str(e)) for e in res["errors"]])
                    upd["reason"] = f"Ошибка API: {errors_str}"
                    stats["errors"].append(f"{upd['sku']}: {errors_str}")
            elif dry_run:
                upd["status"] = "updated"
                upd["reason"] = "dry-run (расчёт выполнен)"
