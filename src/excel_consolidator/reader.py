"""Input discovery and reading without modifying the files."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from openpyxl import load_workbook

from . import csv_reader, xls_reader
from .errors import ConsolidationError
from .reader_options import INPUT_FORMATS, ReaderOptions

ORIGIN_COLUMN: str = "source_file"
HEADER_REJECTED_SUFFIX: str = ".xlsx"


@dataclass(frozen=True)
class SheetData:
    """Validated input values and any warnings from reading the file."""

    path: Path
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    warnings: tuple[str, ...] = ()


def discover_input_files(input_dir: Path, formats: Iterable[str] = INPUT_FORMATS) -> list[Path]:
    """List selected input formats directly in the directory, sorted by name."""
    suffixes = {f".{item}" for item in formats}
    return sorted(
        (path for path in input_dir.glob("*")
         if path.suffix.lower() in suffixes and not path.name.startswith("~$") and path.is_file()),
        key=lambda path: path.name,
    )


def check_write_destination(destination: Path, protected: Iterable[Path]) -> None:
    """Reject an existing write target that refers to a file being preserved."""
    if not destination.exists():
        return
    for path in protected:
        try:
            same_file = destination.samefile(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ConsolidationError(f"could not check write destination {destination}: {exc}") from exc
        if same_file:
            raise ConsolidationError(f"{destination}: write destination conflicts with {path}")


def _is_empty(value: object) -> bool:
    return value is None or value == ""


def _validate_rows(
    path: Path,
    records: Iterable[tuple[object, ...]],
    *,
    padded_header: bool,
    warnings: tuple[str, ...] = (),
) -> SheetData:
    lines = iter(records)
    header = next((row for row in lines if any(not _is_empty(value) for value in row)), None)
    if header is None:
        raise ConsolidationError(f"{path}: missing header")
    width = len(header)
    if padded_header:
        # Excel readers can supply trailing cells for the sheet layout.
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
            raise ConsolidationError(f"{path}: value beyond the last header column")
        rows.append(row[:width] + (None,) * max(0, width - len(row)))
    while rows and all(_is_empty(value) for value in rows[-1]):
        rows.pop()
    if not rows:
        raise ConsolidationError(f"{path}: no data rows")
    return SheetData(path, columns, tuple(rows), warnings)


def _read_xlsx(path: Path) -> SheetData:
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.worksheets[0]
            return _validate_rows(path, sheet.iter_rows(values_only=True), padded_header=True)
        finally:
            workbook.close()
    except ConsolidationError:
        raise
    except Exception as exc:
        raise ConsolidationError(f"could not read {path}: {exc}") from exc


def read_sheet(path: Path, csv_options: ReaderOptions = ReaderOptions()) -> SheetData:
    """Read the selected input by extension and validate its tabular structure."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _read_xlsx(path)
    if suffix == ".xls":
        header, rows = xls_reader.read(path, csv_options)
        return _validate_rows(path, chain((header,), rows), padded_header=True)
    if suffix == ".csv":
        warnings: list[str] = []
        header, rows = csv_reader.read(path, csv_options, report_detection=warnings.append)
        return _validate_rows(path, chain((header,), rows), padded_header=False, warnings=tuple(warnings))
    raise ConsolidationError(f"could not read {path}: unsupported input format {path.suffix!r}")


def validate_headers(reference: SheetData, candidate: SheetData) -> None:
    """Compare the names literally, regardless of order."""
    missing = sorted(set(reference.columns) - set(candidate.columns))
    extra = sorted(set(candidate.columns) - set(reference.columns))
    if missing or extra:
        raise ConsolidationError(
            f"{candidate.path}: missing columns: {missing}; extra columns: {extra}"
        )
