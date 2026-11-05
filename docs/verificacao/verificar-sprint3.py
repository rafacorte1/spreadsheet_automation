"""Verificação independente do Sprint 3 (config + logs + núcleo importável)."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

REPO = Path("/home/hermes/spreadsheet_automation")
PY = REPO / ".venv/bin/python"
base = Path(tempfile.mkdtemp(prefix="verif-s3-"))
proj = base / "proj"
(proj / "entrada").mkdir(parents=True)
other = base / "outra_entrada"
other.mkdir()
fails: list[str] = []


def check(name, cond, detail=None):
    print(("PASS  " if cond else "FALHA ") + name)
    if not cond:
        fails.append(name)
        if detail is not None:
            print("       obtido:", detail)


def make(path, rows):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(path)
    wb.close()


make(proj / "entrada/a.xlsx", [["nome", "valor"], ["  Ana  ", " 10 "], ["Bia", "20"]])
make(proj / "entrada/b.xlsx", [["valor", "nome"], [" 30 ", "Caio"]])
make(other / "z.xlsx", [["nome", "valor"], ["Zeca", "1"]])

(proj / "config.toml").write_text(
    'input = "entrada"\noutput = "saida/consolidado.xlsx"\nlog_file = "logs/run.log"\n'
    '[qualidade]\ntrim_texto = true\n', encoding="utf-8")

before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(proj.glob("entrada/*.xlsx"))}
out_file = proj / "saida/consolidado.xlsx"
log_file = proj / "logs/run.log"


def run(args, cwd):
    return subprocess.run([str(PY), "-m", "excel_consolidator", *args], cwd=cwd,
                          capture_output=True, text=True)


print("=========== 1) --config de outro diretório ===========")
p = run(["--config", str(proj / "config.toml")], cwd=base)
print("exit:", p.returncode)
print(p.stdout.strip())
lines = p.stdout.strip().splitlines()
check("exit 0", p.returncode == 0, p.stderr)
check("4 linhas de stdout no formato conhecido",
      lines[:2] == ["arquivos: 2", "linhas: 3"] and lines[2] == f"saida: {out_file.resolve()}"
      and lines[3].startswith("qualidade: nulos="), lines)
check("saída criada relativa ao config", out_file.is_file())
check("log criado relativo ao config", log_file.is_file())

wb = load_workbook(out_file, data_only=True)
data = [tuple(r) for r in wb["consolidado"].values]
wb.close()
check("trim do config aplicado (sem normalizar números)",
      data[1] == ("Ana", "10", "a.xlsx"), data[1])
check("ordem de colunas do primeiro arquivo", data[0] == ("nome", "valor", "arquivo_origem"), data[0])
check("3 linhas de dados", len(data) == 4, len(data))

log1 = log_file.read_text(encoding="utf-8").splitlines()
print("log:", *log1, sep="\n  ")
check("log com 3 linhas", len(log1) == 3, len(log1))
check("formato de data no log", all(len(l.split(" ")[0]) == 10 and l[4] == "-" for l in log1))
check("primeira linha registra input/output/flags",
      "inicio input=" in log1[0] and "flags=trim_texto" in log1[0] and "chave=-" in log1[0], log1[0])
check("segunda linha conta arquivos e linhas lidas",
      "leitura arquivos=2 linhas_lidas=3" in log1[1], log1[1])
check("terceira linha tem contadores e saída",
      "gravado linhas=3" in log1[2] and "alterados=" in log1[2], log1[2])

print("\n=========== 2) CLI vence o config ===========")
p2 = run(["--config", str(proj / "config.toml"), "--input", str(other),
          "--log-file", str(proj / "logs/outro.log")], cwd=base)
print("exit:", p2.returncode)
print(p2.stdout.strip())
check("--input vence o config", "arquivos: 1" in p2.stdout and "linhas: 1" in p2.stdout, p2.stdout)
check("log alternativo criado", (proj / "logs/outro.log").is_file())
check("log do config não foi tocado nesta execução",
      len(log_file.read_text(encoding="utf-8").splitlines()) == 3)

print("\n=========== 3) log acrescenta sem truncar ===========")
p3 = run(["--config", str(proj / "config.toml")], cwd=base)
log2 = log_file.read_text(encoding="utf-8").splitlines()
check("exit 0", p3.returncode == 0, p3.stderr)
check("log com 6 linhas após 2 execuções", len(log2) == 6, len(log2))
check("linhas antigas preservadas", log2[:3] == log1)

print("\n=========== 4) rotação ===========")
rot = base / "rot/run.log"
code = f"""
from pathlib import Path
import logging
from excel_consolidator.runlog import setup_logging, close_logging
log = setup_logging(Path({str(rot)!r}), max_bytes=300, backup_count=1)
for i in range(20):
    log.info("linha %02d " + "x" * 40, i)
close_logging(log)
print(sorted(p.name for p in Path({str(rot.parent)!r}).iterdir()))
"""
p4 = subprocess.run([str(PY), "-c", code], cwd=REPO, capture_output=True, text=True)
check("rotação gera backup .1", "run.log.1" in p4.stdout, p4.stdout + p4.stderr)
check("log atual menor que o limite de rotação", rot.stat().st_size <= 300 * 2, rot.stat().st_size)

print("\n=========== 5) erro depois do log aberto ===========")
hash_ok = hashlib.sha256(out_file.read_bytes()).hexdigest()
bad = proj / "entrada/c.xlsx"
bad.write_bytes(b"nao e xlsx")
p5 = run(["--config", str(proj / "config.toml")], cwd=base)
print("exit:", p5.returncode, "| stderr:", p5.stderr.strip()[:120])
check("exit 1, stdout vazio, stderr com erro",
      p5.returncode == 1 and p5.stdout == "" and p5.stderr.startswith("erro: "))
check("saída anterior intacta", hashlib.sha256(out_file.read_bytes()).hexdigest() == hash_ok)
err_log = log_file.read_text(encoding="utf-8").splitlines()
check("erro registrado no log com nível ERROR", "ERROR erro=" in err_log[-1], err_log[-1])
check("log ganhou inicio + ERROR (2 linhas)", len(err_log) == 8, len(err_log))
check("linha de inicio registrada antes do erro", "inicio input=" in err_log[-2], err_log[-2])
bad.unlink()

print("\n=========== 6) --config inexistente ===========")
p6 = run(["--config", str(base / "nao_existe.toml")], cwd=base)
print("exit:", p6.returncode, "| stderr:", p6.stderr.strip()[:120])
check("exit 1 e mensagem com o caminho", p6.returncode == 1 and "nao_existe.toml" in p6.stderr)
check("nenhum log criado para config inválido", not (base / "data").exists())

print("\n=========== 7) núcleo importável (futura UI) ===========")
code = f"""
import io, contextlib
from pathlib import Path
from excel_consolidator.config import load_config, apply_overrides
from excel_consolidator.cli import run_config
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    cfg = apply_overrides(load_config(Path({str(proj / 'config.toml')!r})),
                          output_path=Path({str(base / 'ui/out.xlsx')!r}),
                          log_file=Path({str(base / 'ui/run.log')!r}))
    result = run_config(cfg)
print("stdout vazio:", buf.getvalue() == "")
print("linhas:", result.rows, "| arquivos:", len(result.files))
print("arquivo:", Path({str(base / 'ui/out.xlsx')!r}).is_file())
"""
p7 = subprocess.run([str(PY), "-c", code], cwd=REPO, capture_output=True, text=True)
print(p7.stdout.strip() or p7.stderr.strip())
check("run_config não imprime nada", "stdout vazio: True" in p7.stdout)
check("run_config grava o arquivo e devolve o resultado",
      "arquivo: True" in p7.stdout and "linhas: 3" in p7.stdout)

print("\n=========== invariantes ===========")
after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(proj.glob("entrada/*.xlsx"))}
check("entradas byte a byte inalteradas", before == after)
check("nenhum temporário nas saídas", sorted(x.name for x in out_file.parent.iterdir()) == ["consolidado.xlsx"],
      [x.name for x in out_file.parent.iterdir()])

print("\nFALHAS:", fails if fails else "nenhuma", f"({len(fails)})")
shutil.rmtree(base)
