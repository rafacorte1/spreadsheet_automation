"""Data quality with synthetic inputs, without external files."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from excel_consolidator.quality import (
    DATES_ISO, NORMALIZE_NUMBERS, TRIM_TEXT, ColumnStats, DuplicateReport, QualityOptions,
    build_duplicate_report, find_duplicates, standardize,
)
from excel_consolidator.reader import ORIGIN_COLUMN, SheetData
from excel_consolidator.report import build_report, summarize


def make_sheet(rows: tuple[tuple[object, ...], ...], columns: tuple[str, ...] = ("amount",)) -> SheetData:
    return SheetData(Path("synthetic.xlsx"), columns, rows)


def test_no_flags_preserves_rows_and_all_column_stats() -> None:
    sheet = make_sheet(((" 42 ", None), ("abc", 5)), ("a", "b"))
    result = standardize(sheet, QualityOptions())
    assert result.sheet == sheet
    assert result.sheet is not sheet
    assert result.stats == {"a": ColumnStats(), "b": ColumnStats()}
    assert not QualityOptions().any_standardization


@pytest.mark.parametrize("flag", ["trim_text", "normalize_numbers", "dates_iso"])
def test_any_standardization(flag: str) -> None:
    assert QualityOptions(**{flag: True}).any_standardization


def test_trim_and_non_string_values() -> None:
    values = ("  a  b  ", "\ttext\n", "normal", 7, None, True, date(2026, 11, 5), datetime(2026, 11, 5))
    sheet = make_sheet(tuple((value,) for value in values))
    result = standardize(sheet, QualityOptions(trim_text=True))
    assert result.sheet.rows == tuple((value,) for value in ("a  b", "text", *values[2:]))
    assert result.stats["amount"] == ColumnStats(changed=2)
    assert sheet.rows == tuple((value,) for value in values)


@pytest.mark.parametrize(("text", "expected"), [
    ("1.234,56", 1234.56), ("1.234", 1234), ("-1.234", -1234),
    ("-12,5", -12.5), ("42", 42), ("-7", -7),
    ("12.345.678,9", 12345678.9), ("1234,56", 1234.56), (" 42\t", 42),
])
def test_numbers(text: str, expected: int | float) -> None:
    result = standardize(make_sheet(((text,),)), QualityOptions(normalize_numbers=True))
    actual = result.sheet.rows[0][0]
    assert actual == expected
    assert type(actual) is type(expected)
    assert result.stats["amount"] == ColumnStats(changed=1)


@pytest.mark.parametrize("text", [
    "R$ 1.234,56", "abc", "1,2,3", "1.23.456", "$42", "(42)", "1e3", "42kg", " abc ", "",
])
def test_invalid_numbers_preserved(text: str) -> None:
    result = standardize(make_sheet(((text,),)), QualityOptions(normalize_numbers=True))
    assert result.sheet.rows == ((text,),)
    expected_failures = {NORMALIZE_NUMBERS: 1} if text else {}
    assert result.stats["amount"] == ColumnStats(failed=expected_failures)


@pytest.mark.parametrize(("text", "expected"), [
    ("05/11/2026", date(2026, 11, 5)),
    ("2026-11-05", date(2026, 11, 5)),
    ("2026-11-05 14:30:00", datetime(2026, 11, 5, 14, 30)),
    ("05/11/2026 14:30:00", datetime(2026, 11, 5, 14, 30)),
])
def test_dates(text: str, expected: date | datetime) -> None:
    result = standardize(make_sheet(((text,),)), QualityOptions(dates_iso=True))
    actual = result.sheet.rows[0][0]
    assert actual == expected
    assert type(actual) is type(expected)
    assert result.stats["amount"] == ColumnStats(changed=1)


@pytest.mark.parametrize("text", ["31/02/2026", "2026-13-01", "05/11/26", "abc", "5/11/2026", " 05/11/2026 "])
def test_invalid_dates_preserved(text: str) -> None:
    result = standardize(make_sheet(((text,),)), QualityOptions(dates_iso=True))
    assert result.sheet.rows == ((text,),)
    assert result.stats["amount"] == ColumnStats(failed={DATES_ISO: 1})


def test_independent_column_counts_and_original_unchanged() -> None:
    sheet = make_sheet(((" a ", " b "), (" c ", "d")), ("a", "b"))
    result = standardize(sheet, QualityOptions(trim_text=True))
    assert result.stats == {"a": ColumnStats(changed=2), "b": ColumnStats(changed=1)}
    assert result.sheet.rows == (("a", "b"), ("c", "d"))
    assert sheet.rows == ((" a ", " b "), (" c ", "d"))
    assert result.sheet.path == sheet.path
    assert result.sheet.columns == sheet.columns


def test_rule_order_and_accumulated_counts() -> None:
    sheet = make_sheet(((" 42 ",), (" 05/11/2026 ",), (" abc ",)))
    result = standardize(sheet, QualityOptions(True, True, True))
    assert result.sheet.rows == ((42,), (date(2026, 11, 5),), ("abc",))
    assert result.stats["amount"] == ColumnStats(
        changed=5, failed={NORMALIZE_NUMBERS: 1, DATES_ISO: 1},
    )
    assert sheet.rows == ((" 42 ",), (" 05/11/2026 ",), (" abc ",))


@pytest.mark.parametrize(("text", "expected"), [
    ("05/11/2026", date(2026, 11, 5)),
    ("1.234,56", 1234.56),
])
def test_conversion_suppresses_cell_failures(text: str, expected: object) -> None:
    result = standardize(
        make_sheet(((text,),)), QualityOptions(normalize_numbers=True, dates_iso=True),
    )
    assert result.sheet.rows == ((expected,),)
    assert type(result.sheet.rows[0][0]) is type(expected)
    assert result.stats["amount"] == ColumnStats(changed=1)


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
@pytest.mark.parametrize("options", [
    QualityOptions(normalize_numbers=True),
    QualityOptions(dates_iso=True),
    QualityOptions(normalize_numbers=True, dates_iso=True),
])
def test_blank_strings_skip_conversions(text: str, options: QualityOptions) -> None:
    result = standardize(make_sheet(((text,),)), options)
    assert result.sheet.rows == ((text,),)
    assert result.stats["amount"] == ColumnStats()


def test_trim_blank_string_counts_only_trim() -> None:
    result = standardize(
        make_sheet((("   ",),)), QualityOptions(trim_text=True, dates_iso=True),
    )
    assert result.sheet.rows == (("",),)
    assert result.stats["amount"] == ColumnStats(changed=1)


def test_unconverted_string_counts_both_failures() -> None:
    result = standardize(
        make_sheet((("abc",),)), QualityOptions(normalize_numbers=True, dates_iso=True),
    )
    assert result.sheet.rows == (("abc",),)
    assert result.stats["amount"] == ColumnStats(
        failed={NORMALIZE_NUMBERS: 1, DATES_ISO: 1},
    )


def test_converted_cell_does_not_hide_other_cell_failures() -> None:
    result = standardize(
        make_sheet((("05/11/2026",), ("abc",))),
        QualityOptions(normalize_numbers=True, dates_iso=True),
    )
    assert result.sheet.rows == ((date(2026, 11, 5),), ("abc",))
    assert result.stats["amount"] == ColumnStats(
        changed=1, failed={NORMALIZE_NUMBERS: 1, DATES_ISO: 1},
    )


def test_all_rules_skip_non_strings() -> None:
    values = (42, 1.5, None, False, date(2026, 11, 5), datetime(2026, 11, 5))
    sheet = make_sheet(tuple((value,) for value in values))
    result = standardize(sheet, QualityOptions(True, True, True))
    assert result.sheet == sheet
    assert all(new[0] is old[0] for new, old in zip(result.sheet.rows, sheet.rows))
    assert result.stats == {"amount": ColumnStats()}


@pytest.fixture
def frame() -> pd.DataFrame:
    return pd.DataFrame([
        ("Ana", None, "a.xlsx"), ("Ana", None, "b.xlsx"),
        ("Ana", 10, "c.xlsx"), ("Bea", None, "d.xlsx"),
    ], columns=["name", "amount", ORIGIN_COLUMN], dtype=object, index=[4, 6, 8, 10])


def test_duplicate_mask_preserves_first_and_index(frame: pd.DataFrame) -> None:
    mask = find_duplicates(frame, ("name", "amount"))
    assert mask.tolist() == [False, True, False, False]
    assert mask.index.equals(frame.index)
    assert mask.dtype == bool


@pytest.mark.parametrize("remove", [False, True])
def test_report_whole_rows_excludes_origin(frame: pd.DataFrame, remove: bool) -> None:
    original = frame.copy(deep=True)
    report = build_duplicate_report(frame, QualityOptions(remove_duplicates=remove))
    assert report.total == 1
    assert report.removed == (1 if remove else 0)
    assert report.mode == "identical_rows"
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("remove", [False, True])
def test_report_by_key(frame: pd.DataFrame, remove: bool) -> None:
    options = QualityOptions(key=("name",), remove_duplicates=remove)
    assert find_duplicates(frame, options.key).tolist() == [False, True, True, False]
    report = build_duplicate_report(frame, options)
    assert report.total == 2
    assert report.removed == (2 if remove else 0)
    assert report.mode == "key:name"


def test_explicit_origin_key_is_respected(frame: pd.DataFrame) -> None:
    report = build_duplicate_report(frame, QualityOptions(key=("name", ORIGIN_COLUMN)))
    assert report.total == 0
    assert report.mode == "key:name,source_file"


def test_empty_sheet_has_stats() -> None:
    result = standardize(make_sheet((), ("a", "b")), QualityOptions(True, True, True))
    assert result.sheet.rows == ()
    assert result.stats == {"a": ColumnStats(), "b": ColumnStats()}


def test_stats_dictionaries_are_independent() -> None:
    first, second = ColumnStats(), ColumnStats()
    first.failed[NORMALIZE_NUMBERS] = 1
    assert second.failed == {}


@pytest.mark.parametrize(("text", "expected", "changed", "rule_changes", "failures"), [
    ("  Ana  ", "Ana", 1, {TRIM_TEXT: 1}, {NORMALIZE_NUMBERS: 1, DATES_ISO: 1}),
    (" 42 ", 42, 2, {TRIM_TEXT: 1, NORMALIZE_NUMBERS: 1}, {}),
    (" 05/11/2026 ", date(2026, 11, 5), 2, {TRIM_TEXT: 1, DATES_ISO: 1}, {}),
    (" abc ", "abc", 1, {TRIM_TEXT: 1}, {NORMALIZE_NUMBERS: 1, DATES_ISO: 1}),
    ("", "", 0, {}, {}),
    ("   ", "", 1, {TRIM_TEXT: 1}, {}),
])
def test_trim_preserves_failures_unless_conversion_succeeds(
    text: str, expected: object, changed: int,
    rule_changes: dict[str, int], failures: dict[str, int],
) -> None:
    result = standardize(make_sheet(((text,),)), QualityOptions(True, True, True))
    assert result.sheet.rows == ((expected,),)
    assert type(result.sheet.rows[0][0]) is type(expected)
    stats = result.stats["amount"]
    assert stats.changed == changed
    assert stats.changed_by_rule == rule_changes
    assert stats.failed == failures


@pytest.mark.parametrize(("rows", "expected", "changed", "rule_changes"), [
    ((("  Ana  ",), ("1.234,56",), ("",)),
     (("Ana",), (1234.56,), ("",)), 2, {TRIM_TEXT: 1, NORMALIZE_NUMBERS: 1}),
    ((("  Ana  ",), (" 1.234,56 ",), ("",), ("42",)),
     (("Ana",), (1234.56,), ("",), (42,)), 4, {TRIM_TEXT: 2, NORMALIZE_NUMBERS: 2}),
])
def test_mixed_column_trim_failures_reach_report(
    rows: tuple[tuple[object, ...], ...], expected: tuple[tuple[object, ...], ...],
    changed: int, rule_changes: dict[str, int],
) -> None:
    options = QualityOptions(True, True, True)
    result = standardize(make_sheet(rows), options)
    assert result.sheet.rows == expected
    stats = result.stats["amount"]
    assert stats.changed == changed
    assert stats.changed_by_rule == rule_changes
    assert stats.failed == {NORMALIZE_NUMBERS: 1, DATES_ISO: 1}
    report = build_report(
        [result.sheet], {result.sheet.path.name: result.stats},
        DuplicateReport(0, 0, "identical_rows"), options,
    )
    metrics = report.loc[report["section"] == "standardization"].set_index("metric")["value"].to_dict()
    assert metrics == {
        "changed_trim_text": rule_changes[TRIM_TEXT], "failed_trim_text": 0,
        "changed_normalize_numbers": rule_changes[NORMALIZE_NUMBERS],
        "failed_normalize_numbers": 1,
        "changed_dates_iso": 0, "failed_dates_iso": 1,
    }
    assert summarize(report).changed == changed
