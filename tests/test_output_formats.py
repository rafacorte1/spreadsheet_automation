"""Exercise the export modes with synthetic inputs and isolated destinations."""
from __future__ import annotations

import csv
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path

from openpyxl import load_workbook
import pandas as pd
import pytest
import xlwt

from excel_consolidator import writer
from excel_consolidator.cli import main, run
from excel_consolidator.config import load_config
from excel_consolidator.errors import ConsolidationError
from excel_consolidator.ui.controller import FormFields, build_config, run_from_fields


@pytest.fixture
def mixed_inputs(tmp_path: Path, make_xlsx) -> Path:
    folder = tmp_path / "inputs"
    make_xlsx(folder / "a.xlsx", [
        ["name", "amount", "when", "active", "note"],
        ["São Tomé", 7, datetime(2026, 11, 18, 10, 30), True, None],
        ["Bea", 2.5, None, False, 'A, "quoted" line\nnext'],
        ["Cris", 9, None, True, ""],
    ])
    legacy = xlwt.Workbook()
    sheet = legacy.add_sheet("Data")
    for row_index, row in enumerate([
        ["amount", "name", "when", "note", "active"],
        [12, "Dani", None, "legacy", True],
        [4.5, "Eli", None, None, False],
    ]):
        for column_index, value in enumerate(row):
            sheet.write(row_index, column_index, value)
    legacy.save(str(folder / "b.xls"))
    (folder / "c.csv").write_text(
        "name;amount;when;active;note\nFay;15;;yes;csv\nGi;16,25;;no;last\n", encoding="utf-8",
    )
    return folder


def read_csv(path: Path) -> list[tuple[str, ...]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return [tuple(row) for row in csv.reader(stream)]


def test_csv_writes_seven_mixed_rows_with_bom_and_exact_path(mixed_inputs: Path, tmp_path: Path):
    output = tmp_path / "out" / "result.v1.data"
    log = tmp_path / "run.log"
    assert main(["--input", str(mixed_inputs), "--output", str(output), "--log-file", str(log),
                 "--output-format", "csv", "--normalize-numbers"]) == 0
    report = output.with_name("result.v1_report.csv")
    assert set(output.parent.iterdir()) == {output, report}
    assert output.read_bytes().startswith(b"\xef\xbb\xbfname,amount,when,active,note,source_file\n")
    assert report.read_bytes().startswith(b"\xef\xbb\xbfsection,file,column,metric,value\n")
    assert read_csv(output) == [
        ("name", "amount", "when", "active", "note", "source_file"),
        ("São Tomé", "7", "2026-11-18 10:30:00", "True", "", "a.xlsx"),
        ("Bea", "2.5", "", "False", 'A, "quoted" line\nnext', "a.xlsx"),
        ("Cris", "9", "", "True", "", "a.xlsx"),
        ("Dani", "12", "", "True", "legacy", "b.xls"),
        ("Eli", "4.5", "", "False", "", "b.xls"),
        ("Fay", "15", "", "yes", "csv", "c.csv"),
        ("Gi", "16.25", "", "no", "last", "c.csv"),
    ]
    assert read_csv(report)[1:4] == [
        ("summary", "a.xlsx", "", "rows_read", "3"),
        ("summary", "b.xls", "", "rows_read", "2"),
        ("summary", "c.csv", "", "rows_read", "2"),
    ]


def test_csv_uses_minimal_quoting_for_embedded_cr_lf_and_stringifies_dates(tmp_path: Path):
    data = tmp_path / "data.csv"
    frame = pd.DataFrame(
        [(date(2026, 11, 18), 'first\rsecond, "third"\nlast', 2.0, None)],
        columns=["date", "note", "amount", "empty"], dtype=object,
    )
    writer.write_outputs(frame, pd.DataFrame(), {"csv": data})
    assert data.read_bytes() == (
        b'\xef\xbb\xbfdate,note,amount,empty\n2026-11-18,"first\rsecond, ""third""\nlast",2.0,\n'
    )
    assert read_csv(data)[1] == ("2026-11-18", 'first\rsecond, "third"\nlast', "2.0", "")


def test_both_exports_have_cell_by_cell_parity_for_data_and_report(mixed_inputs: Path, tmp_path: Path):
    output = tmp_path / "out" / "result.xlsx"
    assert main(["--input", str(mixed_inputs), "--output", str(output), "--output-format", "both",
                 "--normalize-numbers"]) == 0
    data, report = output.with_suffix(".csv"), output.with_name("result_report.csv")
    assert set(output.parent.iterdir()) == {output, data, report}
    with output.open("rb") as stream:
        book = load_workbook(stream, read_only=True, data_only=True)
        try:
            assert book.sheetnames == ["consolidated", "report"]
            for sheet, csv_output in (("consolidated", data), ("report", report)):
                assert read_csv(csv_output) == [
                    tuple("" if value is None else str(value) for value in row) for row in book[sheet].values
                ]
        finally:
            book.close()
    header, *rows = read_csv(data)
    assert header.count("source_file") == 1
    assert [row[-1] for row in rows] == ["a.xlsx"] * 3 + ["b.xls"] * 2 + ["c.csv"] * 2


@pytest.mark.parametrize("filename", ["result", "result.csv", "result.XLSX"])
def test_both_requires_xlsx_suffix_before_writing(mixed_inputs, tmp_path, capsys, filename):
    out_dir = tmp_path / "out"
    assert main(["--input", str(mixed_inputs), "--output", str(out_dir / filename),
                 "--output-format", "both", "--log-file", str(out_dir / "run.log"), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "--output must end in .xlsx" in captured.err and "both" in captured.err
    assert not out_dir.exists()


@pytest.mark.parametrize("mode", ["xlsx", "csv", "both"])
def test_json_reports_exact_outputs_and_keeps_inputs_intact(mixed_inputs, tmp_path, capsys, mode):
    before = {path: sha256(path.read_bytes()).hexdigest() for path in mixed_inputs.iterdir()}
    primary = Path("out/result.csv" if mode == "csv" else "out/result.xlsx")
    outputs = {}
    if mode in {"xlsx", "both"}:
        outputs["xlsx"] = str(tmp_path / "out/result.xlsx")
    if mode in {"csv", "both"}:
        outputs["csv"] = str(tmp_path / "out/result.csv")
        outputs["report"] = str(tmp_path / "out/result_report.csv")
    log = tmp_path / "run.log"
    args = ["--input", str(mixed_inputs), "--output", str(primary), "--log-file", str(log)]
    if mode != "xlsx":
        args.extend(["--output-format", mode])
    assert main([*args, "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert len(captured.out.splitlines()) == 1 and captured.out.endswith("\n")
    warning = f"csv {mixed_inputs / 'c.csv'}: encoding=utf-8 delimiter=';'"
    assert json.loads(captured.out) == {
        "files": 3, "rows": 7, "output": str(tmp_path / primary), "outputs": outputs,
        "quality": {"nulls": 9, "duplicates": 0, "removed": 0, "changed": 0},
        "warnings": [warning],
    }
    assert set((tmp_path / "out").iterdir()) == {Path(path) for path in outputs.values()}
    logged = log.read_text(encoding="utf-8").splitlines()
    assert any(line.endswith(f"WARNING {warning}") for line in logged)
    for kind, path in outputs.items():
        assert f"{kind}={path}" in logged[-1]
    assert main(args) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        f"files: 3\nrows: 7\noutput: {tmp_path / primary}\n"
        "quality: nulls=9 duplicates=0 removed=0 changed=0\n"
    )
    both_runs = log.read_text(encoding="utf-8").splitlines()
    assert [line[20:] for line in logged] == [line[20:] for line in both_runs[len(logged):]]
    assert {path: sha256(path.read_bytes()).hexdigest() for path in mixed_inputs.iterdir()} == before


def test_json_error_has_empty_stdout_and_normal_stderr(tmp_path, capsys):
    assert main(["--input", str(tmp_path / "missing"), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: no .xlsx, .xls, .csv files in {tmp_path / 'missing'}\n"


@pytest.mark.parametrize("setting", ['"tsv"', '""', '"XLSX"', "7", "true", '["csv"]'])
def test_invalid_toml_output_format_is_configuration_error(tmp_path, capsys, setting):
    config = tmp_path / "config.toml"
    config.write_text(f"output_format = {setting}\n", encoding="utf-8")
    assert main(["--config", str(config), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: key 'output_format': expected ")
    assert not (tmp_path / "data").exists()


def test_invalid_cli_output_format_is_argument_error(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--output-format", "tsv", "--json"])
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--output-format: invalid choice: 'tsv'" in captured.err


def test_cli_output_format_uses_toml_and_explicit_override(tmp_path, make_xlsx):
    make_xlsx(tmp_path / "input" / "one.xlsx", [["A"], [1]])
    config = tmp_path / "run.toml"
    config.write_text(
        'input="input"\noutput="toml.data"\nlog_file="run.log"\noutput_format="csv"\n',
        encoding="utf-8",
    )
    assert main(["--config", str(config)]) == 0
    assert read_csv(tmp_path / "toml.data") == [("A", "source_file"), ("1", "one.xlsx")]
    assert (tmp_path / "toml_report.csv").is_file()
    assert main(["--config", str(config), "--output", "cli.data", "--output-format", "xlsx"]) == 0
    with (tmp_path / "cli.data").open("rb") as stream:
        book = load_workbook(stream)
        try:
            assert book.sheetnames == ["consolidated", "report"]
        finally:
            book.close()
    assert not (tmp_path / "cli_report.csv").exists()


@pytest.mark.parametrize("mode", ["csv", "both"])
def test_csv_report_write_failure_preserves_previous_set(mixed_inputs, tmp_path, monkeypatch, mode):
    primary = tmp_path / "out" / ("result.csv" if mode == "csv" else "result.xlsx")
    run(mixed_inputs, primary, output_format=mode)
    before = {path: path.read_bytes() for path in primary.parent.iterdir()}
    write_csv = writer._write_csv

    def fail_while_writing_report(frame, path):
        if frame.columns[0] == "section":
            path.write_bytes(b"\xef\xbb\xbfsection,file,")
            raise OSError("forced report write failure")
        write_csv(frame, path)

    def unexpected_replace(*args):
        pytest.fail("published an output before the report was ready")

    monkeypatch.setattr(writer, "_write_csv", fail_while_writing_report)
    monkeypatch.setattr(writer.os, "replace", unexpected_replace)
    with pytest.raises(ConsolidationError, match=r"result_report\.csv: forced report write failure"):
        run(mixed_inputs, primary, output_format=mode)
    assert {path: path.read_bytes() for path in primary.parent.iterdir()} == before


@pytest.mark.parametrize("previous_csv", [True, False])
def test_replace_failure_rolls_back_published_files(mixed_inputs, tmp_path, monkeypatch, previous_csv):
    primary = tmp_path / "out" / "result.xlsx"
    run(mixed_inputs, primary, output_format="both")
    if not previous_csv:
        primary.with_suffix(".csv").unlink()
    before = {path: path.read_bytes() for path in primary.parent.iterdir()}
    source_csv = mixed_inputs / "c.csv"
    source_csv.write_text(source_csv.read_text(encoding="utf-8").replace("Fay", "Hay"), encoding="utf-8")
    replace = writer.os.replace

    def fail_report_replace(source, destination):
        if destination.name == "result_report.csv":
            raise OSError("forced replacement failure")
        replace(source, destination)

    monkeypatch.setattr(writer.os, "replace", fail_report_replace)
    with pytest.raises(ConsolidationError, match=r"result_report\.csv: forced replacement failure"):
        run(mixed_inputs, primary, output_format="both")
    assert {path: path.read_bytes() for path in primary.parent.iterdir()} == before


@pytest.mark.parametrize("filename", ["c.xlsx", "a.xlsx"])
def test_both_protects_inputs_from_primary_and_derived_destinations(mixed_inputs, capsys, filename):
    before = {path: path.read_bytes() for path in mixed_inputs.iterdir()}
    assert main(["--input", str(mixed_inputs), "--output", str(mixed_inputs / filename),
                 "--output-format", "both"]) == 1
    assert "write destination conflicts with" in capsys.readouterr().err
    assert {path: path.read_bytes() for path in mixed_inputs.iterdir()} == before


@pytest.mark.parametrize(("output", "log"), [
    ("result.csv", "result_report.csv"), ("run.log.1", "run.log"),
])
def test_csv_output_cannot_overlap_log_or_rotation(mixed_inputs, tmp_path, capsys, output, log):
    directory = tmp_path / "out"
    assert main(["--input", str(mixed_inputs), "--output", str(directory / output),
                 "--output-format", "csv", "--log-file", str(directory / log)]) == 1
    assert "write destination conflicts with" in capsys.readouterr().err
    assert not directory.exists()


def test_gui_controller_loads_runs_and_logs_csv_mode(mixed_inputs, tmp_path, capsys):
    config_path = tmp_path / "run.toml"
    config_path.write_text(
        'input="inputs"\noutput="out/result.csv"\nlog_file="run.log"\noutput_format="csv"\n',
        encoding="utf-8",
    )
    config = load_config(config_path)
    fields = FormFields.from_config(config)
    assert fields.output_format == build_config(fields, config).output_format == "csv"
    outcome = run_from_fields(fields, config)
    assert outcome.ok and (outcome.files, outcome.rows) == (3, 7)
    assert outcome.report is not None
    report = config.output_path.with_name("result_report.csv")
    assert set(config.output_path.parent.iterdir()) == {config.output_path, report}
    assert f"csv={config.output_path} report={report}" in outcome.log_tail[-1]
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
