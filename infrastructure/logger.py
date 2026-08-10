"""
Настройка логирования для приложения.

Использует structlog для структурированных логов и стандартный logging
с ротацией по дням (TimedRotatingFileHandler).
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog

_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Логгеры, для которых отключаем propagation в парсере
_PARSER_LOGGERS = [
    "update_competitor_prices",
    "infrastructure.ozon_parser",
    "undetected_chromedriver",
    "undetected_chromedriver.patcher",
    "uc",
    "WDM",
    "selenium",
    "urllib3",
    "webdriver_manager",
]

# Настройка structlog – выполняется один раз при импорте
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.KeyValueRenderer(key_order=["event", "level", "timestamp"]),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Глобальный логгер (без обработчиков – они добавляются через setup_logging)
logger = structlog.get_logger()


def setup_logging(
    log_file: str | None = None, mode: str = "a", console: bool = True
) -> structlog.BoundLogger:
    """
    Настраивает логирование репрайсера.

    Args:
        log_file: Имя файла лога (без пути). Если None – "repricer.log".
        mode: Режим открытия файла: 'a' – дописывать, 'w' – перезаписывать.
        console: Добавлять ли консольный обработчик (для отладки).

    Returns:
        Глобальный объект логгера (structlog.BoundLogger).
    """
    root_logger = logging.getLogger()

    # Удаляем все существующие обработчики, чтобы избежать дублирования
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if log_file is None:
        log_file = "repricer.log"
    file_path = _LOG_DIR / log_file

    file_handler: TimedRotatingFileHandler | logging.FileHandler
    if mode == "a":
        file_handler = TimedRotatingFileHandler(
            file_path,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
    else:
        file_handler = logging.FileHandler(file_path, mode=mode, encoding="utf-8")

    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)

    root_logger.setLevel(logging.INFO)
    return logger


def setup_parser_logging(log_file: str | None = None, mode: str = "a") -> logging.Logger:
    """
    Настраивает логирование для парсера конкурентов.

    Изолирует логгеры selenium, webdriver_manager, undetected-chromedriver и др.,
    чтобы они писали только в файл парсера.

    Args:
        log_file: Имя файла лога (без пути). Если None – "parser.log".
        mode: Режим открытия файла: 'a' – дописывать, 'w' – перезаписывать.

    Returns:
        Логгер с именем "update_competitor_prices".
    """
    if log_file is None:
        log_file = "parser.log"
    file_path = _LOG_DIR / log_file

    file_handler: TimedRotatingFileHandler | logging.FileHandler
    if mode == "a":
        file_handler = TimedRotatingFileHandler(
            file_path,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )
    else:
        file_handler = logging.FileHandler(file_path, mode=mode, encoding="utf-8")

    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    # Настраиваем дочерние логгеры – только файл, без propagation
    for name in _PARSER_LOGGERS:
        sub = logging.getLogger(name)
        sub.setLevel(logging.INFO)
        sub.handlers.clear()
        sub.addHandler(file_handler)
        sub.propagate = False

    # Основной логгер парсера
    log = logging.getLogger("update_competitor_prices")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    log.addHandler(file_handler)
    log.propagate = False

    return log
