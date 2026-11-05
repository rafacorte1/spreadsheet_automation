"""Acceptance of the vertical consolidation without changing the inputs."""
from __future__ import annotations

import pytest

from excel_consolidator.consolidator import consolidate
from excel_consolidator.reader import ConsolidationError


def test_vertical_sorted_raw_values_and_unchanged_inputs(tmp_path, make_xlsx):
    second = make_xlsx(tmp_path / "z.xlsx", [["B", "A"], [False, "repeated"], [7, "end"]])
    first = make_xlsx(tmp_path / "a.xlsx", [["A", "B"], ["repeated", False], ["null", None], ["decimal", 1.23456789]])
    before = {path: path.read_bytes() for path in (first, second)}
    result = consolidate(tmp_path)
    assert [sheet.path for sheet in result.files] == [first, second]
    assert list(result.frame.columns) == ["A", "B", "source_file"]
    assert result.frame.values.tolist() == [
        ["repeated", False, "a.xlsx"], ["null", None, "a.xlsx"],
        ["decimal", 1.23456789, "a.xlsx"], ["repeated", False, "z.xlsx"],
        ["end", 7, "z.xlsx"],
    ]
    assert result.frame.iloc[1, 1] is None
    assert result.frame.iloc[0, 1] is False
    assert result.rows == sum(len(sheet.rows) for sheet in result.files)
    assert result.frame.index.tolist() == list(range(result.rows))
    assert all(path.read_bytes() == content for path, content in before.items())


def test_empty_directory(tmp_path):
    with pytest.raises(ConsolidationError, match=f"no .xlsx files in {tmp_path}"):
        consolidate(tmp_path)


def test_origin_collision(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "a.xlsx", [["source_file"], ["x"]])
    with pytest.raises(ConsolidationError, match="source_file"):
        consolidate(tmp_path)


def test_incompatible_columns(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "a.xlsx", [["A"], [1]])
    make_xlsx(tmp_path / "b.xlsx", [["B"], [2]])
    with pytest.raises(ConsolidationError, match="missing"):
        consolidate(tmp_path)


def test_key_validation_and_first_occurrence(tmp_path, make_xlsx):
    from excel_consolidator.quality import QualityOptions
    make_xlsx(tmp_path / "a.xlsx", [["id", "amount"], [1, "first"], [2, None]])
    make_xlsx(tmp_path / "z.xlsx", [["amount", "id"], ["second", 1]])
    ignored = consolidate(tmp_path, QualityOptions(key=("unknown",)))
    assert ignored.rows == 3
    assert ignored.options.key == ()
    assert len(ignored.warnings) == 1 and "ignored" in ignored.warnings[0]
    assert ignored.report[ignored.report.metric == "mode"].value.tolist() == ["identical_rows"]
    with pytest.raises(ConsolidationError, match="unknown.*a.xlsx"):
        consolidate(tmp_path, QualityOptions(key=("unknown",), remove_duplicates=True))
    raw = consolidate(tmp_path)
    assert raw.rows == 3
    result = consolidate(tmp_path, QualityOptions(key=("id",), remove_duplicates=True))
    assert result.frame.values.tolist() == [[1, "first", "a.xlsx"], [2, None, "a.xlsx"]]
    assert result.report[result.report.metric == "rows_read"].value.tolist() == [2, 1]
    assert result.report[result.report.metric == "mode"].value.tolist() == ["key:id"]
