"""Verificação independente do Sprint 2: números conferidos na mão."""
from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

PY = Path("/home/hermes/spreadsheet_automation/.venv/bin/python")
root = Path(tempfile.mkdtemp(prefix="verif-s2-"))
inp, out = root / "data/input", root / "data/output"
inp.mkdir(parents=True)
out.mkdir(parents=True)
fails: list[str] = []


def make(path, rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)
    wb.close()


# a: linha de nulos no topo (linha final totalmente vazia seria descartada pelo Sprint 1)
make(inp / "a.xlsx", [["Nome", "Valor", "Data"],
                      [None, "", None],
                      ["  Ana  ", "1.234,56", "05/11/2026"]])
make(inp / "b.xlsx", [["Data", "Valor", "Nome"],
                      ["05/11/2026", "1.234,56", "Ana"]])
make(inp / "c.xlsx", [["Nome", "Valor", "Data"],
                      ["Bia", 42, "2026-11-05"]])

before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}
target = out / "consolidado.xlsx"


def check(name, cond, detail=None):
    print(("PASS  " if cond else "FALHA ") + name)
    if not cond:
        fails.append(name)
        if detail is not None:
            print("       obtido:", detail)


def run(*args):
    return subprocess.run([str(PY), "-m", "excel_consolidator", *args],
                          cwd=root, capture_output=True, text=True)


def read(path):
    wb = load_workbook(path, data_only=True)
    data = {"sheets": wb.sheetnames,
            "consolidado": [tuple(r) for r in wb["consolidado"].values],
            "relatorio": [tuple(r) for r in wb["relatorio"].values]}
    wb.close()
    return data


print("=========== execução 1: sem flags ===========")
p1 = run()
print("exit:", p1.returncode)
print(p1.stdout.strip())
lines = p1.stdout.strip().splitlines()
check("exit 0", p1.returncode == 0)
check("3 primeiras linhas do formato do Sprint 1",
      lines[:3] == ["arquivos: 3", "linhas: 4", f"saida: {target.resolve()}"], lines[:3])
check("qualidade zerada sem flags",
      lines[3] == "qualidade: nulos=3 duplicados=0 removidos=0 alterados=0", lines[3])

d1 = read(target)
check("abas = [consolidado, relatorio]", d1["sheets"] == ["consolidado", "relatorio"], d1["sheets"])
check("dado bruto sem trim", d1["consolidado"][2] == ("  Ana  ", "1.234,56", "05/11/2026", "a.xlsx"),
      d1["consolidado"][2])
check("linha de nulos preservada", d1["consolidado"][1] == (None, None, None, "a.xlsx"),
      d1["consolidado"][1])
rel1 = d1["relatorio"]
check("relatorio sem seção de padronizacao", not any(r[0] == "padronizacao" for r in rel1))
res1 = [r for r in rel1 if r[3] == "linhas_lidas"]
check("resumo linhas_lidas por arquivo",
      res1 == [("resumo", "a.xlsx", None, "linhas_lidas", 2),
               ("resumo", "b.xlsx", None, "linhas_lidas", 1),
               ("resumo", "c.xlsx", None, "linhas_lidas", 1)], res1)
nul1 = [(r[1], r[2], r[4]) for r in rel1 if r[0] == "nulos"]
check("nulos por coluna e arquivo",
      nul1 == [("a.xlsx", "Nome", 1), ("a.xlsx", "Valor", 1), ("a.xlsx", "Data", 1),
               ("b.xlsx", "Data", 0), ("b.xlsx", "Valor", 0), ("b.xlsx", "Nome", 0),
               ("c.xlsx", "Nome", 0), ("c.xlsx", "Valor", 0), ("c.xlsx", "Data", 0)], nul1)
dup1 = [r for r in rel1 if r[0] == "duplicados"]
check("duplicados sem chave: 0",
      dup1 == [("duplicados", None, None, "modo", "linhas_identicas"),
               ("duplicados", None, None, "linhas_duplicadas", 0),
               ("duplicados", None, None, "linhas_removidas", 0)], dup1)

print("\n=========== execução 2: padronização + dedup por chave ===========")
p2 = run("--trim-texto", "--normalizar-numeros", "--datas-iso",
         "--chave", " Nome ", "--remover-duplicados")
print("exit:", p2.returncode)
print(p2.stdout.strip())
l2 = p2.stdout.strip().splitlines()
check("exit 0", p2.returncode == 0, p2.stderr)
check("linhas = 3 após remover 1 duplicado", l2[1] == "linhas: 3", l2)
check("contadores conferidos na mão",
      l2[3] == "qualidade: nulos=3 duplicados=1 removidos=1 alterados=6", l2[3])

d2 = read(target)
rows2 = d2["consolidado"]
check("cabeçalho com origem ao final", rows2[0] == ("Nome", "Valor", "Data", "arquivo_origem"), rows2[0])
check("linha de nulos preservada no topo", rows2[1] == (None, None, None, "a.xlsx"), rows2[1])
check("trim + número + data aplicados, duplicado removido (fica o 1º)",
      rows2[2] == ("Ana", 1234.56, dt.datetime(2026, 11, 5), "a.xlsx"), rows2[2])
check("tipos: nome str, valor float",
      isinstance(rows2[2][0], str) and isinstance(rows2[2][1], float), rows2[2])
check("int 42 preservado e data convertida",
      rows2[3] == ("Bia", 42, dt.datetime(2026, 11, 5), "c.xlsx"), rows2[3])

rel2 = d2["relatorio"]
dup2 = [r for r in rel2 if r[0] == "duplicados"]
check("modo do relatório com chave",
      dup2 == [("duplicados", None, None, "modo", "chave:Nome"),
               ("duplicados", None, None, "linhas_duplicadas", 1),
               ("duplicados", None, None, "linhas_removidas", 1)], dup2)
pad = [r for r in rel2 if r[0] == "padronizacao"]
check("padronizacao = 3 regras x 3 colunas x 3 arquivos x 2 métricas",
      len(pad) == 54, len(pad))
check("alterados_trim_texto em a.Nome = 1",
      ("padronizacao", "a.xlsx", "Nome", "alterados_trim_texto", 1) in pad)
check("alterados_normalizar_numeros em b.Valor = 1",
      ("padronizacao", "b.xlsx", "Valor", "alterados_normalizar_numeros", 1) in pad)
check("alterados_datas_iso em c.Data = 1",
      ("padronizacao", "c.xlsx", "Data", "alterados_datas_iso", 1) in pad)
check("falhas_datas_iso nas três colunas Nome (Ana/Bia não são data)",
      [(r[1], r[2], r[4]) for r in pad if r[3] == "falhas_datas_iso" and r[4]]
      == [("a.xlsx", "Nome", 1), ("b.xlsx", "Nome", 1), ("c.xlsx", "Nome", 1)],
      [(r[1], r[2], r[4]) for r in pad if r[3] == "falhas_datas_iso" and r[4]])
check("alterados somam 6", sum(r[4] for r in pad if r[3].startswith("alterados_")) == 6)

print("\n=========== execução 3: chave inexistente ===========")
hash_ok = hashlib.sha256(target.read_bytes()).hexdigest()
p3 = run("--chave", "Inexistente")
print("exit:", p3.returncode, "| stderr:", p3.stderr.strip()[:160])
check("exit 1, stderr com erro e nome da coluna",
      p3.returncode == 1 and p3.stderr.startswith("erro: ") and "Inexistente" in p3.stderr)
check("saída anterior intacta", hashlib.sha256(target.read_bytes()).hexdigest() == hash_ok)
check("sem temporários", sorted(p.name for p in out.iterdir()) == ["consolidado.xlsx"])

print("\n=========== execução 4: chave sem remoção ===========")
p4 = run("--trim-texto", "--normalizar-numeros", "--chave", "Nome")
print("exit:", p4.returncode)
print(p4.stdout.strip())
l4 = p4.stdout.strip().splitlines()
check("mantém 4 linhas quando não remove", l4[1] == "linhas: 4", l4)
check("detecta 1 duplicado sem remover (com trim) e conta 3 alterações",
      l4[3] == "qualidade: nulos=3 duplicados=1 removidos=0 alterados=3", l4[3])

print("\n=========== invariantes gerais ===========")
after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}
check("entradas byte a byte inalteradas", before == after)
check("nenhum arquivo extra na saída", sorted(p.name for p in out.iterdir()) == ["consolidado.xlsx"])

print("\nFALHAS:", fails if fails else "nenhuma", f"({len(fails)})")
shutil.rmtree(root)
