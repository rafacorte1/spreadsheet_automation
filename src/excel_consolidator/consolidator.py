"""Vertical consolidation of the raw input values."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from .quality import QualityOptions, build_duplicate_report, find_duplicates, standardize
from .report import build_report
from .reader import (
    ORIGIN_COLUMN, ConsolidationError, SheetData, discover_input_files,
    read_sheet, validate_headers,
)


@dataclass(frozen=True)
class ConsolidationResult:
    """Validated inputs and their consolidated content."""

    files: tuple[SheetData, ...]
    frame: pd.DataFrame
    report: pd.DataFrame
    options: QualityOptions
    warnings: tuple[str, ...] = ()

    @property
    def rows(self) -> int:
        """Return the total number of consolidated rows."""
        return len(self.frame)


def consolidate(input_dir: Path, options: QualityOptions | None = None) -> ConsolidationResult:
    """Validate every input and concatenate preserving values and order."""
    options = options if options is not None else QualityOptions()
    paths = discover_input_files(input_dir)
    if not paths:
        raise ConsolidationError(f"no .xlsx files in {input_dir}")
    files = tuple(read_sheet(path) for path in paths)
    stats = {}
    if options.any_standardization:
        results = tuple(standardize(sheet, options) for sheet in files)
        files = tuple(result.sheet for result in results)
        stats = {result.sheet.path.name: result.stats for result in results}
    reference = files[0]
    unknown = [column for column in options.key if column not in reference.columns]
    warnings: list[str] = []
    if unknown and options.remove_duplicates:
        raise ConsolidationError(f"key {options.key}: unknown columns {unknown} in {reference.path}")
    if unknown:
        # The key only drives removal: without removal it is ignored and the report
        # falls back to identical rows, with an explicit warning instead of an error.
        warnings.append(
            f"key {options.key} ignored: unknown columns {unknown} in {reference.path}; "
            "duplicates counted with mode identical_rows"
        )
        options = replace(options, key=())
    frames: list[pd.DataFrame] = []
    for sheet in files:
        if sheet is not reference:
            validate_headers(reference, sheet)
        # object avoids numeric inference and the conversion of None into NaN.
        frame = pd.DataFrame(sheet.rows, columns=sheet.columns, dtype=object)
        frame = frame.loc[:, list(reference.columns)].copy()
        frame[ORIGIN_COLUMN] = sheet.path.name
        frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    duplicates = build_duplicate_report(frame, options)
    report = build_report(files, stats, duplicates, options)
    if options.remove_duplicates:
        frame = frame.loc[~find_duplicates(frame, options.key or reference.columns)].reset_index(drop=True)
    return ConsolidationResult(files, frame, report, options, tuple(warnings))
