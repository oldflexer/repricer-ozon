import structlog
import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Модули, чьи логи нужно изолировать в parser.log
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


def setup_logging():
    """Настраивает логирование репрайсера (repricer.log) с ротацией."""
    # Очищаем существующие хендлеры, чтобы избежать дублирования
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    file_handler = TimedRotatingFileHandler(
        _LOG_DIR / "repricer.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    console_handler.setLevel(logging.INFO)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.KeyValueRenderer(key_order=['event', 'level', 'timestamp'])
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()


def setup_parser_logging() -> logging.Logger:
    """
    Настраивает изолированное логирование парсера (parser.log) с ротацией.
    """
    file_handler = TimedRotatingFileHandler(
        _LOG_DIR / "parser.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    console_handler.setLevel(logging.INFO)

    for name in _PARSER_LOGGERS:
        sub = logging.getLogger(name)
        sub.setLevel(logging.INFO)
        sub.handlers.clear()
        sub.addHandler(file_handler)
        sub.addHandler(console_handler)
        sub.propagate = False

    log = logging.getLogger("update_competitor_prices")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    log.addHandler(file_handler)
    log.addHandler(console_handler)
    log.propagate = False
    return log


logger = setup_logging()