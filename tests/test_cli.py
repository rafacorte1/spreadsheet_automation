"""Acceptance of the CLI arguments, messages and exit codes."""
from __future__ import annotations

import pytest

from excel_consolidator.cli import DEFAULT_INPUT, DEFAULT_OUTPUT, build_parser, main


def test_success_with_custom_paths(tmp_path, make_xlsx, capsys):
    folder = tmp_path / "custom"
    make_xlsx(folder / "a.xlsx", [["A"], [1], [2]])
    output = tmp_path / "export" / "custom.xlsx"
    assert main(["--input", str(folder), "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"files: 1\nrows: 2\noutput: {output.resolve()}\nquality: nulls=0 duplicates=0 removed=0 changed=0\n"
    assert captured.err == ""
    assert output.is_file()


@pytest.mark.parametrize("existing", [False, True])
def test_input_error_preserves_output(tmp_path, capsys, existing):
    output = tmp_path / "result.xlsx"
    if existing:
        output.write_bytes(b"previous result")
    assert main(["--input", str(tmp_path / "missing"), "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: no .xlsx files in {tmp_path / 'missing'}\n"
    assert "Traceback" not in captured.err
    assert output.read_bytes() == b"previous result" if existing else not output.exists()


def test_defaults():
    args = build_parser().parse_args([])
    assert args.input is None
    assert args.output is None


def test_argument_error(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--unknown"])
    assert caught.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_quality_flags_and_final_rows(tmp_path, make_xlsx, capsys):
    from openpyxl import load_workbook
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A", "B"], [" x ", None], ["x", None]])
    output = tmp_path / "out.xlsx"
    assert main(["--input", str(folder), "--output", str(output), "--trim-text", "--remove-duplicates"]) == 0
    assert capsys.readouterr().out == f"files: 1\nrows: 1\noutput: {output}\nquality: nulls=2 duplicates=1 removed=1 changed=1\n"
    workbook = load_workbook(output)
    try:
        assert workbook["consolidated"]["A2"].value == "x"
    finally:
        workbook.close()


@pytest.mark.parametrize("key", ["", ","])
def test_empty_key_preserves_output(tmp_path, make_xlsx, capsys, key):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A"], [1]])
    output = tmp_path / "out.xlsx"
    output.write_bytes(b"previous")
    assert main(["--input", str(folder), "--output", str(output), "--key", key]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "key" in captured.err
    assert "Traceback" not in captured.err
    assert output.read_bytes() == b"previous"


@pytest.mark.parametrize("key", ["missing", "source_file"])
def test_unknown_key_without_removal_is_warned(tmp_path, make_xlsx, capsys, key):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A"], [1]])
    output = tmp_path / "out.xlsx"
    assert main(["--input", str(folder), "--output", str(output), "--key", key]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "rows: 1" in captured.out
    log = (tmp_path / "data/output/consolidation.log").read_text()
    assert "WARNING key" in log and "ignored" in log and "identical_rows" in log


def test_key_spaces_and_empty_entries(tmp_path, make_xlsx, capsys):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A", "B"], [1, "x"], [1, "y"]])
    assert main(["--input", str(folder), "--output", str(tmp_path / "out.xlsx"),
                 "--key", " , A, ,", "--remove-duplicates"]) == 0
    assert "rows: 1\n" in capsys.readouterr().out


def test_config_flags_and_overrides(tmp_path, make_xlsx, capsys):
    from openpyxl import load_workbook
    make_xlsx(tmp_path / 'input' / 'a.xlsx', [['A'], [' x '], ['x']])
    make_xlsx(tmp_path / 'other' / 'b.xlsx', [['A'], [' y ']])
    config = tmp_path / 'config.toml'
    config.write_text('input="input"\noutput="out.xlsx"\nlog_file="configured.log"\n[quality]\ntrim_text=true\nnormalize_numbers=true\ndates_iso=true\nremove_duplicates=true\nkey=["A"]\n')
    assert main(['--config', str(config)]) == 0
    assert capsys.readouterr().out == f'files: 1\nrows: 1\noutput: {tmp_path / "out.xlsx"}\nquality: nulls=0 duplicates=1 removed=1 changed=1\n'
    explicit = tmp_path / 'explicit.log'
    assert main(['--config', str(config), '--input', str(tmp_path / 'other'), '--log-file', str(explicit)]) == 0
    assert 'flags=trim_text,normalize_numbers,dates_iso,remove_duplicates key=A' in explicit.read_text()
    book = load_workbook(tmp_path / 'out.xlsx')
    try:
        assert book['consolidated']['A2'].value == 'y'
    finally:
        book.close()


@pytest.mark.parametrize('contents, message', [(None, 'missing.toml'), ('unknown=true', 'unknown')])
def test_config_error(tmp_path, capsys, contents, message):
    config = tmp_path / 'missing.toml'
    if contents is not None:
        config.write_text(contents)
    assert main(['--config', str(config), '--output', str(tmp_path / 'out.xlsx')]) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert message in captured.err
    assert not (tmp_path / 'out.xlsx').exists()


def test_default_config_and_error_log(tmp_path, make_xlsx, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    make_xlsx(tmp_path / 'data/input/a.xlsx', [['A'], [1]])
    assert main([]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 4
    log = tmp_path / 'data/output/consolidation.log'
    assert len(log.read_text().splitlines()) == 3
    assert main(['--input', 'missing']) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'ERROR error=' in log.read_text()
    assert 'missing' in captured.err


def test_unknown_key_without_removal_warns_in_log(tmp_path, make_xlsx, capsys):
    make_xlsx(tmp_path / 'input/a.xlsx', [['product'], ['Mouse']])
    assert main(['--input', str(tmp_path / 'input'), '--output', str(tmp_path / 'out.xlsx'),
                 '--key', 'date']) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert captured.out.splitlines() == [
        'files: 1', 'rows: 1', f'output: {(tmp_path / "out.xlsx").resolve()}',
        'quality: nulls=0 duplicates=0 removed=0 changed=0',
    ]
    log = (tmp_path / 'data/output/consolidation.log').read_text()
    assert "WARNING key ('date',) ignored" in log
    assert 'identical_rows' in log


def test_unknown_key_with_removal_fails(tmp_path, make_xlsx, capsys):
    make_xlsx(tmp_path / 'input/a.xlsx', [['product'], ['Mouse']])
    assert main(['--input', str(tmp_path / 'input'), '--output', str(tmp_path / 'out.xlsx'),
                 '--key', 'date', '--remove-duplicates']) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'unknown columns' in captured.err
    assert not (tmp_path / 'out.xlsx').exists()
