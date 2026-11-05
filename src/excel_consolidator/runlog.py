"""File logging, explicitly configured by the CLI."""
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from .errors import ConsolidationError

LOGGER_NAME: str = "excel_consolidator"
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES: int = 1_000_000
DEFAULT_BACKUP_COUNT: int = 1


def close_logging(logger: logging.Logger) -> None:
    """Remove and close every handler left by the previous run."""
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def setup_logging(
    log_file: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    """Open a rotating log without configuring console output."""
    logger = logging.getLogger(LOGGER_NAME)
    close_logging(logger)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
    except OSError as exc:
        raise ConsolidationError(f"error opening log '{log_file}': {exc}") from exc
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(handler)
    return logger
