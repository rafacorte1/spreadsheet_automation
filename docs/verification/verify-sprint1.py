"""Independent verification of Sprint 1: realistic scenario plus invariants."""
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

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / ".venv" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)

root = Path(tempfile.mkdtemp(prefix="verify-s1-"))
inp = root / "data/input"
out = root / "data/output"
inp.mkdir(parents=True)
out.mkdir(parents=True)


def make(path: Path, rows, sheetname="Sheet1"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheetname
    for r in rows:
        ws.append(r)
    wb.save(path)
    wb.close()


# 3 files, different column orders, mixed types, accents, None, dates
make(inp / "a_clients.xlsx", [
    ["Name", "City", "Amount", "Active", "Date"],
    ["José Ávila", "Limeira", 1500.5, True, dt.date(2026, 1, 5)],
    ["Ana", "Campinas", 0, False, dt.date(2026, 2, 10)],
    ["Bia", "Limeira", None, True, None],
])
make(inp / "b_clients.xlsx", [
    ["Amount", "Name", "Date", "Active", "City"],
    [42, "Carlos", dt.date(2025, 12, 31), True, "Rio Claro"],
])
make(inp / "c_clients.xlsx", [
    ["Active", "City", "Amount", "Date", "Name"],
    [False, "Araras", 7.25, None, "  spaced  "],
    [True, "Limeira", 3, dt.date(2026, 3, 1), "007"],
])
# noise that must be ignored
(inp / "~$a_clients.xlsx").write_bytes(b"lock")
(inp / "notes.txt").write_text("ignore me")
(inp / "old.xls").write_bytes(b"ignore me too")

before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}

proc = subprocess.run([str(PY), "-m", "excel_consolidator"],
                      cwd=root, capture_output=True, text=True)
print("=== run 1 ===")
print("exit:", proc.returncode)
print("stdout:", proc.stdout.strip())
print("stderr:", proc.stderr.strip())

target = out / "consolidated.xlsx"
wb = load_workbook(target)
print("sheets:", wb.sheetnames)
ws = wb.worksheets[0]
print("dimensions:", ws.dimensions, "| max_row:", ws.max_row, "| max_col:", ws.max_column)
rows = list(ws.values)
print("header:", rows[0])
for r in rows[1:]:
    print("  row:", r)
wb.close()

checks = []
checks.append(("sheets are consolidated and report", wb.sheetnames == ["consolidated", "report"]))
checks.append(("header = first file order plus source_file",
               list(rows[0]) == ["Name", "City", "Amount", "Active", "Date", "source_file"]))
checks.append(("6 data rows", len(rows) - 1 == 6))
checks.append(("origin holds the file name only",
               [r[5] for r in rows[1:]] == ["a_clients.xlsx"] * 3 + ["b_clients.xlsx"] + ["c_clients.xlsx"] * 2))
checks.append(("1500.5 preserved", rows[1][2] == 1500.5))
checks.append(("None preserved as empty", rows[3][2] is None and rows[3][4] is None))
checks.append(("bool preserved in order and value",
               [r[3] for r in rows[1:]] == [True, False, True, True, False, True]))
checks.append(("date preserved", isinstance(rows[1][4], dt.datetime) and rows[1][4].date() == dt.date(2026, 1, 5)))
checks.append(("string with spaces not normalised", rows[5][0] == "  spaced  "))
checks.append(("'007' stays text", str(rows[6][0]) == "007"))
checks.append(("accents intact", rows[1][0] == "José Ávila"))

after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}
checks.append(("inputs byte for byte unchanged", before == after))
checks.append(("no temporary file in the output",
               sorted(p.name for p in out.iterdir() if not p.name.endswith(".log")) == ["consolidated.xlsx"]))

# ---- failure: a corrupted input must not touch the previous output ----
hash_ok = hashlib.sha256(target.read_bytes()).hexdigest()
(inp / "d_bad.xlsx").write_bytes(b"this is not an xlsx")
proc2 = subprocess.run([str(PY), "-m", "excel_consolidator"],
                       cwd=root, capture_output=True, text=True)
print("\n=== run 2 (corrupted input) ===")
print("exit:", proc2.returncode)
print("stderr:", proc2.stderr.strip()[:200])
checks.append(("failure returns non-zero", proc2.returncode != 0))
checks.append(("previous output intact", hashlib.sha256(target.read_bytes()).hexdigest() == hash_ok))
checks.append(("no temporary file after failure",
               sorted(p.name for p in out.iterdir() if not p.name.endswith(".log")) == ["consolidated.xlsx"]))

# ---- failure: empty directory ----
empty = root / "empty"
empty.mkdir()
proc3 = subprocess.run([str(PY), "-m", "excel_consolidator", "--input", str(empty),
                        "--output", str(root / "out2/consolidated.xlsx")],
                       cwd=root, capture_output=True, text=True)
print("\n=== run 3 (empty input) ===")
print("exit:", proc3.returncode, "| stderr:", proc3.stderr.strip()[:120])
checks.append(("empty input fails without creating output",
               proc3.returncode != 0 and not (root / "out2/consolidated.xlsx").exists()))

# ---- incompatible headers ----
make(inp / "e_other.xlsx", [["Other", "City"], ["x", "y"]])
os.remove(inp / "d_bad.xlsx")
proc4 = subprocess.run([str(PY), "-m", "excel_consolidator"], cwd=root,
                       capture_output=True, text=True)
print("\n=== run 4 (incompatible header) ===")
print("exit:", proc4.returncode, "| stderr:", proc4.stderr.strip()[:200])
checks.append(("incompatible header fails", proc4.returncode != 0 and "e_other.xlsx" in proc4.stderr))
checks.append(("previous output intact (second time)",
               hashlib.sha256(target.read_bytes()).hexdigest() == hash_ok))

print("\n=== RESULT ===")
for name, ok in checks:
    print(("PASS " if ok else "FAIL ") + name)
print("\nfailures:", sum(1 for _, ok in checks if not ok), "of", len(checks))
shutil.rmtree(root)
