import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import List, Optional, Dict

from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SENDER_EMAIL, RECIPIENT_EMAIL
)

logger = logging.getLogger(__name__)


class MailNotifier:
    def __init__(self):
        self.host: str = SMTP_HOST or ''
        self.port: int = SMTP_PORT
        self.user: str = SMTP_USER or ''
        self.password: str = SMTP_PASSWORD or ''
        self.sender: str = SENDER_EMAIL or ''
        self.recipient: str = RECIPIENT_EMAIL or ''

    def send_message(self, subject: str, body: str) -> bool:
        if not self.host or not self.user or not self.password or not self.sender or not self.recipient:
            logger.warning("Не настроены параметры SMTP для отправки email")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = self.recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

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

    def send_detailed_report(self, updates: List[Dict], errors: List[str], dry_run: bool = False):
        """Отправляет детальный отчёт о каждом товаре."""
        if dry_run:
            subject = "[DRY-RUN] Репрайсер – результаты расчёта (цены не отправлялись)"
        else:
            updated_count = sum(1 for u in updates if u.get('status') == 'updated')
            subject = f"Репрайсер – цикл завершён. Обновлено товаров: {updated_count}"

        lines = []
        if dry_run:
            lines.append("*** ЭТО ТЕСТОВЫЙ ЗАПУСК (DRY-RUN). ЦЕНЫ НЕ ОТПРАВЛЯЛИСЬ. ***\n")
        lines.append("Детализация по товарам:")
        lines.append("")

        for u in updates:
            sku = u.get('sku', 'N/A')
            name = u.get('product_name', '')
            status = u.get('status', 'unknown')
            old_price = u.get('old_price')
            new_price = u.get('new_price')
            reason = u.get('reason')

            if status == 'updated':
                if old_price is not None:
                    lines.append(f"✅ {sku} – {name}: {old_price:.0f} → {new_price:.0f}")
                else:
                    lines.append(f"✅ {sku} – {name}: установлена цена {new_price:.0f}")
            elif status == 'pending':
                # Не должно оставаться после обработки, но на всякий случай
                lines.append(f"⏳ {sku} – {name}: ожидание ответа API (не должно быть)")
            elif status == 'error':
                lines.append(f"❌ {sku} – {name}: ошибка – {reason}")
            else:
                lines.append(f"❓ {sku} – {name}: неизвестный статус {status}")

        if errors:
            lines.append("\n❌ Общие ошибки:")
            for err in errors:
                lines.append(f"  - {err}")

        body = "\n".join(lines)
        self.send_message(subject, body)

    # Старый метод (для совместимости)
    def notify_cycle_complete(self, updated_count: int, errors: Optional[List[str]] = None):
        subject = f"Репрайсер – цикл завершён. Обновлено {updated_count} товаров"
        body = f"Обновлено цен: {updated_count}\n"
        if errors:
            body += "\n".join(errors)
        self.send_message(subject, body)

    def notify_critical_event(self, event: str):
        subject = "Репрайсер – критическое событие"
        self.send_message(subject, event)