"""Optional standardization and duplicate detection without external effects."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import math
import re

import pandas as pd

from .reader import ORIGIN_COLUMN, SheetData

TRIM_TEXT: str = "trim_text"
NORMALIZE_NUMBERS: str = "normalize_numbers"
DATES_ISO: str = "dates_iso"

_NUMBER_PATTERN = re.compile(r"-?(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)(?:,[0-9]+)?")
_DATE_FORMATS: tuple[tuple[str, str, bool], ...] = (
    (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "%d/%m/%Y", False),
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d", False),
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", "%Y-%m-%d %H:%M:%S", True),
    (r"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}", "%d/%m/%Y %H:%M:%S", True),
)


@dataclass(frozen=True)
class QualityOptions:
    """Explicit data quality rules."""

    trim_text: bool = False
    normalize_numbers: bool = False
    dates_iso: bool = False
    key: tuple[str, ...] = ()
    remove_duplicates: bool = False

    @property
    def any_standardization(self) -> bool:
        """Report whether any standardization rule is active."""
        return self.trim_text or self.normalize_numbers or self.dates_iso


@dataclass(frozen=True)
class ColumnStats:
    """Accumulated changes and failures per rule in a column."""

    changed: int = 0
    failed: dict[str, int] = field(default_factory=dict)
    changed_by_rule: dict[str, int] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class StandardizationResult:
    """New sheet and per-column counters."""

    sheet: SheetData
    stats: dict[str, ColumnStats]


@dataclass(frozen=True)
class DuplicateReport:
    """Duplicate counts for the requested policy."""

    total: int
    removed: int
    mode: str


def _normalize_number(value: str) -> int | float:
    """Convert only numbers written in the accepted pt-BR formats."""
    stripped = value.strip()
    if _NUMBER_PATTERN.fullmatch(stripped) is None:
        raise ValueError("unsupported number format")
    normalized = stripped.replace(".", "").replace(",", ".")
    if "," not in stripped:
        return int(normalized)
    result = float(normalized)
    if not math.isfinite(result):
        raise ValueError("number outside the finite range")
    return result


def _parse_date(value: str) -> date | datetime:
    """Convert dates only in the explicit formats, with a four-digit year."""
    for pattern, date_format, has_time in _DATE_FORMATS:
        if re.fullmatch(pattern, value) is not None:
            parsed = datetime.strptime(value, date_format)
            return parsed if has_time else parsed.date()
    raise ValueError("unsupported date format")


def standardize(sheet: SheetData, options: QualityOptions) -> StandardizationResult:
    """Apply rules in order and count failures only in cells without conversion."""
    changes = {column: 0 for column in sheet.columns}
    failures: dict[str, dict[str, int]] = {column: {} for column in sheet.columns}
    rule_changes: dict[str, dict[str, int]] = {column: {} for column in sheet.columns}
    rows: list[tuple[object, ...]] = []
    for row in sheet.rows:
        values: list[object] = []
        for column, original in zip(sheet.columns, row, strict=True):
            value = original
            cell_changes = 0
            converted = False
            cell_failures: list[str] = []
            if options.trim_text and isinstance(value, str):
                trimmed = value.strip()
                if trimmed != value:
                    rule_changes[column][TRIM_TEXT] = rule_changes[column].get(TRIM_TEXT, 0) + 1
                cell_changes += int(trimmed != value)
                value = trimmed
            for enabled, rule, converter in (
                (options.normalize_numbers, NORMALIZE_NUMBERS, _normalize_number),
                (options.dates_iso, DATES_ISO, _parse_date),
            ):
                if enabled and isinstance(value, str) and value.strip():
                    try:
                        value = converter(value)
                    except ValueError:
                        cell_failures.append(rule)
                    else:
                        converted = True
                        cell_changes += 1
                        rule_changes[column][rule] = rule_changes[column].get(rule, 0) + 1
            changes[column] += cell_changes
            if not converted:
                for rule in cell_failures:
                    failures[column][rule] = failures[column].get(rule, 0) + 1
            values.append(value)
        rows.append(tuple(values))
    result_sheet = SheetData(sheet.path, sheet.columns, tuple(rows))
    stats = {
        column: ColumnStats(changes[column], failures[column], rule_changes[column])
        for column in sheet.columns
    }
    return StandardizationResult(result_sheet, stats)


def find_duplicates(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    """Mark duplicate occurrences after the first one."""
    return frame.duplicated(subset=list(columns), keep="first")


def build_duplicate_report(frame: pd.DataFrame, options: QualityOptions) -> DuplicateReport:
    """Count duplicates by key or by whole row without the origin column."""
    columns = options.key or tuple(column for column in frame.columns if column != ORIGIN_COLUMN)
    total = int(find_duplicates(frame, columns).sum())
    mode = "key:" + ",".join(options.key) if options.key else "identical_rows"
    return DuplicateReport(total, total if options.remove_duplicates else 0, mode)
