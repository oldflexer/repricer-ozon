import requests
import logging
from typing import List, Optional
from config.settings import MAX_BOT_TOKEN, MAX_API_URL

logger = logging.getLogger(__name__)


class MaxNotifier:
    """Отправка уведомлений через MAX Bot API"""

    def __init__(self, chat_id: Optional[str] = None):
        """
        chat_id: идентификатор чата с ботом (можно получить после первого сообщения)
        Если не указан, сообщения не отправляются.
        """
        self.token = MAX_BOT_TOKEN
        self.chat_id = chat_id
        self.base_url = MAX_API_URL

    def send_message(self, text: str) -> bool:
        """Отправляет текстовое сообщение в чат с ботом"""
        if not self.token or not self.chat_id:
            logger.warning("Не настроены токен MAX или chat_id")
            return False

        url = f"{self.base_url}/messages.send"
        payload = {
            'token': self.token,
            'chat_id': self.chat_id,
            'text': text
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки в MAX: {e}")
            return False

    def notify_cycle_complete(self, updated_count: int, errors: Optional[List[str]] = None):
        """Уведомление о завершении цикла репрайсинга"""
        text = f"✅ Репрайсинг завершён.\nОбновлено товаров: {updated_count}"
        if errors:
            text += f"\n⚠️ Ошибки:\n" + "\n".join(errors[:5])  # первые 5 ошибок
        self.send_message(text)

    def notify_critical_event(self, event: str):
        """Уведомление о критическом событии (резкое падение цены и т.п.)"""
        text = f"🚨 Внимание!\n{event}"
        self.send_message(text)