# infrastructure/logger.py
import structlog
import logging
import sys
from pathlib import Path

def setup_logging():
    """Настройка структурированного логирования."""
    # Настройка стандартного logging для библиотек (requests, httpx и т.д.)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            # logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path(__file__).parent.parent / 'repricer.log', mode='w', encoding='utf-8')
        ]
    )

    # Настройка structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,           # Добавляет уровень логирования
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),  # Добавляет временную метку
            structlog.processors.StackInfoRenderer(),    # Добавляет информацию о стеке при ошибках
            structlog.processors.format_exc_info,        # Форматирует исключения
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()          # Вывод в JSON
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Заменяем стандартный логгер на structlog
    return structlog.get_logger()

logger = setup_logging()