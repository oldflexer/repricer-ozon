import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging
import csv
import io
from typing import List, Optional, Dict

from config.settings import settings

logger = logging.getLogger(__name__)


class MailNotifier:
    def __init__(self):
        self.host: str = settings.SMTP_HOST
        self.port: int = settings.SMTP_PORT
        self.user: str = settings.SMTP_USER
        self.password: str = settings.SMTP_PASSWORD
        self.sender: str = settings.SENDER_EMAIL or settings.SMTP_USER
        self.recipient: str = settings.RECIPIENT_EMAIL

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

    def send_message_with_attachment(self, subject: str, body: str, filename: str, csv_content: str) -> bool:
        if not self.host or not self.user or not self.password or not self.sender or not self.recipient:
            logger.warning("Не настроены параметры SMTP для отправки email")
            return False

        msg = MIMEMultipart()
        msg['From'] = self.sender
        msg['To'] = self.recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        part = MIMEBase('application', 'octet-stream')
        part.set_payload(csv_content.encode('utf-8-sig'))
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)

        try:
            server = smtplib.SMTP(self.host, self.port, timeout=10)
            server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.sender, [self.recipient], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки email с вложением: {e}")
            return False

    def _generate_csv(self, updates: List[Dict]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['SKU', 'Название', 'Старая цена', 'Новая цена', 'Статус', 'Причина'])
        for u in updates:
            writer.writerow([
                u.get('sku', ''),
                u.get('product_name', ''),
                u.get('old_price', ''),
                u.get('new_price', ''),
                u.get('status', ''),
                u.get('reason', '')
            ])
        return output.getvalue()

    def send_detailed_report(self, updates: List[Dict], errors: List[str], dry_run: bool = False):
        if dry_run:
            subject = "[DRY-RUN] Репрайсер – результаты расчёта (цены не отправлялись)"
        else:
            updated_count = sum(1 for u in updates if u.get('status') == 'updated')
            subject = f"Репрайсер – цикл завершён. Обновлено товаров: {updated_count}"

        lines = []
        if dry_run:
            lines.append("*** ЭТО ТЕСТОВЫЙ ЗАПУСК (DRY-RUN). ЦЕНЫ НЕ ОТПРАВЛЯЛИСЬ. ***\n")

        if len(updates) > settings.NOTIFICATION_MAX_DETAILS:
            lines.append(f"Количество товаров ({len(updates)}) превышает лимит детализации ({settings.NOTIFICATION_MAX_DETAILS}).")
            lines.append("Полные данные прилагаются в CSV-файле.\n")
            csv_data = self._generate_csv(updates)
            self.send_message_with_attachment(subject, "\n".join(lines), "report.csv", csv_data)
            return

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

    # Старый метод оставлен для совместимости (не используется)
    def notify_cycle_complete(self, updated_count: int, errors: Optional[List[str]] = None):
        subject = f"Репрайсер – цикл завершён. Обновлено {updated_count} товаров"
        body = f"Обновлено цен: {updated_count}\n"
        if errors:
            body += "\n".join(errors)
        self.send_message(subject, body)

    def notify_critical_event(self, event: str):
        subject = "Репрайсер – критическое событие"
        self.send_message(subject, event)