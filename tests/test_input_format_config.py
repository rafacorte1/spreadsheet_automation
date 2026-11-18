"""Exercise the new reader options through TOML, the CLI and the GUI controller."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import load_workbook

from excel_consolidator.cli import main
from excel_consolidator.config import load_config
from excel_consolidator.errors import ConsolidationError
from excel_consolidator.reader_options import ReaderOptions
from excel_consolidator.ui.controller import FormFields, build_config, run_from_fields


def test_toml_formats_and_csv_settings(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('formats = ["csv", "xls"]\n[csv]\nencoding = "latin-1"\ndelimiter = "\\t"\n',
                    encoding="utf-8")
    assert load_config(path).reader_options == ReaderOptions(("csv", "xls"), "latin-1", "\t")


@pytest.mark.parametrize(("toml", "message"), [
    ('[csv]\ncharset = "utf-8"\n', r"unknown keys: csv\.charset"),
    ("csv = 7\n", r"key 'csv': expected table"),
    ('formats = "csv"\n', r"key 'formats': expected list"),
    ('formats = ["csv", 7]\n', r"key 'formats': expected list"),
    ("formats = []\n", r"key 'formats': expected one or more"),
    ("[csv]\nencoding = false\n", r"key 'csv\.encoding': expected str"),
    ("[csv]\ndelimiter = 7\n", r"key 'csv\.delimiter': expected str"),
    ('[csv]\ndelimiter = "::"\n', r"key 'csv\.delimiter': expected a str of one character"),
])
def test_toml_rejects_invalid_reader_settings(tmp_path: Path, toml: str, message: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(toml, encoding="utf-8")
    with pytest.raises(ConsolidationError, match=message):
        load_config(path)


def test_invalid_format_is_argparse_exit_two(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--formats", "csv", "tsv"])
    assert caught.value.code == 2
    assert "invalid choice: 'tsv'" in capsys.readouterr().err


def test_invalid_toml_format_is_exit_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "config.toml"
    path.write_text('formats = ["tsv"]\n', encoding="utf-8")
    assert main(["--config", str(path)]) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert result.err.startswith("error: key 'formats':")
    assert "tsv" in result.err


def test_cli_csv_restriction_and_settings_override_toml(
    tmp_path: Path, make_xlsx, capsys: pytest.CaptureFixture[str],
) -> None:
    inputs = tmp_path / "input"
    make_xlsx(inputs / "ignored.xlsx", [["different"], [123]])
    csv = inputs / "data.csv"
    csv.write_text("A,B|City\nx,y|São\n", encoding="iso-8859-1")
    config = tmp_path / "run.toml"
    config.write_text(
        'input = "input"\noutput = "result.xlsx"\nlog_file = "run.log"\nformats = ["xlsx"]\n'
        '[csv]\nencoding = "ascii"\ndelimiter = ","\n',
        encoding="utf-8",
    )
    output = tmp_path / "result.xlsx"
    assert main(["--config", str(config), "--formats", "csv", "--csv-encoding", "iso-8859-1",
                 "--csv-delimiter", "|"]) == 0
    result = capsys.readouterr()
    assert result.out.splitlines() == [
        "files: 1", "rows: 1", f"output: {output}",
        "quality: nulls=0 duplicates=0 removed=0 changed=0",
    ]
    assert result.err == ""
    workbook = load_workbook(output, data_only=True)
    try:
        assert list(workbook["consolidated"].values) == [
            ("A,B", "City", "source_file"), ("x,y", "São", csv.name),
        ]
    finally:
        workbook.close()
    log = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "formats=csv csv_encoding=iso-8859-1 csv_delimiter='|'" in log
    assert "WARNING" not in log


def test_cli_uses_toml_options_without_overrides(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "ignore.xls").touch()
    (inputs / "export.csv").write_text("City\tNo.\nSão\t007\n", encoding="latin-1")
    path = tmp_path / "config.toml"
    path.write_text(
        'input = "inputs"\noutput = "result.xlsx"\nlog_file = "run.log"\nformats = ["csv"]\n'
        '[csv]\nencoding = "latin-1"\ndelimiter = "\\t"\n', encoding="utf-8",
    )
    assert main(["--config", str(path)]) == 0
    assert "formats=csv csv_encoding=latin-1 csv_delimiter='\\t'" in (
        tmp_path / "run.log"
    ).read_text(encoding="utf-8")


def test_cli_logs_automatic_csv_choices(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    csv = inputs / "legacy.csv"
    csv.write_text("City;No.\nSão;007\n", encoding="cp1252")
    log = tmp_path / "run.log"
    assert main(["--input", str(inputs), "--output", str(tmp_path / "result.xlsx"),
                 "--log-file", str(log)]) == 0
    result = capsys.readouterr()
    assert len(result.out.splitlines()) == 4
    assert result.err == ""
    assert f"WARNING csv {csv}: encoding=cp1252 delimiter=';'" in log.read_text(encoding="utf-8")


@pytest.mark.parametrize("flag", ["--output", "--log-file"])
def test_cli_refuses_to_use_a_csv_input_as_a_write_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flag: str,
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    csv = inputs / "input.csv"
    original = b"City,No.\nSao,007\n"
    csv.write_bytes(original)
    assert main(["--input", str(inputs), flag, str(csv)]) == 1
    result = capsys.readouterr()
    assert result.out == ""
    assert "write destination conflicts with" in result.err
    assert csv.read_bytes() == original
    assert list(inputs.iterdir()) == [csv]


def test_controller_roundtrips_reader_options_and_applies_them(tmp_path: Path) -> None:
    inputs = tmp_path / "input"
    inputs.mkdir()
    (inputs / "ignore.xls").touch()
    (inputs / "export.csv").write_text("City\tNo.\nSão\t007\n", encoding="latin-1")
    config_path = tmp_path / "gui.toml"
    config_path.write_text(
        'input = "input"\noutput = "out.xlsx"\nlog_file = "run.log"\nformats = ["csv"]\n'
        '[csv]\nencoding = "latin-1"\ndelimiter = "\\t"\n', encoding="utf-8",
    )
    config = load_config(config_path)
    fields = FormFields.from_config(config)
    assert (fields.formats, fields.csv_encoding, fields.csv_delimiter) == ("csv", "latin-1", r"\t")
    assert build_config(fields, config).reader_options == config.reader_options
    auto = replace(fields, csv_encoding="", csv_delimiter="")
    assert build_config(auto, config).reader_options == ReaderOptions(("csv",))
    outcome = run_from_fields(fields, config)
    assert outcome.ok and (outcome.rows, outcome.files) == (1, 1)
    assert outcome.warnings == ()
    assert "formats=csv csv_encoding=latin-1 csv_delimiter='\\t'" in outcome.log_tail[0]
