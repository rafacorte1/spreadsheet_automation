"""Quality report over the data before deduplication."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from .quality import DATES_ISO, NORMALIZE_NUMBERS, TRIM_TEXT, ColumnStats, DuplicateReport, QualityOptions
from .reader import ORIGIN_COLUMN, SheetData

REPORT_SHEET: str = "report"
REPORT_COLUMNS: tuple[str, ...] = ("section", "file", "column", "metric", "value")


@dataclass(frozen=True)
class QualitySummary:
    nulls: int
    duplicates: int
    removed: int
    changed: int


def count_nulls(sheet: SheetData) -> dict[str, int]:
    """Count None and empty text, ignoring the origin column."""
    return {
        column: sum(row[index] is None or (isinstance(row[index], str) and not row[index].strip())
                    for row in sheet.rows)
        for index, column in enumerate(sheet.columns) if column != ORIGIN_COLUMN
    }


def build_report(
    sheets: Sequence[SheetData],
    stats: Mapping[str, Mapping[str, ColumnStats]],
    duplicates: DuplicateReport,
    options: QualityOptions,
) -> pd.DataFrame:
    """Build the sections in a stable order, including zeroed counters."""
    ordered = sorted(sheets, key=lambda sheet: sheet.path.name)
    rows: list[tuple[object, ...]] = [
        ("summary", sheet.path.name, "", "rows_read", len(sheet.rows)) for sheet in ordered
    ]
    for sheet in ordered:
        rows.extend(("nulls", sheet.path.name, column, "nulls", count)
                    for column, count in count_nulls(sheet).items())
    for sheet in ordered:
        for column in sheet.columns:
            if column == ORIGIN_COLUMN:
                continue
            column_stats = stats.get(sheet.path.name, {}).get(column, ColumnStats())
            for enabled, rule in ((options.trim_text, TRIM_TEXT),
                                  (options.normalize_numbers, NORMALIZE_NUMBERS),
                                  (options.dates_iso, DATES_ISO)):
                if enabled:
                    rows.append(("standardization", sheet.path.name, column, f"changed_{rule}",
                                 column_stats.changed_by_rule.get(rule, 0)))
                    rows.append(("standardization", sheet.path.name, column, f"failed_{rule}",
                                 column_stats.failed.get(rule, 0)))
    rows.extend(("duplicates", "", "", metric, value) for metric, value in (
        ("mode", duplicates.mode), ("duplicate_rows", duplicates.total),
        ("rows_removed", duplicates.removed),
    ))
    return pd.DataFrame(rows, columns=REPORT_COLUMNS)


def summarize(report: pd.DataFrame) -> QualitySummary:
    """Extract the four counters printed by the CLI."""
    duplicates = report.loc[report["section"] == "duplicates"].set_index("metric")["value"]
    changed = (report["section"] == "standardization") & report["metric"].str.startswith("changed_")
    return QualitySummary(
        int(report.loc[report["section"] == "nulls", "value"].sum()),
        int(duplicates["duplicate_rows"]), int(duplicates["rows_removed"]),
        int(report.loc[changed, "value"].sum()),
    )
