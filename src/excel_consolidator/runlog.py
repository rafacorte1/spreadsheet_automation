"""File logging for CLI and GUI runs."""
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from .config import RuntimeConfig
from .consolidator import ConsolidationResult
from .errors import ConsolidationError
from .reader import check_write_destination, discover_input_files
from .report import QualitySummary

LOGGER_NAME: str = "excel_consolidator"
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES: int = 1_000_000
DEFAULT_BACKUP_COUNT: int = 1


def setup_run_logging(config: RuntimeConfig) -> logging.Logger:
    """Open the run log after checking that it cannot clobber existing data."""
    outputs = tuple(config.outputs.values())
    inputs = discover_input_files(config.input_dir, config.reader_options.formats)
    for path in (config.log_file, Path(f"{config.log_file.absolute()}.1")):
        resolved = path.resolve()
        for output in outputs:
            if resolved == output.resolve():
                raise ConsolidationError(f"{path}: write destination conflicts with {output}")
        check_write_destination(path, [*outputs, *inputs])
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
        "start input=%s output=%s flags=%s key=%s formats=%s csv_encoding=%s csv_delimiter=%s "
        "output_format=%s",
        config.input_dir.resolve(), config.output_path.resolve(), flags,
        ",".join(options.key) or "-", ",".join(reader.formats),
        reader.csv_encoding if reader.csv_encoding is not None else "auto",
        repr(reader.csv_delimiter) if reader.csv_delimiter is not None else "auto",
        config.output_format,
    )


def log_written(
    logger: logging.Logger, config: RuntimeConfig, result: ConsolidationResult, summary: QualitySummary,
) -> None:
    """Record the counters and all paths published by a successful run."""
    paths = " ".join(f"{kind}={path.resolve()}" for kind, path in config.outputs.items())
    logger.info("written rows=%s nulls=%s duplicates=%s removed=%s changed=%s output=%s %s",
                result.rows, summary.nulls, summary.duplicates, summary.removed, summary.changed,
                config.output_path.resolve(), paths)


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
