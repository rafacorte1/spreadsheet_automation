"""Execução real do módulo com entradas sintéticas e diretório isolado."""
from __future__ import annotations

import subprocess
import sys

from openpyxl import load_workbook


def test_module_defaults_and_previous_result_survives_corruption(tmp_path, make_xlsx):
    folder = tmp_path / "data" / "input"
    first = make_xlsx(folder / "a.xlsx", [["nome", "valor"], ["Ana", 10], ["Bia", 20]])
    second = make_xlsx(folder / "b.xlsx", [["valor", "nome"], [30, "Caio"]])
    before = {path: path.read_bytes() for path in (first, second)}
    output = tmp_path / "data" / "output" / "consolidado.xlsx"
    command = [sys.executable, "-m", "excel_consolidator"]
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == f"arquivos: 2\nlinhas: 3\nsaida: {output}\n"
    assert completed.stderr == ""
    workbook = load_workbook(output, data_only=True)
    try:
        assert workbook.sheetnames == ["consolidado"]
        assert list(workbook.active.values) == [
            ("nome", "valor", "arquivo_origem"),
            ("Ana", 10, "a.xlsx"), ("Bia", 20, "a.xlsx"), ("Caio", 30, "b.xlsx"),
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
    assert failed.stderr.startswith("erro: ")
    assert "c.xlsx" in failed.stderr
    assert "Traceback" not in failed.stderr
    assert output.read_bytes() == previous_output
    assert list(output.parent.iterdir()) == [output]
    assert corrupt.read_bytes() == b"corrupted input"
    assert all(path.read_bytes() == content for path, content in before.items())
