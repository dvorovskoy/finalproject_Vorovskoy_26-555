"""Настройка логирования ValutaTrade Hub."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "actions.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Настраивает корневой логгер проекта и возвращает его."""
    global _configured
    logger = logging.getLogger("valutatrade")
    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    LOG_DIR.mkdir(exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    _configured = True
    return logger


def get_logger() -> logging.Logger:
    """Возвращает логгер проекта (с автонастройкой при первом вызове)."""
    return setup_logging()