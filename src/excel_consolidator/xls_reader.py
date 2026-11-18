"""Read values from the first worksheet of a legacy BIFF workbook."""
from __future__ import annotations

from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import xlrd

from .errors import ConsolidationError
from .reader_options import ReaderOptions


def _rows(path: Path, sheet: xlrd.sheet.Sheet, datemode: int) -> Iterator[tuple[object, ...]]:
    for row_index in range(sheet.nrows):
        row: list[object] = []
        for column_index, cell in enumerate(sheet.row(row_index)):
            if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                value = None
            elif cell.ctype == xlrd.XL_CELL_TEXT:
                value = cell.value
            elif cell.ctype == xlrd.XL_CELL_NUMBER:
                number = float(cell.value)
                value = int(number) if number.is_integer() else number
            elif cell.ctype == xlrd.XL_CELL_DATE:
                value = xlrd.xldate_as_datetime(cell.value, datemode)
            elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                value = bool(cell.value)
            else:
                location = f"{path}: row {row_index + 1}, column {column_index + 1}"
                if cell.ctype == xlrd.XL_CELL_ERROR:
                    error = xlrd.error_text_from_code.get(cell.value, cell.value)
                    raise ConsolidationError(f"{location}: Excel cell error {error}")
                raise ConsolidationError(f"{location}: unsupported Excel cell type {cell.ctype}")
            row.append(value)
        yield tuple(row)


def read(
    path: Path, csv_options: ReaderOptions,
) -> tuple[tuple[object, ...], list[tuple[object, ...]]]:
    """Return the raw first worksheet. CSV settings have no effect on BIFF."""
    try:
        with StringIO() as diagnostics:
            with xlrd.open_workbook(
                path, logfile=diagnostics, on_demand=True, formatting_info=True, ragged_rows=True,
            ) as workbook:
                rows = _rows(path, workbook.sheet_by_index(0), workbook.datemode)
                header = next(rows, ())
                return header, list(rows)
    except ConsolidationError:
        raise
    except Exception as exc:
        raise ConsolidationError(f"could not read {path}: {exc}") from exc
