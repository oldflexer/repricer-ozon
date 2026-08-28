"""
Шаг 9: Отправка email отчёта.
"""

from core.pipeline.steps.base import PipelineContext, PipelineStep
from core.protocols.notifier import INotifier
from infrastructure.logger import logger


class SendReportStep(PipelineStep):
    """Шаг 9: Отправка email отчёта."""

    def __init__(self, notifier: INotifier):
        self.notifier = notifier

    @property
    def name(self) -> str:
        return "SendReport"

    async def execute(self, context: PipelineContext) -> None:
        logger.info("Pipeline: Sending email report")

        # Формируем данные для отчёта
        updates = []
        errors = []

        for product in context.products:
            result = context.calculation_results.get(str(product.sku))
            if not result:
                continue

            api_result = (
                context.api_results.get(product.product_id, {}) if product.product_id else {}
            )
            updated = api_result.get("updated", False) if not context.dry_run else True

            updates.append(
                {
                    "sku": str(product.sku),
                    "name": product.product_name or "",
                    "old_price": product.current_price.rubles_float if product.current_price else 0,
                    "new_price": int(
                        round(
                            result.result_target_price
                            * result.log_details.get("discount_coef", 1.0)
                        )
                    ),
                    "min_price": int(
                        round(
                            product.min_price.rubles_float
                            / result.log_details.get("discount_coef", 1.0)
                        )
                    ),
                    "marginality": result.marginality,
                    "updated": updated,
                    "strategy": result.log_details.get("strategy_type_name", "Unknown"),
                    "discount_coef": result.log_details.get("discount_coef", 0),
                }
            )

            if not updated and not context.dry_run:
                for err in api_result.get("errors", []):
                    errors.append(f"{product.sku}: {err.get('message', 'Unknown error')}")

        try:
            if hasattr(self.notifier, "send_detailed_report"):
                self.notifier.send_detailed_report(updates, errors, dry_run=context.dry_run)
            else:
                updated_count = sum(1 for u in updates if u.get("status") == "updated")
                self.notifier.notify_cycle_complete(updated_count, errors)
            logger.info("Pipeline: Email report sent")
        except Exception as e:
            context.add_error(f"Failed to send email report: {e}")
