"""Synthetic CSV and BIFF fixtures exercising shared reader invariants."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path

import pytest
import xlwt
from openpyxl import load_workbook

from excel_consolidator.cli import run
from excel_consolidator.consolidator import consolidate
from excel_consolidator.errors import ConsolidationError
from excel_consolidator.quality import QualityOptions
from excel_consolidator.reader import discover_input_files, read_sheet, validate_headers
from excel_consolidator.reader_options import ReaderOptions


def make_xls(path: Path, rows: list[list[object]]) -> Path:
    """Write a BIFF workbook whose cells use the types supplied in the rows."""
    workbook = xlwt.Workbook()
    worksheet = workbook.add_sheet("Data")
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            worksheet.write(row_index, column_index, value)
    workbook.save(str(path))
    return path


@pytest.mark.parametrize(("delimiter", "amount"), [
    (",", "007"), (";", "1.234,56"), ("\t", "42"), ("|", "9.25"),
])
def test_detects_csv_delimiters_and_preserves_text(
    tmp_path: Path, delimiter: str, amount: str,
) -> None:
    path = tmp_path / "export.csv"
    path.write_text(f" Name {delimiter}amount\n Ana {delimiter}{amount}\n", encoding="utf-8")
    sheet = read_sheet(path)
    assert sheet.columns == (" Name ", "amount")
    assert sheet.rows == ((" Ana ", amount),)
    assert sheet.warnings == (f"csv {path}: encoding=utf-8 delimiter={delimiter!r}",)


@pytest.mark.parametrize(("text", "delimiter", "columns"), [
    ("A,B;C\n1,2;3\n", ",", ("A", "B;C")),
    ("A,B;C;D\n1,2;3;4\n", ";", ("A,B", "C", "D")),
    ("A,B;C\n1,2;3\n4;5\n", ";", ("A,B", "C")),
])
def test_csv_delimiter_consistency_width_and_ties(
    tmp_path: Path, text: str, delimiter: str, columns: tuple[str, ...],
) -> None:
    path = tmp_path / "ambiguous.csv"
    path.write_text(text, encoding="utf-8")
    sheet = read_sheet(path)
    assert sheet.columns == columns
    assert sheet.warnings == (f"csv {path}: encoding=utf-8 delimiter={delimiter!r}",)


def test_csv_detection_uses_first_fifty_nonempty_lines(tmp_path: Path) -> None:
    path = tmp_path / "sampled.csv"
    path.write_text("A,B;C\n" + "\n1,2;3\n" * 49 + "4;5\n", encoding="utf-8")
    sheet = read_sheet(path)
    assert sheet.columns == ("A", "B;C")
    assert sheet.rows[-1] == ("4;5", None)


def test_csv_sample_counts_physical_lines_in_quoted_records(tmp_path: Path) -> None:
    path = tmp_path / "sampled.csv"
    path.write_text('A,B;C\n"first\nsecond",2;3\n' + "1,2;3\n" * 47 + "4;5\n", encoding="utf-8")
    sheet = read_sheet(path)
    assert sheet.columns == ("A", "B;C")
    assert sheet.rows[0] == ("first\nsecond", "2;3")
    assert sheet.rows[-1] == ("4;5", None)


@pytest.mark.parametrize(("encoding", "explicit", "value", "detected"), [
    ("iso-8859-1", "iso-8859-1", "São Tomé", "iso-8859-1"),
    ("cp1252", None, "São Tomé €", "cp1252"),
    ("utf-8-sig", None, "São Tomé", "utf-8-sig"),
])
def test_csv_latin1_cp1252_and_utf8_bom(
    tmp_path: Path, encoding: str, explicit: str | None, value: str, detected: str,
) -> None:
    path = tmp_path / "accented.csv"
    path.write_text(f"city;id\n{value};001\n", encoding=encoding)
    sheet = read_sheet(path, ReaderOptions(csv_encoding=explicit))
    assert sheet.columns == ("city", "id")
    assert sheet.rows == ((value, "001"),)
    assert sheet.warnings == (f"csv {path}: encoding={detected} delimiter=';'",)


def test_csv_empty_fields_short_rows_and_trailing_rows(tmp_path: Path) -> None:
    path = tmp_path / "gaps.csv"
    path.write_text("\nA,B,C\nx,,z\n,,\ny\nw,9,t,\n,,\n\n", encoding="utf-8")
    sheet = read_sheet(path, ReaderOptions(csv_delimiter=","))
    assert sheet.rows == (("x", None, "z"), (None, None, None),
                          ("y", None, None), ("w", "9", "t"))


def test_csv_quoted_delimiters_and_multiline_values(tmp_path: Path) -> None:
    path = tmp_path / "quoted.csv"
    path.write_bytes(b'"Full,name",Note\r\n"Tom,Jr","first\r\n\r\nlast"\r\n')
    sheet = read_sheet(path)
    assert sheet.columns == ("Full,name", "Note")
    assert sheet.rows == (("Tom,Jr", "first\r\n\r\nlast"),)


def test_csv_one_column_warns_about_comma_fallback(tmp_path: Path) -> None:
    path = tmp_path / "one.csv"
    path.write_text("Item\none\n\n two \n", encoding="utf-8")
    sheet = read_sheet(path)
    assert sheet.columns == ("Item",)
    assert sheet.rows == (("one",), (None,), (" two ",))
    assert sheet.warnings == (
        f"csv {path}: encoding=utf-8 delimiter=',' (no consistent multi-column delimiter; using comma)",
    )


@pytest.mark.parametrize(("text", "message"), [
    ("A,B\nx,y,z\n", "value beyond the last header column"),
    ("A,B\n", "no data rows"),
    ("A,B\n,\n\n", "no data rows"),
    ("A,A\nx,y\n", "duplicate headers"),
    ("A,source_file\nx,y\n", "reserved column source_file"),
    ("A,\nx,y\n", "blank header"),
    ("\n,\n", "missing header"),
])
def test_csv_structural_errors(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "invalid.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConsolidationError, match=message) as caught:
        read_sheet(path)
    assert str(path) in str(caught.value)


@pytest.mark.parametrize(("prefix", "encoding"), [
    (b"", "utf-8"), (b"\xef\xbb\xbf", "utf-8-sig"),
])
def test_explicit_csv_decode_error_reports_absolute_byte_position(
    tmp_path: Path, prefix: bytes, encoding: str,
) -> None:
    path = tmp_path / "wrong-encoding.csv"
    path.write_bytes(prefix + b"A\n\xe9\n")
    with pytest.raises(ConsolidationError, match=f"at byte {len(prefix) + 2}") as caught:
        read_sheet(path, ReaderOptions(csv_encoding=encoding))
    assert str(path) in str(caught.value)
    assert isinstance(caught.value.__cause__, UnicodeDecodeError)


@pytest.mark.parametrize("dates_1904", [False, True])
def test_xls_values_and_trailing_blanks(tmp_path: Path, dates_1904: bool) -> None:
    path = tmp_path / "legacy.XLS"
    workbook = xlwt.Workbook()
    workbook.dates_1904 = dates_1904
    sheet = workbook.add_sheet("First")
    date_style = xlwt.easyxf(num_format_str="YYYY-MM-DD HH:MM:SS")
    date = datetime(2026, 11, 18, 10, 30, 25)
    for column, header in enumerate((" Label ", "int", "float", "date", "flag", "empty", "blank")):
        sheet.write(0, column, header)
    for row, flag in ((1, True), (2, False)):
        for column, value in enumerate((" text ", 42, 0.25)):
            sheet.write(row, column, value)
        sheet.write(row, 3, date, date_style)
        sheet.write(row, 4, flag)
        sheet.write(row, 6, None, date_style)
    sheet.write(5, 0, None, date_style)
    workbook.add_sheet("Ignored").row(0).set_cell_error(0, "#DIV/0!")
    workbook.save(str(path))
    data = read_sheet(path)
    assert data.columns == (" Label ", "int", "float", "date", "flag", "empty", "blank")
    assert data.rows == ((" text ", 42, 0.25, date, True, None, None),
                         (" text ", 42, 0.25, date, False, None, None))
    assert tuple(type(value) for value in data.rows[0][1:5]) == (int, float, datetime, bool)
    assert data.warnings == ()


def test_xls_corruption_is_wrapped(tmp_path: Path) -> None:
    path = tmp_path / "broken.xls"
    path.write_bytes(b"not an Excel workbook")
    with pytest.raises(ConsolidationError, match="could not read") as caught:
        read_sheet(path)
    assert str(path) in str(caught.value)
    assert caught.value.__cause__ is not None


@pytest.mark.parametrize(("rows", "message"), [
    ([["A"], [None]], "no data rows"),
    ([["A"], [1, 2]], "value beyond the last header column"),
    ([["A", "A"], [1, 2]], "duplicate headers"),
    ([["A", "source_file"], [1, 2]], "reserved column source_file"),
])
def test_xls_structural_errors(tmp_path: Path, rows: list[list[object]], message: str) -> None:
    path = make_xls(tmp_path / "invalid.xls", rows)
    with pytest.raises(ConsolidationError, match=message) as caught:
        read_sheet(path)
    assert str(path) in str(caught.value)


def test_xls_cell_error_identifies_its_location(tmp_path: Path) -> None:
    path = tmp_path / "cell-error.xls"
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet("Data")
    sheet.write(0, 0, "A")
    sheet.write(0, 1, "B")
    sheet.write(1, 0, "valid")
    sheet.row(1).set_cell_error(1, "#DIV/0!")
    workbook.save(str(path))
    with pytest.raises(ConsolidationError, match=r"row 2, column 2: Excel cell error #DIV/0!") as caught:
        read_sheet(path)
    assert str(path) in str(caught.value)


def test_mixed_formats_sort_reorder_preserve_sources_and_inputs(tmp_path: Path, make_xlsx) -> None:
    inputs = tmp_path / "inputs"
    modern = make_xlsx(inputs / "z.XlSX", [["name", "qty"], ["C", 3]])
    legacy = make_xls(inputs / "a.XlS", [["qty", "name"], [1, "A"]])
    csv = inputs / "b.CsV"
    csv.write_text("name;qty\n B ;2\n", encoding="utf-8")
    (inputs / "~$ignore.CSV").touch()
    (inputs / "directory.xls").mkdir()
    (inputs / "ignore.txt").touch()
    paths = [legacy, csv, modern]
    assert discover_input_files(inputs) == paths
    assert discover_input_files(inputs, ("csv",)) == [csv]
    hashes = {path: sha256(path.read_bytes()).hexdigest() for path in paths}
    output = tmp_path / "out" / "consolidated.xlsx"
    result = run(inputs, output, QualityOptions(trim_text=True, normalize_numbers=True))
    assert result.frame.columns.tolist() == ["qty", "name", "source_file"]
    expected = [(1, "A", legacy.name), (2, "B", csv.name), (3, "C", modern.name)]
    assert list(result.frame.itertuples(index=False, name=None)) == expected
    assert validate_headers(result.files[0], result.files[1]) is None
    assert validate_headers(result.files[0], result.files[2]) is None
    assert result.files[1].warnings == result.warnings == (f"csv {csv}: encoding=utf-8 delimiter=';'",)
    workbook = load_workbook(output, read_only=True, data_only=True)
    try:
        assert list(workbook["consolidated"].values)[1:] == expected
    finally:
        workbook.close()
    assert {path: sha256(path.read_bytes()).hexdigest() for path in paths} == hashes


def test_csv_xlsx_parity_cell_by_cell_after_standardization(tmp_path: Path, make_xlsx) -> None:
    date = datetime(2026, 11, 18, 10, 30)
    xlsx = make_xlsx(tmp_path / "xlsx" / "same.xlsx",
                     [["name", "amount", "date", "note"], ["Ana", 1234.56, date, None]])
    csv = tmp_path / "csv" / "same.csv"
    csv.parent.mkdir()
    csv.write_text("name;amount;date;note\nAna;1.234,56;18/11/2026 10:30:00;\n", encoding="utf-8")
    options = QualityOptions(normalize_numbers=True, dates_iso=True)
    a = consolidate(xlsx.parent, options).frame
    b = consolidate(csv.parent, options).frame
    assert a.columns.tolist() == b.columns.tolist()
    for left_row, right_row in zip(a.itertuples(index=False, name=None),
                                   b.itertuples(index=False, name=None), strict=True):
        for left, right in zip(left_row[:-1], right_row[:-1], strict=True):
            assert type(left) is type(right) and left == right
        assert Path(left_row[-1]).stem == Path(right_row[-1]).stem


def test_mixed_header_mismatch_preserves_existing_output_and_cleans_temp(
    tmp_path: Path, make_xlsx,
) -> None:
    output = make_xlsx(tmp_path / "output" / "consolidated.xlsx", [["previous"], ["keep"]])
    previous = output.read_bytes()
    xlsx = make_xlsx(tmp_path / "input" / "a.xlsx", [["A", "B"], [1, 2]])
    xls = make_xls(xlsx.parent / "b.xls", [["B", "A"], [2, 1]])
    csv = xlsx.parent / "c.csv"
    csv.write_text(" A,B\n1,2\n", encoding="utf-8")
    hashes = {path: sha256(path.read_bytes()).hexdigest() for path in (xlsx, xls, csv)}
    with pytest.raises(ConsolidationError, match=r"missing columns: \['A'\]; extra columns: \[' A'\]"):
        run(xlsx.parent, output)
    assert output.read_bytes() == previous
    assert list(output.parent.iterdir()) == [output]
    assert {path: sha256(path.read_bytes()).hexdigest() for path in hashes} == hashes
