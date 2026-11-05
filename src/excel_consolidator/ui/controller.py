"""Interface control layer: validates fields, runs and summarizes without a screen."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .. import runlog
from ..cli import run_config
from ..config import DEFAULT_INPUT, DEFAULT_LOG_FILE, DEFAULT_OUTPUT, RuntimeConfig, apply_overrides, load_config
from ..errors import ConsolidationError
from ..quality import QualityOptions
from ..report import QualitySummary, summarize

DEFAULT_LOG_TAIL_LINES: int = 40
_LOG_TAIL_BYTES: int = 8_192


def split_key(text: str) -> tuple[str, ...]:
    """Convert `"product, date"` into `("product", "date")`, dropping empty entries."""
    return tuple(part.strip() for part in text.split(",") if part.strip())


def default_config() -> RuntimeConfig:
    """Return the configuration used when there is no valid `config.toml`."""
    return RuntimeConfig(DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_LOG_FILE, QualityOptions())


@dataclass(frozen=True)
class FormFields:
    """Raw values typed in the window, without conversion."""

    input_dir: str = ""
    output_path: str = ""
    trim_text: bool = False
    normalize_numbers: bool = False
    dates_iso: bool = False
    remove_duplicates: bool = False
    key: str = ""
    log_file: str = ""

    @classmethod
    def from_config(cls, config: RuntimeConfig) -> "FormFields":
        """Fill the fields from an already resolved configuration."""
        options = config.options
        return cls(
            input_dir=str(config.input_dir),
            output_path=str(config.output_path),
            trim_text=options.trim_text,
            normalize_numbers=options.normalize_numbers,
            dates_iso=options.dates_iso,
            remove_duplicates=options.remove_duplicates,
            key=", ".join(options.key),
            log_file=str(config.log_file),
        )


@dataclass(frozen=True)
class RunOutcome:
    """Result of a run, ready to be displayed."""

    ok: bool
    message: str
    files: int = 0
    rows: int = 0
    output_path: Path | None = None
    summary: QualitySummary | None = None
    report: pd.DataFrame | None = None
    log_tail: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def build_config(fields: FormFields, base: RuntimeConfig | None = None) -> RuntimeConfig:
    """Apply the fields over the base, treating empty paths as errors."""
    base = default_config() if base is None else base
    input_dir = fields.input_dir.strip()
    output_path = fields.output_path.strip()
    if not input_dir:
        raise ConsolidationError("the input folder is required")
    if not output_path:
        raise ConsolidationError("the output file is required")
    log_file = fields.log_file.strip()
    return apply_overrides(
        base,
        input_dir=Path(input_dir).expanduser(),
        output_path=Path(output_path).expanduser(),
        log_file=Path(log_file).expanduser() if log_file else None,
        trim_text=fields.trim_text,
        normalize_numbers=fields.normalize_numbers,
        dates_iso=fields.dates_iso,
        remove_duplicates=fields.remove_duplicates,
        key=split_key(fields.key),
    )


def load_base(path: Path | None = None) -> tuple[RuntimeConfig, str | None]:
    """Load `config.toml`; on failure return the defaults and the message."""
    try:
        return load_config(path), None
    except ConsolidationError as exc:
        return default_config(), str(exc)


def format_summary(files: int, rows: int, output_path: Path, summary: QualitySummary) -> str:
    """Reproduce the four lines the CLI writes to stdout."""
    return "\n".join((
        f"files: {files}",
        f"rows: {rows}",
        f"output: {output_path.resolve()}",
        f"quality: nulls={summary.nulls} duplicates={summary.duplicates} "
        f"removed={summary.removed} changed={summary.changed}",
    ))


def read_log_tail(path: Path, lines: int = DEFAULT_LOG_TAIL_LINES) -> tuple[str, ...]:
    """Read the last lines of the log without loading the whole file."""
    if lines <= 0:
        return ()
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            start = max(0, size - _LOG_TAIL_BYTES)
            stream.seek(start)
            data = stream.read()
    except OSError:
        return ()
    text = data.decode("utf-8", errors="replace")
    tail = text.splitlines()
    if start > 0 and tail:
        tail = tail[1:]
    return tuple(tail[-lines:])


def run_from_fields(
    fields: FormFields,
    base: RuntimeConfig | None = None,
    log_tail_lines: int = DEFAULT_LOG_TAIL_LINES,
) -> RunOutcome:
    """Run the consolidation from the window fields without printing anything."""
    config: RuntimeConfig | None = None
    logger = None
    try:
        config = build_config(fields, base)
        logger = runlog.setup_logging(config.log_file)
        options = config.options
        flags = ",".join(name for name, enabled in (
            ("trim_text", options.trim_text), ("normalize_numbers", options.normalize_numbers),
            ("dates_iso", options.dates_iso), ("remove_duplicates", options.remove_duplicates),
        ) if enabled) or "none"
        logger.info("start input=%s output=%s flags=%s key=%s", config.input_dir.resolve(),
                    config.output_path.resolve(), flags, ",".join(options.key) or "-")
        result = run_config(config)
        for warning in result.warnings:
            logger.warning("%s", warning)
        rows_read = result.report.loc[result.report["metric"] == "rows_read", "value"].sum()
        logger.info("read files=%s rows_read=%s", len(result.files), rows_read)
        summary = summarize(result.report)
        logger.info("written rows=%s nulls=%s duplicates=%s removed=%s changed=%s output=%s",
                    result.rows, summary.nulls, summary.duplicates, summary.removed,
                    summary.changed, config.output_path.resolve())
        return RunOutcome(
            ok=True,
            message=format_summary(len(result.files), result.rows, config.output_path, summary),
            files=len(result.files),
            rows=result.rows,
            output_path=config.output_path,
            summary=summary,
            report=result.report,
            log_tail=read_log_tail(config.log_file, log_tail_lines),
            warnings=result.warnings,
        )
    except ConsolidationError as exc:
        if logger is not None:
            logger.error("error=%s", exc)
        log_tail = read_log_tail(config.log_file, log_tail_lines) if config is not None else ()
        return RunOutcome(ok=False, message=f"error: {exc}", log_tail=log_tail)
    finally:
        if logger is not None:
            runlog.close_logging(logger)
