"""Command line interface for the consolidation."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .config import DEFAULT_INPUT, DEFAULT_OUTPUT, RuntimeConfig, load_config, apply_overrides
from . import runlog
from .consolidator import ConsolidationResult, consolidate
from .errors import ConsolidationError
from .writer import write_atomic
from .quality import QualityOptions
from .report import summarize


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(description="Consolidate .xlsx spreadsheets vertically.")
    parser.add_argument("--input", type=Path, default=None, metavar="DIR")
    parser.add_argument("--output", type=Path, default=None, metavar="PATH")
    parser.add_argument("--trim-text", action="store_true", default=None)
    parser.add_argument("--normalize-numbers", action="store_true", default=None)
    parser.add_argument("--dates-iso", action="store_true", default=None)
    parser.add_argument("--key", metavar="COL1,COL2")
    parser.add_argument("--remove-duplicates", action="store_true", default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--log-file", type=Path, default=None)
    return parser


def run(input_dir: Path, output_path: Path, options: QualityOptions | None = None) -> ConsolidationResult:
    """Consolidate validated inputs and publish the result atomically."""
    result = consolidate(input_dir, options)
    write_atomic(result.frame, output_path, result.report)
    return result


def run_config(config: RuntimeConfig) -> ConsolidationResult:
    """Run a resolved configuration without logging or console output."""
    return run(config.input_dir, config.output_path, config.options)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit code."""
    args = build_parser().parse_args(argv)
    logger = None
    try:
        config = load_config(args.config)
        config = apply_overrides(
            config, input_dir=args.input, output_path=args.output, log_file=args.log_file,
            trim_text=args.trim_text, normalize_numbers=args.normalize_numbers,
            dates_iso=args.dates_iso, remove_duplicates=args.remove_duplicates,
        )
        logger = runlog.setup_logging(config.log_file, max_bytes=runlog.DEFAULT_MAX_BYTES,
                                      backup_count=runlog.DEFAULT_BACKUP_COUNT)
        if args.key is not None:
            key = tuple(part.strip() for part in args.key.split(",") if part.strip())
            if not key:
                raise ConsolidationError("empty key: provide at least one column")
            config = apply_overrides(config, key=key)
        options = config.options
        flags = ",".join(name for name, enabled in (
            ("trim_text", options.trim_text), ("normalize_numbers", options.normalize_numbers),
            ("dates_iso", options.dates_iso), ("remove_duplicates", options.remove_duplicates),
        ) if enabled) or "none"
        logger.info("start input=%s output=%s flags=%s key=%s",
                    config.input_dir.resolve(), config.output_path.resolve(), flags,
                    ",".join(options.key) or "-")
        result = run_config(config)
        for warning in result.warnings:
            logger.warning("%s", warning)
        rows_read = result.report.loc[result.report["metric"] == "rows_read", "value"].sum()
        logger.info("read files=%s rows_read=%s", len(result.files), rows_read)
        summary = summarize(result.report)
        logger.info("written rows=%s nulls=%s duplicates=%s removed=%s changed=%s output=%s",
                    result.rows, summary.nulls, summary.duplicates, summary.removed,
                    summary.changed, config.output_path.resolve())
        print(f"files: {len(result.files)}")
        print(f"rows: {result.rows}")
        print(f"output: {config.output_path.resolve()}")
        print(f"quality: nulls={summary.nulls} duplicates={summary.duplicates} removed={summary.removed} changed={summary.changed}")
        return 0
    except ConsolidationError as exc:
        if logger is not None:
            logger.error("error=%s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if logger is not None:
            runlog.close_logging(logger)
