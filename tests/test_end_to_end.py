"""Real module execution with synthetic inputs in an isolated directory."""
from __future__ import annotations

import subprocess
import sys

from openpyxl import load_workbook


def test_module_defaults_and_previous_result_survives_corruption(tmp_path, make_xlsx):
    folder = tmp_path / "data" / "input"
    first = make_xlsx(folder / "a.xlsx", [["name", "amount"], ["Ana", 10], ["Bea", 20]])
    second = make_xlsx(folder / "b.xlsx", [["amount", "name"], [30, "Cara"]])
    before = {path: path.read_bytes() for path in (first, second)}
    output = tmp_path / "data" / "output" / "consolidated.xlsx"
    command = [sys.executable, "-m", "excel_consolidator"]
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == f"files: 2\nrows: 3\noutput: {output}\nquality: nulls=0 duplicates=0 removed=0 changed=0\n"
    assert completed.stderr == ""
    workbook = load_workbook(output, data_only=True)
    try:
        assert workbook.sheetnames == ["consolidated", "report"]
        assert list(workbook.active.values) == [
            ("name", "amount", "source_file"),
            ("Ana", 10, "a.xlsx"), ("Bea", 20, "a.xlsx"), ("Cara", 30, "b.xlsx"),
        ]
    finally:
        workbook.close()
    assert all(path.read_bytes() == content for path, content in before.items())
    previous_output = output.read_bytes()
    corrupt = folder / "c.xlsx"
    corrupt.write_bytes(b"corrupted input")
    failed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert failed.returncode == 1
    assert failed.stdout == ""
    assert failed.stderr.startswith("error: ")
    assert "c.xlsx" in failed.stderr
    assert "Traceback" not in failed.stderr
    assert output.read_bytes() == previous_output
    assert set(output.parent.iterdir()) == {output, output.parent / "consolidation.log"}
    assert corrupt.read_bytes() == b"corrupted input"
    assert all(path.read_bytes() == content for path, content in before.items())


def test_quality_workbook_and_second_run_without_flags(tmp_path, make_xlsx):
    folder = tmp_path / "input"
    first = make_xlsx(folder / "a.xlsx", [["name", "amount"], ["Ana", " 1.234,56 "], ["Bea", None]])
    second = make_xlsx(folder / "b.xlsx", [["name", "amount"], ["Ana", " 1.234,56 "]])
    before = {path: path.read_bytes() for path in (first, second)}
    output = tmp_path / "out.xlsx"
    command = [sys.executable, "-m", "excel_consolidator", "--input", str(folder), "--output", str(output)]
    run = subprocess.run(command + ["--trim-text", "--normalize-numbers", "--remove-duplicates"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout == f"files: 2\nrows: 2\noutput: {output}\nquality: nulls=1 duplicates=1 removed=1 changed=4\n"
    workbook = load_workbook(output, data_only=True)
    try:
        assert workbook.sheetnames == ["consolidated", "report"]
        assert list(workbook["consolidated"].values) == [("name", "amount", "source_file"), ("Ana", 1234.56, "a.xlsx"), ("Bea", None, "a.xlsx")]
        rows = list(workbook["report"].values)
        assert rows[0] == ("section", "file", "column", "metric", "value")
        assert rows[1:3] == [("summary", "a.xlsx", None, "rows_read", 2), ("summary", "b.xlsx", None, "rows_read", 1)]
        assert rows[-3:] == [("duplicates", None, None, "mode", "identical_rows"), ("duplicates", None, None, "duplicate_rows", 1), ("duplicates", None, None, "rows_removed", 1)]
        assert sum(row[4] for row in rows[1:] if row[0] == "nulls") == 1
        assert sum(row[4] for row in rows[1:] if row[3].startswith("changed_")) == 4
    finally:
        workbook.close()
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "rows: 3\n" in run.stdout
    workbook = load_workbook(output, data_only=True)
    try:
        assert list(workbook["consolidated"].values)[1:] == [("Ana", " 1.234,56 ", "a.xlsx"), ("Bea", None, "a.xlsx"), ("Ana", " 1.234,56 ", "b.xlsx")]
        assert not any(row[0] == "standardization" for row in workbook["report"].values)
    finally:
        workbook.close()
    assert all(path.read_bytes() == content for path, content in before.items())


def test_config_and_log_subprocess(tmp_path, make_xlsx):
    source = make_xlsx(tmp_path / 'input/a.xlsx', [['name'], [' Ana ']])
    before = source.read_bytes()
    config = tmp_path / 'settings.toml'
    config.write_text('input="input"\noutput="out.xlsx"\nlog_file="unused.log"\n[quality]\ntrim_text=true\n')
    log = tmp_path / 'logs/run.log'
    completed = subprocess.run([sys.executable, '-m', 'excel_consolidator', '--config', str(config), '--log-file', str(log)], cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ''
    assert completed.stdout == f'files: 1\nrows: 1\noutput: {tmp_path / "out.xlsx"}\nquality: nulls=0 duplicates=0 removed=0 changed=1\n'
    workbook = load_workbook(tmp_path / 'out.xlsx')
    try:
        assert workbook.sheetnames == ['consolidated', 'report']
        assert list(workbook['consolidated'].values) == [('name', 'source_file'), ('Ana', 'a.xlsx')]
        assert workbook['report']['A1'].value == 'section'
    finally:
        workbook.close()
    lines = log.read_text().splitlines()
    assert len(lines) == 3
    assert 'start input=' in lines[0]
    assert 'read files=1 rows_read=1' in lines[1]
    assert 'written rows=1' in lines[2]
    assert source.read_bytes() == before
    assert not (tmp_path / 'unused.log').exists()
