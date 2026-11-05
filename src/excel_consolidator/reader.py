"""Input discovery and reading without modifying the files."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from .errors import ConsolidationError

ORIGIN_COLUMN: str = "source_file"
HEADER_REJECTED_SUFFIX: str = ".xlsx"


@dataclass(frozen=True)
class SheetData:
    """Raw content of the first sheet of a file."""

    path: Path
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


def discover_input_files(input_dir: Path) -> list[Path]:
    """List inputs directly in the directory, sorted by name."""
    if not input_dir.exists():
        return []
    return sorted(
        (path for path in input_dir.glob("*.xlsx")
         if path.is_file() and not path.name.startswith("~$")),
        key=lambda path: path.name,
    )


def _is_empty(value: object) -> bool:
    return value is None or value == ""


def read_sheet(path: Path) -> SheetData:
    """Read the first sheet and validate headers and record width."""
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.worksheets[0]
            # No padding from the sheet dimension: it may include trailing data.
            lines = sheet.iter_rows(values_only=True)
            header = next((row for row in lines if any(
                not _is_empty(value) for value in row
            )), None)
            if header is None:
                raise ConsolidationError(f"{path}: missing header")
            # openpyxl pads every row up to the widest column of the sheet.
            width = len(header)
            while width and header[width - 1] is None:
                width -= 1
            header = header[:width]
            if any(value is None or not str(value).strip() for value in header):
                raise ConsolidationError(f"{path}: blank header")
            columns = tuple(str(value) for value in header)
            if len(set(columns)) != len(columns):
                raise ConsolidationError(f"{path}: duplicate headers")
            if ORIGIN_COLUMN in columns:
                raise ConsolidationError(f"{path}: reserved column {ORIGIN_COLUMN}")

            rows: list[tuple[object, ...]] = []
            for row in lines:
                if any(not _is_empty(value) for value in row[width:]):
                    raise ConsolidationError(
                        f"{path}: value beyond the last header column"
                    )
                rows.append(tuple(row[:width]) + (None,) * max(0, width - len(row)))
            while rows and all(_is_empty(value) for value in rows[-1]):
                rows.pop()
            if not rows:
                raise ConsolidationError(f"{path}: no data rows")
            return SheetData(path, columns, tuple(rows))
        finally:
            workbook.close()
    except ConsolidationError:
        raise
    except Exception as exc:
        raise ConsolidationError(f"could not read {path}: {exc}") from exc


def validate_headers(reference: SheetData, candidate: SheetData) -> None:
    """Compare the names literally, regardless of order."""
    missing = sorted(set(reference.columns) - set(candidate.columns))
    extra = sorted(set(candidate.columns) - set(reference.columns))
    if missing or extra:
        raise ConsolidationError(
            f"{candidate.path}: missing columns: {missing}; extra columns: {extra}"
        )
