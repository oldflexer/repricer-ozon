"""
Сервис для отправки email-уведомлений.

Отправляет текстовые письма и письма с CSV-вложениями.
Используется для уведомлений о результатах репрайсинга.
"""

import csv
import io
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings import settings
from infrastructure.logger import logger


class MailNotifier:
    """
    Отправляет email-уведомления через SMTP.

    Поддерживает:
        - plain-text письма,
        - письма с CSV-вложением,
        - детализированные отчёты с авто-определением формата.
    """

    def __init__(self) -> None:
        """Инициализирует параметры SMTP из настроек."""
        self.host: str = settings.SMTP_HOST
        self.port: int = settings.SMTP_PORT
        self.user: str = settings.SMTP_USER
        self.password: str = settings.SMTP_PASSWORD
        self.sender: str = settings.SENDER_EMAIL or settings.SMTP_USER
        self.recipient: str = settings.RECIPIENT_EMAIL

    def send_message(self, subject: str, body: str) -> bool:
        """
        Отправляет простое текстовое письмо.

        Args:
            subject: Тема письма.
            body: Тело письма (plain text).

        Returns:
            True в случае успеха, иначе False.
        """
        if not self._check_config():
            return False

        msg = MIMEMultipart()
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        return self._send(msg)

    def send_message_with_attachment(
        self, subject: str, body: str, filename: str, csv_content: str
    ) -> bool:
        """
        Отправляет письмо с CSV-вложением.

        Args:
            subject: Тема письма.
            body: Текстовое тело письма.
            filename: Имя файла во вложении.
            csv_content: Содержимое CSV (строка).

        Returns:
            True в случае успеха, иначе False.
        """
        if not self._check_config():
            return False

        msg = MIMEMultipart()
        msg["From"] = self.sender
        msg["To"] = self.recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        part = MIMEBase("application", "octet-stream")
        part.set_payload(csv_content.encode("utf-8-sig"))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

        return self._send(msg)

    def send_detailed_report(  # noqa: PLR0912
        self, updates: list[dict], errors: list[str], dry_run: bool = False
    ) -> None:
        """
        Отправляет детализированный отчёт о результатах репрайсинга.

        Если количество товаров превышает NOTIFICATION_MAX_DETAILS,
        отправляет CSV-вложение вместо детализации в теле письма.

        Args:
            updates: Список словарей с информацией об обновлениях.
            errors: Список общих ошибок.
            dry_run: Флаг тестового запуска (добавляет пометку в тему).
        """
        if dry_run:
            subject = f"[DRY-RUN] Репрайсер {settings.INSTANCE_NAME} – результаты расчёта (цены не отправлялись)"
        else:
            updated_count = sum(1 for u in updates if u.get("status") == "updated")
            subject = f"Репрайсер {settings.INSTANCE_NAME} – цикл завершён. Обновлено товаров: {updated_count}"

        lines = []
        if dry_run:
            lines.append("*** ЭТО ТЕСТОВЫЙ ЗАПУСК (DRY-RUN). ЦЕНЫ НЕ ОТПРАВЛЯЛИСЬ. ***\n")

        if len(updates) > settings.NOTIFICATION_MAX_DETAILS:
            lines.append(
                f"Количество товаров ({len(updates)}) превышает лимит детализации "
                f"({settings.NOTIFICATION_MAX_DETAILS})."
            )
            lines.append("Полные данные прилагаются в CSV-файле.\n")
            csv_data = self._generate_csv(updates)
            self.send_message_with_attachment(subject, "\n".join(lines), "report.csv", csv_data)
            return

        lines.append("Детализация по товарам:")
        lines.append("")
        for u in updates:
            sku = u.get("sku", "N/A")
            name = u.get("product_name", "")
            status = u.get("status", "unknown")
            old_price = u.get("old_price")
            new_price = u.get("new_price")
            reason = u.get("reason")
            if status == "updated":
                if old_price is not None and new_price is not None:
                    lines.append(f"✅ {sku} – {name}: {old_price:.0f} → {new_price:.0f}")
                elif new_price is not None:
                    lines.append(f"✅ {sku} – {name}: установлена цена {new_price:.0f}")
                else:
                    lines.append(f"✅ {sku} – {name}: обновлено")
            elif status == "error":
                lines.append(f"❌ {sku} – {name}: ошибка – {reason}")
            else:
                lines.append(f"❓ {sku} – {name}: неизвестный статус {status}")

        if errors:
            lines.append("\n❌ Общие ошибки:")
            for err in errors:
                lines.append(f"  - {err}")

        body = "\n".join(lines)
        self.send_message(subject, body)

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------

    def _check_config(self) -> bool:
        """Проверяет, что все необходимые SMTP-параметры заданы."""
        if not all([self.host, self.user, self.password, self.sender, self.recipient]):
            logger.warning("Не настроены параметры SMTP для отправки email")
            return False
        return True

    def _send(self, msg: MIMEMultipart) -> bool:
        """Отправляет письмо через SMTP."""
        try:
            server = smtplib.SMTP(self.host, self.port, timeout=10)
            server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.sender, [self.recipient], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False

    def _generate_csv(self, updates: list[dict]) -> str:
        """Генерирует CSV-строку из списка обновлений."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["SKU", "Название", "Старая цена", "Новая цена", "Статус", "Причина"])
        for u in updates:
            writer.writerow(
                [
                    u.get("sku", ""),
                    u.get("product_name", ""),
                    u.get("old_price", ""),
                    u.get("new_price", ""),
                    u.get("status", ""),
                    u.get("reason", ""),
                ]
            )
        return output.getvalue()

    # ------------------------------------------------------------------
    # Устаревшие методы (для обратной совместимости)
    # ------------------------------------------------------------------

    def notify_cycle_complete(self, updated_count: int, errors: list[str] | None = None) -> None:
        """
        Устаревший метод. Отправляет краткое уведомление о завершении цикла.

        Args:
            updated_count: Количество обновлённых товаров.
            errors: Список ошибок (опционально).
        """
        subject = f"Репрайсер – цикл завершён. Обновлено {updated_count} товаров"
        body = f"Обновлено цен: {updated_count}\n"
        if errors:
            body += "\n".join(errors)
        self.send_message(subject, body)

    def notify_critical_event(self, event: str) -> None:
        """
        Устаревший метод. Отправляет уведомление о критическом событии.

        Args:
            event: Текст события.
        """
        subject = "Репрайсер – критическое событие"
        self.send_message(subject, event)
