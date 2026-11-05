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
    assert completed.stdout == f"arquivos: 2\nlinhas: 3\nsaida: {output}\nqualidade: nulos=0 duplicados=0 removidos=0 alterados=0\n"
    assert completed.stderr == ""
    workbook = load_workbook(output, data_only=True)
    try:
        assert workbook.sheetnames == ["consolidado", "relatorio"]
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


def test_quality_workbook_and_second_run_without_flags(tmp_path, make_xlsx):
    folder = tmp_path / "input"
    first = make_xlsx(folder / "a.xlsx", [["nome", "valor"], ["Ana", " 1.234,56 "], ["Bia", None]])
    second = make_xlsx(folder / "b.xlsx", [["nome", "valor"], ["Ana", " 1.234,56 "]])
    before = {path: path.read_bytes() for path in (first, second)}
    output = tmp_path / "out.xlsx"
    command = [sys.executable, "-m", "excel_consolidator", "--input", str(folder), "--output", str(output)]
    run = subprocess.run(command + ["--trim-texto", "--normalizar-numeros", "--remover-duplicados"], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert run.stdout == f"arquivos: 2\nlinhas: 2\nsaida: {output}\nqualidade: nulos=1 duplicados=1 removidos=1 alterados=4\n"
    workbook = load_workbook(output, data_only=True)
    try:
        assert workbook.sheetnames == ["consolidado", "relatorio"]
        assert list(workbook["consolidado"].values) == [("nome", "valor", "arquivo_origem"), ("Ana", 1234.56, "a.xlsx"), ("Bia", None, "a.xlsx")]
        rows = list(workbook["relatorio"].values)
        assert rows[0] == ("secao", "arquivo", "coluna", "metrica", "valor")
        assert rows[1:3] == [("resumo", "a.xlsx", None, "linhas_lidas", 2), ("resumo", "b.xlsx", None, "linhas_lidas", 1)]
        assert rows[-3:] == [("duplicados", None, None, "modo", "linhas_identicas"), ("duplicados", None, None, "linhas_duplicadas", 1), ("duplicados", None, None, "linhas_removidas", 1)]
        assert sum(row[4] for row in rows[1:] if row[0] == "nulos") == 1
        assert sum(row[4] for row in rows[1:] if row[3].startswith("alterados_")) == 4
    finally:
        workbook.close()
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "linhas: 3\n" in run.stdout
    workbook = load_workbook(output, data_only=True)
    try:
        assert list(workbook["consolidado"].values)[1:] == [("Ana", " 1.234,56 ", "a.xlsx"), ("Bia", None, "a.xlsx"), ("Ana", " 1.234,56 ", "b.xlsx")]
        assert not any(row[0] == "padronizacao" for row in workbook["relatorio"].values)
    finally:
        workbook.close()
    assert all(path.read_bytes() == content for path, content in before.items())
