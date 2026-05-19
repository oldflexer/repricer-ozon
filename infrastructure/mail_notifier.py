import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import List, Optional

from config.settings import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    SENDER_EMAIL, RECIPIENT_EMAIL
)

logger = logging.getLogger(__name__)


class MailNotifier:
    """Отправка уведомлений по email."""

    def __init__(self):
        # Гарантируем строки: None заменяем на ''
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

    def notify_cycle_complete(self, updated_count: int, errors: Optional[List[str]] = None):
        subject = f"Репрайсер – цикл завершён. Обновлено {updated_count} товаров"
        body = f"Обновлено цен: {updated_count}\n"
        if errors:
            body += "\n".join(errors)
        self.send_message(subject, body)

    def notify_critical_event(self, event: str):
        subject = "Репрайсер – критическое событие"
        self.send_message(subject, event)