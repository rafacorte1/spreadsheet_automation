"""Independent verification of Sprint 3 (config, logs and importable core)."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)

base = Path(tempfile.mkdtemp(prefix="verify-s3-"))
proj = base / "proj"
(proj / "input").mkdir(parents=True)
other = base / "other_input"
other.mkdir()
fails: list[str] = []
total = 0


def check(name, cond, detail=None):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)
        if detail is not None:
            print("       got:", detail)


def make(path, rows):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    wb.save(path)
    wb.close()


make(proj / "input/a.xlsx", [["name", "amount"], ["  Ana  ", " 10 "], ["Bia", "20"]])
make(proj / "input/b.xlsx", [["amount", "name"], [" 30 ", "Caio"]])
make(other / "z.xlsx", [["name", "amount"], ["Zeca", "1"]])

(proj / "config.toml").write_text(
    'input = "input"\noutput = "output/consolidated.xlsx"\nlog_file = "logs/run.log"\n'
    '[quality]\ntrim_text = true\n', encoding="utf-8")

before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(proj.glob("input/*.xlsx"))}
out_file = proj / "output/consolidated.xlsx"
log_file = proj / "logs/run.log"


def run(args, cwd):
    return subprocess.run([str(PY), "-m", "excel_consolidator", *args], cwd=cwd,
                          capture_output=True, text=True)


print("=========== 1) --config from another directory ===========")
p = run(["--config", str(proj / "config.toml")], cwd=base)
print("exit:", p.returncode)
print(p.stdout.strip())
lines = p.stdout.strip().splitlines()
check("exit 0", p.returncode == 0, p.stderr)
check("4 stdout lines in the known format",
      lines[:2] == ["files: 2", "rows: 3"] and lines[2] == f"output: {out_file.resolve()}"
      and lines[3].startswith("quality: nulls="), lines)
check("output created relative to the config", out_file.is_file())
check("log created relative to the config", log_file.is_file())

wb = load_workbook(out_file, data_only=True)
data = [tuple(r) for r in wb["consolidated"].values]
wb.close()
check("trim from the config applied (numbers not normalised)",
      data[1] == ("Ana", "10", "a.xlsx"), data[1])
check("column order of the first file", data[0] == ("name", "amount", "source_file"), data[0])
check("3 data rows", len(data) == 4, len(data))

log1 = log_file.read_text(encoding="utf-8").splitlines()
print("log:", *log1, sep="\n  ")
check("log has 3 lines", len(log1) == 3, len(log1))
check("date format in the log", all(len(line.split(" ")[0]) == 10 and line[4] == "-" for line in log1))
check("first line records input, output and flags",
      "start input=" in log1[0] and "flags=trim_text" in log1[0] and "key=-" in log1[0], log1[0])
check("second line counts files and rows read",
      "read files=2 rows_read=3" in log1[1], log1[1])
check("third line has counters and the output",
      "written rows=3" in log1[2] and "changed=" in log1[2], log1[2])

print("\n=========== 2) CLI wins over the config ===========")
p2 = run(["--config", str(proj / "config.toml"), "--input", str(other),
          "--log-file", str(proj / "logs/other.log")], cwd=base)
print("exit:", p2.returncode)
print(p2.stdout.strip())
check("--input wins over the config", "files: 1" in p2.stdout and "rows: 1" in p2.stdout, p2.stdout)
check("alternative log created", (proj / "logs/other.log").is_file())
check("config log untouched in this run",
      len(log_file.read_text(encoding="utf-8").splitlines()) == 3)

print("\n=========== 3) the log appends without truncating ===========")
p3 = run(["--config", str(proj / "config.toml")], cwd=base)
log2 = log_file.read_text(encoding="utf-8").splitlines()
check("exit 0", p3.returncode == 0, p3.stderr)
check("log has 6 lines after 2 runs", len(log2) == 6, len(log2))
check("earlier lines preserved", log2[:3] == log1)

print("\n=========== 4) rotation ===========")
rot = base / "rot/run.log"
code = f"""
from pathlib import Path
import logging
from excel_consolidator.runlog import setup_logging, close_logging
log = setup_logging(Path({str(rot)!r}), max_bytes=300, backup_count=1)
for i in range(20):
    log.info("line %02d " + "x" * 40, i)
close_logging(log)
print(sorted(p.name for p in Path({str(rot.parent)!r}).iterdir()))
"""
p4 = subprocess.run([str(PY), "-c", code], cwd=ROOT, capture_output=True, text=True)
check("rotation creates the .1 backup", "run.log.1" in p4.stdout, p4.stdout + p4.stderr)
check("current log smaller than twice the rotation limit", rot.stat().st_size <= 300 * 2, rot.stat().st_size)

print("\n=========== 5) error after the log is open ===========")
hash_ok = hashlib.sha256(out_file.read_bytes()).hexdigest()
bad = proj / "input/c.xlsx"
bad.write_bytes(b"not an xlsx")
p5 = run(["--config", str(proj / "config.toml")], cwd=base)
print("exit:", p5.returncode, "| stderr:", p5.stderr.strip()[:120])
check("exit 1, empty stdout, error on stderr",
      p5.returncode == 1 and p5.stdout == "" and p5.stderr.startswith("error: "))
check("previous output intact", hashlib.sha256(out_file.read_bytes()).hexdigest() == hash_ok)
err_log = log_file.read_text(encoding="utf-8").splitlines()
check("error recorded in the log at ERROR level", "ERROR error=" in err_log[-1], err_log[-1])
check("log gained start plus ERROR (2 lines)", len(err_log) == 8, len(err_log))
check("start line written before the error", "start input=" in err_log[-2], err_log[-2])
bad.unlink()

print("\n=========== 6) missing --config ===========")
p6 = run(["--config", str(base / "missing.toml")], cwd=base)
print("exit:", p6.returncode, "| stderr:", p6.stderr.strip()[:120])
check("exit 1 and the path in the message", p6.returncode == 1 and "missing.toml" in p6.stderr)
check("no log created for an invalid config", not (base / "data").exists())

print("\n=========== 7) importable core (future UI) ===========")
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
print("stdout empty:", buf.getvalue() == "")
print("rows:", result.rows, "| files:", len(result.files))
print("file written:", Path({str(base / 'ui/out.xlsx')!r}).is_file())
"""
p7 = subprocess.run([str(PY), "-c", code], cwd=ROOT, capture_output=True, text=True)
print(p7.stdout.strip() or p7.stderr.strip())
check("run_config prints nothing", "stdout empty: True" in p7.stdout)
check("run_config writes the file and returns the result",
      "file written: True" in p7.stdout and "rows: 3" in p7.stdout)

print("\n=========== invariants ===========")
after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(proj.glob("input/*.xlsx"))}
check("inputs byte for byte unchanged", before == after)
check("no temporary file in the output",
      sorted(x.name for x in out_file.parent.iterdir()) == ["consolidated.xlsx"],
      [x.name for x in out_file.parent.iterdir()])

print("\nFAILURES:", fails if fails else "none", f"({len(fails)} of {total})")
shutil.rmtree(base)
