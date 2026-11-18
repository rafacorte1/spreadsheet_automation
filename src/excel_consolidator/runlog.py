"""File logging for CLI and GUI runs."""
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from .config import RuntimeConfig
from .errors import ConsolidationError
from .reader import check_write_destination, discover_input_files

LOGGER_NAME: str = "excel_consolidator"
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES: int = 1_000_000
DEFAULT_BACKUP_COUNT: int = 1


def setup_run_logging(config: RuntimeConfig) -> logging.Logger:
    """Open the run log after checking that it cannot clobber existing data."""
    if config.log_file.exists():
        inputs = discover_input_files(config.input_dir, config.reader_options.formats)
        check_write_destination(config.log_file, [config.output_path, *inputs])
    return setup_logging(config.log_file, max_bytes=DEFAULT_MAX_BYTES, backup_count=DEFAULT_BACKUP_COUNT)


def log_start(logger: logging.Logger, config: RuntimeConfig) -> None:
    """Record the effective settings in the run's first log entry."""
    options = config.options
    reader = config.reader_options
    flags = ",".join(name for name, enabled in (
        ("trim_text", options.trim_text), ("normalize_numbers", options.normalize_numbers),
        ("dates_iso", options.dates_iso), ("remove_duplicates", options.remove_duplicates),
    ) if enabled) or "none"
    logger.info(
        "start input=%s output=%s flags=%s key=%s formats=%s csv_encoding=%s csv_delimiter=%s",
        config.input_dir.resolve(), config.output_path.resolve(), flags,
        ",".join(options.key) or "-", ",".join(reader.formats),
        reader.csv_encoding if reader.csv_encoding is not None else "auto",
        repr(reader.csv_delimiter) if reader.csv_delimiter is not None else "auto",
    )


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
