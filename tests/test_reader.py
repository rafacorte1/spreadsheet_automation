"""Tests with synthetic spreadsheets created in temporary directories."""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from excel_consolidator import ConsolidationError
from excel_consolidator.reader import (
    SheetData, discover_input_files, read_sheet, validate_headers,
)


def make_sheet(tmp_path: Path, rows: list[list[object]], name: str = "input.xlsx") -> Path:
    """Create a synthetic input and close the workbook."""
    path = tmp_path / name
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    workbook.save(path)
    workbook.close()
    return path


def test_discover_sorted_and_filtered(tmp_path: Path) -> None:
    for name in ["z.xlsx", "a.xlsx", "~$lock.xlsx", "other.csv", "old.xls"]:
        (tmp_path / name).touch()
    (tmp_path / "directory.xlsx").mkdir()
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hidden.xlsx").touch()
    assert discover_input_files(tmp_path) == [tmp_path / "a.xlsx", tmp_path / "z.xlsx"]


def test_discover_empty_and_missing(tmp_path: Path) -> None:
    assert discover_input_files(tmp_path) == []
    assert discover_input_files(tmp_path / "missing") == []


def test_read_valid_raw_values_and_preserve_input(tmp_path: Path) -> None:
    path = make_sheet(tmp_path, [[" Name ", 42], ["Ana", 7], ["Bea", False]])
    original = path.read_bytes()
    assert read_sheet(path) == SheetData(path, (" Name ", "42"), (("Ana", 7), ("Bea", False)))
    assert path.read_bytes() == original


@pytest.mark.parametrize("header", [
    [None, "B"], ["", "B"], ["   ", "B"], ["A", None, "B"],
    ["A", "A"], [1, "1"], ["source_file", "B"],
])
def test_invalid_headers(tmp_path: Path, header: list[object]) -> None:
    path = make_sheet(tmp_path, [header, [1] * len(header)])
    with pytest.raises(ConsolidationError, match=path.name):
        read_sheet(path)


def test_corrupted_file_wraps_cause(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"not an xlsx archive")
    with pytest.raises(ConsolidationError, match=str(path)) as caught:
        read_sheet(path)
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize("rows", [[["A"]], [["A"], [None], [""]]])
def test_no_data(tmp_path: Path, rows: list[list[object]]) -> None:
    path = make_sheet(tmp_path, rows)
    with pytest.raises(ConsolidationError, match="no data rows"):
        read_sheet(path)


def test_empty_sheet(tmp_path: Path) -> None:
    path = make_sheet(tmp_path, [])
    with pytest.raises(ConsolidationError, match="missing header"):
        read_sheet(path)


def test_short_rows_and_internal_empty_rows(tmp_path: Path) -> None:
    path = make_sheet(tmp_path, [
        [None], ["A", "B"], [1], [None, None], [2, 3], [None, None],
    ])
    assert read_sheet(path).rows == ((1, None), (None, None), (2, 3))


def test_extra_value_beyond_header(tmp_path: Path) -> None:
    path = make_sheet(tmp_path, [["A"], [1, 2]])
    with pytest.raises(ConsolidationError, match="beyond the last header column"):
        read_sheet(path)


def test_only_first_sheet(tmp_path: Path) -> None:
    path = tmp_path / "two.xlsx"
    workbook = Workbook()
    workbook.active.append(["A"])
    workbook.active.append([1])
    workbook.create_sheet("ignored").append(["source_file"])
    workbook.save(path)
    workbook.close()
    assert read_sheet(path).rows == ((1,),)


def test_reordered_headers(tmp_path: Path) -> None:
    reference = read_sheet(make_sheet(tmp_path, [["A", "B"], [1, 2]], "a.xlsx"))
    candidate = read_sheet(make_sheet(tmp_path, [["B", "A"], [2, 1]], "b.xlsx"))
    assert validate_headers(reference, candidate) is None


@pytest.mark.parametrize("candidate_columns", [("A", "C"), ("a", "B"), (" A", "B"), ("A", "B ")])
def test_incompatible_literal_headers(tmp_path: Path, candidate_columns: tuple[str, ...]) -> None:
    reference = SheetData(tmp_path / "a.xlsx", ("A", "B"), ())
    candidate = SheetData(tmp_path / "b.xlsx", candidate_columns, ())
    with pytest.raises(ConsolidationError) as caught:
        validate_headers(reference, candidate)
    message = str(caught.value)
    assert str(candidate.path) in message
    assert "missing columns:" in message and "extra columns:" in message
    for name in set(reference.columns) ^ set(candidate.columns):
        assert repr(name) in message
