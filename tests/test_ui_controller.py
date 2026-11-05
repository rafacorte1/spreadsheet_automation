"""Acceptance of the interface control layer, without opening a window."""
from __future__ import annotations

import pandas as pd
import pytest

from excel_consolidator.config import DEFAULT_INPUT, DEFAULT_OUTPUT
from excel_consolidator.errors import ConsolidationError
from excel_consolidator.quality import QualityOptions
from excel_consolidator.ui.controller import (
    FormFields, build_config, default_config, format_summary, load_base, read_log_tail,
    run_from_fields, split_key,
)


def fields_for(tmp_path, **overrides) -> FormFields:
    """Fields ready for one run inside the temporary directory."""
    base = dict(
        input_dir=str(tmp_path / "input"),
        output_path=str(tmp_path / "out" / "consolidated.xlsx"),
        log_file=str(tmp_path / "out" / "consolidation.log"),
    )
    base.update(overrides)
    return FormFields(**base)


def test_full_run_writes_output_and_summary(tmp_path, make_xlsx, capsys):
    make_xlsx(tmp_path / "input" / "b.xlsx", [["name", "amount"], ["Mouse", 50]])
    make_xlsx(tmp_path / "input" / "a.xlsx", [["amount", "name"], [100, "Keyboard"], [10, "Cable"]])
    outcome = run_from_fields(fields_for(tmp_path))
    assert outcome.ok
    assert (outcome.files, outcome.rows) == (2, 3)
    assert outcome.output_path == tmp_path / "out" / "consolidated.xlsx"
    assert outcome.output_path.is_file()
    assert outcome.summary is not None and outcome.summary.nulls == 0
    assert list(outcome.report.columns) == ["section", "file", "column", "metric", "value"]
    assert outcome.message.splitlines()[0:2] == ["files: 2", "rows: 3"]
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")


def test_run_writes_log_and_returns_tail(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "input" / "a.xlsx", [["name"], ["x"]])
    outcome = run_from_fields(fields_for(tmp_path))
    log_path = tmp_path / "out" / "consolidation.log"
    assert log_path.is_file()
    assert "written" in outcome.log_tail[-1]
    assert "start" in outcome.log_tail[0]


def test_error_preserves_previous_output(tmp_path):
    output = tmp_path / "out" / "consolidated.xlsx"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"previous result")
    outcome = run_from_fields(fields_for(tmp_path, input_dir=str(tmp_path / "missing")))
    assert not outcome.ok
    assert outcome.message.startswith("error: ")
    assert "Traceback" not in outcome.message
    assert outcome.report is None and outcome.summary is None
    assert output.read_bytes() == b"previous result"
    assert "error=" in outcome.log_tail[-1]


def test_error_without_config_survives(tmp_path):
    outcome = run_from_fields(fields_for(tmp_path, input_dir="", output_path=""))
    assert not outcome.ok
    assert outcome.message == "error: the input folder is required"
    assert outcome.log_tail == ()


@pytest.mark.parametrize(("text", "expected"), [
    ("", ()), ("  ", ()), ("product", ("product",)),
    ("product, date", ("product", "date")), (" a ,, b ", ("a", "b")),
])
def test_split_key(text, expected):
    assert split_key(text) == expected


def test_build_config_requires_output_path():
    with pytest.raises(ConsolidationError, match="the output file is required"):
        build_config(FormFields(input_dir="input", output_path="  "))


def test_build_config_applies_fields_over_base():
    base = default_config()
    config = build_config(FormFields(
        input_dir="input", output_path="out.xlsx", trim_text=True,
        normalize_numbers=True, dates_iso=True, remove_duplicates=True, key="product, date",
    ), base)
    assert config.input_dir.name == "input"
    assert config.output_path.name == "out.xlsx"
    assert config.options == QualityOptions(
        trim_text=True, normalize_numbers=True, dates_iso=True,
        key=("product", "date"), remove_duplicates=True,
    )


def test_build_config_clears_inherited_key():
    base = default_config()
    base = base.__class__(base.input_dir, base.output_path, base.log_file, QualityOptions(key=("product",)))
    config = build_config(FormFields(input_dir="e", output_path="s.xlsx", key=""), base)
    assert config.options.key == ()


def test_unknown_key_without_removal_is_ignored_with_warning(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "input" / "a.xlsx", [["product", "amount"], ["Mouse", 50]])
    outcome = run_from_fields(fields_for(tmp_path, key="product, date"))
    assert outcome.ok
    assert outcome.message.startswith("files: 1")
    assert len(outcome.warnings) == 1 and "ignored" in outcome.warnings[0]
    assert any("ignored" in line for line in outcome.log_tail)
    report = outcome.report
    assert report.loc[report["metric"] == "mode", "value"].tolist() == ["identical_rows"]
    assert (tmp_path / "out" / "consolidated.xlsx").is_file()


def test_unknown_key_with_removal_returns_error(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "input" / "a.xlsx", [["product", "amount"], ["Mouse", 50]])
    outcome = run_from_fields(fields_for(tmp_path, key="product, date", remove_duplicates=True))
    assert not outcome.ok
    assert "unknown columns" in outcome.message
    assert not (tmp_path / "out" / "consolidated.xlsx").exists()


def test_remove_duplicates_counts_and_rows(tmp_path, make_xlsx):
    rows = [["product", "amount"], ["Mouse", 50], ["Keyboard", 100]]
    make_xlsx(tmp_path / "input" / "a.xlsx", rows)
    make_xlsx(tmp_path / "input" / "b.xlsx", rows)
    outcome = run_from_fields(fields_for(tmp_path, remove_duplicates=True, key="product"))
    assert outcome.ok
    assert outcome.rows == 2
    assert outcome.summary is not None
    assert (outcome.summary.duplicates, outcome.summary.removed) == (2, 2)


def test_form_fields_roundtrip():
    config = build_config(FormFields(
        input_dir="input", output_path="out.xlsx", log_file="app.log",
        trim_text=True, key="product, date",
    ))
    recovered = FormFields.from_config(config)
    assert recovered.input_dir == "input"
    assert recovered.output_path == "out.xlsx"
    assert recovered.log_file == "app.log"
    assert recovered.trim_text is True
    assert recovered.key == "product, date"


def test_load_base_without_file_returns_defaults(tmp_path):
    config, error = load_base()
    assert error is None
    assert config.input_dir == DEFAULT_INPUT and config.output_path == DEFAULT_OUTPUT


def test_load_base_with_invalid_file_returns_error_and_defaults(tmp_path):
    broken = tmp_path / "config.toml"
    broken.write_text("input = 'x'\n[quality]\nfoo = true\n", encoding="utf-8")
    config, error = load_base(broken)
    assert error is not None and "unknown" in error
    assert config.output_path == DEFAULT_OUTPUT


def test_load_base_reads_valid_file(tmp_path):
    valid = tmp_path / "config.toml"
    valid.write_text("input = 'sheets'\noutput = 'out.xlsx'\n", encoding="utf-8")
    config, error = load_base(valid)
    assert error is None
    assert config.input_dir == tmp_path / "sheets"
    assert config.output_path == tmp_path / "out.xlsx"


def test_read_log_tail_limits_lines(tmp_path):
    log = tmp_path / "app.log"
    log.write_text("\n".join(f"line {index}" for index in range(100)), encoding="utf-8")
    tail = read_log_tail(log, lines=3)
    assert tail == ("line 97", "line 98", "line 99")
    assert read_log_tail(log, lines=0) == ()
    assert read_log_tail(tmp_path / "missing.log") == ()


def test_read_log_tail_drops_partial_first_line(tmp_path):
    log = tmp_path / "large.log"
    log.write_text("\n".join("x" * 200 for _ in range(200)), encoding="utf-8")
    tail = read_log_tail(log, lines=5)
    assert len(tail) == 5
    assert all(len(line) == 200 for line in tail)


def test_format_summary_matches_cli_contract(tmp_path):
    outcome = run_from_fields(fields_for(tmp_path))
    assert not outcome.ok
    from excel_consolidator.report import QualitySummary
    text = format_summary(3, 7, tmp_path / "consolidated.xlsx", QualitySummary(1, 2, 3, 4))
    assert text.splitlines() == [
        "files: 3",
        "rows: 7",
        f"output: {(tmp_path / 'consolidated.xlsx').resolve()}",
        "quality: nulls=1 duplicates=2 removed=3 changed=4",
    ]


def test_report_frame_matches_written_sheet(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "input" / "a.xlsx", [["product", "amount"], ["Mouse", 50]])
    outcome = run_from_fields(fields_for(tmp_path))
    assert outcome.ok
    written = pd.read_excel(outcome.output_path, sheet_name="report")
    pd.testing.assert_frame_equal(outcome.report, written.fillna(""))
