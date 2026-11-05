"""Layout and totals of the quality report."""
from pathlib import Path

from excel_consolidator.reader import SheetData
from excel_consolidator.quality import DuplicateReport, QualityOptions, standardize
from excel_consolidator.report import REPORT_COLUMNS, QualitySummary, build_report, count_nulls, summarize


def test_exact_layout_and_summary():
    sheets = [SheetData(Path(name), ("B", "A"), ((" x ", None),)) for name in ("z.xlsx", "a.xlsx")]
    options = QualityOptions(trim_text=True)
    results = [standardize(sheet, options) for sheet in sheets]
    report = build_report([r.sheet for r in results], {r.sheet.path.name: r.stats for r in results},
                          DuplicateReport(1, 1, "identical_rows"), options)
    expected = [("summary", name, "", "rows_read", 1) for name in ("a.xlsx", "z.xlsx")]
    expected += [("nulls", name, col, "nulls", count) for name in ("a.xlsx", "z.xlsx") for col, count in (("B", 0), ("A", 1))]
    expected += [("standardization", name, col, metric, value) for name in ("a.xlsx", "z.xlsx")
                 for col, count in (("B", 1), ("A", 0))
                 for metric, value in (("changed_trim_text", count), ("failed_trim_text", 0))]
    expected += [("duplicates", "", "", metric, value) for metric, value in
                 (("mode", "identical_rows"), ("duplicate_rows", 1), ("rows_removed", 1))]
    assert tuple(report.columns) == REPORT_COLUMNS
    assert list(report.itertuples(index=False, name=None)) == expected
    assert summarize(report) == QualitySummary(2, 1, 1, 2)


def test_nulls_only_data_and_no_inactive_rules():
    sheet = SheetData(Path("a.xlsx"), ("A", "source_file"), ((None, None), ("   ", ""), ("", ""), (0, None)))
    assert count_nulls(sheet) == {"A": 3}
    report = build_report([sheet], {}, DuplicateReport(0, 0, "identical_rows"), QualityOptions())
    assert report.section.tolist() == ["summary", "nulls", "duplicates", "duplicates", "duplicates"]
    assert summarize(report) == QualitySummary(3, 0, 0, 0)


def test_counts_each_active_rule_separately():
    options = QualityOptions(trim_text=True, normalize_numbers=True, dates_iso=True)
    result = standardize(SheetData(Path("a.xlsx"), ("A",), ((" 007 ",), ("01/02/2024",), ("no",))), options)
    report = build_report([result.sheet], {"a.xlsx": result.stats}, DuplicateReport(0, 0, "identical_rows"), options)
    metrics = report[report.section == "standardization"].set_index("metric").value.to_dict()
    assert metrics == {"changed_trim_text": 1, "failed_trim_text": 0,
                       "changed_normalize_numbers": 1, "failed_normalize_numbers": 1,
                       "changed_dates_iso": 1, "failed_dates_iso": 1}
    assert summarize(report).changed == 3
