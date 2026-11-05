"""Verificação independente do Sprint 1: cenário realista + invariantes."""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

REPO = Path("/home/hermes/spreadsheet_automation")
PY = REPO / ".venv/bin/python"
root = Path(tempfile.mkdtemp(prefix="verif-s1-"))
inp = root / "data/input"
out = root / "data/output"
inp.mkdir(parents=True)
out.mkdir(parents=True)


def make(path: Path, rows, sheetname="Plan1"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheetname
    for r in rows:
        ws.append(r)
    wb.save(path)
    wb.close()


# 3 arquivos, ordens de coluna diferentes, tipos variados, acentos, None, data
make(inp / "a_clientes.xlsx", [
    ["Nome", "Cidade", "Valor", "Ativo", "Data"],
    ["José Ávila", "Limeira", 1500.5, True, dt.date(2026, 1, 5)],
    ["Ana", "Campinas", 0, False, dt.date(2026, 2, 10)],
    ["Bia", "Limeira", None, True, None],
])
make(inp / "b_clientes.xlsx", [
    ["Valor", "Nome", "Data", "Ativo", "Cidade"],
    [42, "Carlos", dt.date(2025, 12, 31), True, "Rio Claro"],
])
make(inp / "c_clientes.xlsx", [
    ["Ativo", "Cidade", "Valor", "Data", "Nome"],
    [False, "Araras", 7.25, None, "  espaco  "],
    [True, "Limeira", 3, dt.date(2026, 3, 1), "007"],
])
# ruído que deve ser ignorado
(inp / "~$a_clientes.xlsx").write_bytes(b"lock")
(inp / "notas.txt").write_text("ignore me")
(inp / "velho.xls").write_bytes(b"ignore me too")

before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}

proc = subprocess.run([str(PY), "-m", "excel_consolidator"],
                      cwd=root, capture_output=True, text=True)
print("=== execução 1 ===")
print("exit:", proc.returncode)
print("stdout:", proc.stdout.strip())
print("stderr:", proc.stderr.strip())

target = out / "consolidado.xlsx"
wb = load_workbook(target)
print("abas:", wb.sheetnames)
ws = wb.worksheets[0]
print("dimensões:", ws.dimensions, "| max_row:", ws.max_row, "| max_col:", ws.max_column)
rows = list(ws.values)
print("header:", rows[0])
for r in rows[1:]:
    print("  row:", r)
wb.close()

checks = []
checks.append(("1 aba", wb.sheetnames == ["consolidado"]))
checks.append(("header = ordem do 1º arquivo + arquivo_origem",
               list(rows[0]) == ["Nome", "Cidade", "Valor", "Ativo", "Data", "arquivo_origem"]))
checks.append(("6 linhas de dados", len(rows) - 1 == 6))
checks.append(("origem só nome do arquivo",
               [r[5] for r in rows[1:]] == ["a_clientes.xlsx"] * 3 + ["b_clientes.xlsx"] + ["c_clientes.xlsx"] * 2))
checks.append(("valor 1500.5 preservado", rows[1][2] == 1500.5))
checks.append(("None preservado como vazio", rows[3][2] is None and rows[3][4] is None))
checks.append(("bool preservado na ordem e nos valores",
               [r[3] for r in rows[1:]] == [True, False, True, True, False, True]))
checks.append(("data preservada", isinstance(rows[1][4], dt.datetime) and rows[1][4].date() == dt.date(2026, 1, 5)))
checks.append(("string com espaços não normalizada", rows[5][0] == "  espaco  "))
checks.append(("'007' continua texto", str(rows[6][0]) == "007"))
checks.append(("acentos intactos", rows[1][0] == "José Ávila"))

after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}
checks.append(("entradas byte a byte inalteradas", before == after))
checks.append(("nenhum temporário na saída", sorted(p.name for p in out.iterdir()) == ["consolidado.xlsx"]))

# ---- falha: entrada corrompida não pode tocar a saída anterior ----
hash_ok = hashlib.sha256(target.read_bytes()).hexdigest()
(inp / "d_ruim.xlsx").write_bytes(b"isto nao e um xlsx")
proc2 = subprocess.run([str(PY), "-m", "excel_consolidator"],
                       cwd=root, capture_output=True, text=True)
print("\n=== execução 2 (entrada corrompida) ===")
print("exit:", proc2.returncode)
print("stderr:", proc2.stderr.strip()[:200])
checks.append(("falha retorna != 0", proc2.returncode != 0))
checks.append(("saída anterior intacta", hashlib.sha256(target.read_bytes()).hexdigest() == hash_ok))
checks.append(("sem temporários após falha", sorted(p.name for p in out.iterdir()) == ["consolidado.xlsx"]))

# ---- falha: diretório vazio ----
vazio = root / "vazio"
vazio.mkdir()
proc3 = subprocess.run([str(PY), "-m", "excel_consolidator", "--input", str(vazio),
                        "--output", str(root / "out2/consolidado.xlsx")],
                       cwd=root, capture_output=True, text=True)
print("\n=== execução 3 (entrada vazia) ===")
print("exit:", proc3.returncode, "| stderr:", proc3.stderr.strip()[:120])
checks.append(("entrada vazia -> erro sem criar saída",
               proc3.returncode != 0 and not (root / "out2/consolidado.xlsx").exists()))

# ---- cabeçalhos incompatíveis ----
make(inp / "e_outro.xlsx", [["Outra", "Cidade"], ["x", "y"]])
os.remove(inp / "d_ruim.xlsx")
proc4 = subprocess.run([str(PY), "-m", "excel_consolidator"], cwd=root,
                       capture_output=True, text=True)
print("\n=== execução 4 (cabeçalho incompatível) ===")
print("exit:", proc4.returncode, "| stderr:", proc4.stderr.strip()[:200])
checks.append(("cabeçalho incompatível -> erro", proc4.returncode != 0 and "e_outro.xlsx" in proc4.stderr))
checks.append(("saída anterior intacta (2ª vez)",
               hashlib.sha256(target.read_bytes()).hexdigest() == hash_ok))

print("\n=== RESULTADO ===")
for name, ok in checks:
    print(("PASS " if ok else "FALHA ") + name)
print("\nfalhas:", sum(1 for _, ok in checks if not ok), "de", len(checks))
shutil.rmtree(root)
