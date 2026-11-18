"""Command line interface for the consolidation."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import runlog
from .config import (
    DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_OUTPUT_FORMAT, OUTPUT_FORMATS, RuntimeConfig,
    apply_overrides, load_config, output_paths,
)
from .consolidator import ConsolidationResult, consolidate
from .errors import ConsolidationError
from .quality import QualityOptions
from .reader import check_write_destination
from .reader_options import INPUT_FORMATS, ReaderOptions
from .report import summarize
from .writer import write_outputs


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(description="Consolidate .xlsx, .xls and .csv inputs vertically.")
    parser.add_argument("--input", type=Path, default=None, metavar="DIR")
    parser.add_argument("--output", type=Path, default=None, metavar="PATH")
    parser.add_argument("--output-format", choices=OUTPUT_FORMATS,
                        help="select the export format (default: xlsx)")
    parser.add_argument("--json", action="store_true", help="print a one-line JSON summary")
    parser.add_argument("--trim-text", action="store_true", default=None)
    parser.add_argument("--normalize-numbers", action="store_true", default=None)
    parser.add_argument("--dates-iso", action="store_true", default=None)
    parser.add_argument("--key", metavar="COL1,COL2")
    parser.add_argument("--remove-duplicates", action="store_true", default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--log-file", type=Path, default=None)
    parser.add_argument("--formats", nargs="+", choices=INPUT_FORMATS,
                        help="restrict the input formats (default: all)")
    parser.add_argument("--csv-encoding", metavar="NAME",
                        help="set the CSV encoding explicitly (default: automatic)")
    parser.add_argument("--csv-delimiter", metavar="CHAR",
                        help="set a single-character CSV delimiter (default: automatic)")
    return parser


def run(
    input_dir: Path,
    output_path: Path,
    options: QualityOptions | None = None,
    reader_options: ReaderOptions = ReaderOptions(),
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> ConsolidationResult:
    """Consolidate validated inputs and publish the result atomically."""
    outputs = output_paths(output_path, output_format)
    result = consolidate(input_dir, options, reader_options)
    for path in outputs.values():
        check_write_destination(path, (sheet.path for sheet in result.files))
    write_outputs(result.frame, result.report, outputs)
    return result


def run_config(config: RuntimeConfig) -> ConsolidationResult:
    """Run a resolved configuration without logging or console output."""
    return run(config.input_dir, config.output_path, config.options, config.reader_options,
               output_format=config.output_format)


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
            formats=tuple(args.formats) if args.formats is not None else None,
            csv_encoding=args.csv_encoding, csv_delimiter=args.csv_delimiter,
            output_format=args.output_format,
        )
        logger = runlog.setup_run_logging(config)
        if args.key is not None:
            key = tuple(part.strip() for part in args.key.split(",") if part.strip())
            if not key:
                raise ConsolidationError("empty key: provide at least one column")
            config = apply_overrides(config, key=key)
        runlog.log_start(logger, config)
        result = run_config(config)
        for warning in result.warnings:
            logger.warning("%s", warning)
        rows_read = result.report.loc[result.report["metric"] == "rows_read", "value"].sum()
        logger.info("read files=%s rows_read=%s", len(result.files), rows_read)
        summary = summarize(result.report)
        runlog.log_written(logger, config, result, summary)
        output = config.output_path.resolve()
        if args.json:
            print(json.dumps({
                "files": len(result.files),
                "rows": result.rows,
                "output": str(output),
                "outputs": {kind: str(path.resolve()) for kind, path in config.outputs.items()},
                "quality": asdict(summary),
                "warnings": list(result.warnings),
            }))
        else:
            print(f"files: {len(result.files)}")
            print(f"rows: {result.rows}")
            print(f"output: {output}")
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
