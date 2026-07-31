import structlog
import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import TimedRotatingFileHandler

_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

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
        structlog.processors.KeyValueRenderer(key_order=['event', 'level', 'timestamp'])
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Глобальный логгер (без обработчиков – они будут добавлены через setup_logging)
logger = structlog.get_logger()


def setup_logging(log_file: Optional[str] = None, mode: str = 'a', console: bool = True):
    """
    Настраивает логирование репрайсера.
    :param log_file: имя файла (без пути). Если None, используется 'repricer.log'
    :param mode: режим открытия файла ('a' - дописывать, 'w' - перезаписывать)
    :param console: добавлять ли консольный обработчик (для отладки)
    """
    root_logger = logging.getLogger()
    # Удаляем все существующие обработчики, чтобы избежать дублирования
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    if log_file is None:
        log_file = "repricer.log"
    file_path = _LOG_DIR / log_file

    if mode == 'a':
        file_handler = TimedRotatingFileHandler(
            file_path,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
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


def setup_parser_logging(log_file: Optional[str] = None, mode: str = 'a') -> logging.Logger:
    if log_file is None:
        log_file = "parser.log"
    file_path = _LOG_DIR / log_file

    if mode == 'a':
        file_handler = TimedRotatingFileHandler(
            file_path,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
    else:
        file_handler = logging.FileHandler(file_path, mode=mode, encoding="utf-8")

    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    file_handler.setLevel(logging.INFO)

    for name in _PARSER_LOGGERS:
        sub = logging.getLogger(name)
        sub.setLevel(logging.INFO)
        sub.handlers.clear()
        sub.addHandler(file_handler)
        sub.propagate = False

    log = logging.getLogger("update_competitor_prices")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    log.addHandler(file_handler)
    log.propagate = False
    return log