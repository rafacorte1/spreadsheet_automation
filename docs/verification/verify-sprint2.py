"""Independent verification of Sprint 2: counters checked by hand."""
from __future__ import annotations

import datetime as dt
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

root = Path(tempfile.mkdtemp(prefix="verify-s2-"))
inp, out = root / "data/input", root / "data/output"
inp.mkdir(parents=True)
out.mkdir(parents=True)
fails: list[str] = []
total = 0


def make(path, rows):
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)
    wb.close()


# a: a row of nulls at the top (a fully empty trailing row would be dropped by Sprint 1)
make(inp / "a.xlsx", [["Name", "Amount", "Date"],
                      [None, "", None],
                      ["  Ana  ", "1.234,56", "05/11/2026"]])
make(inp / "b.xlsx", [["Date", "Amount", "Name"],
                      ["05/11/2026", "1.234,56", "Ana"]])
make(inp / "c.xlsx", [["Name", "Amount", "Date"],
                      ["Bia", 42, "2026-11-05"]])

before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}
target = out / "consolidated.xlsx"


def check(name, cond, detail=None):
    global total
    total += 1
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)
        if detail is not None:
            print("       got:", detail)


def run(*args):
    return subprocess.run([str(PY), "-m", "excel_consolidator", *args],
                          cwd=root, capture_output=True, text=True)


def read(path):
    wb = load_workbook(path, data_only=True)
    data = {"sheets": wb.sheetnames,
            "consolidated": [tuple(r) for r in wb["consolidated"].values],
            "report": [tuple(r) for r in wb["report"].values]}
    wb.close()
    return data


def output_files():
    return sorted(p.name for p in out.iterdir() if p.suffix != ".log" and not p.name.endswith(".log.1"))


print("=========== run 1: no flags ===========")
p1 = run()
print("exit:", p1.returncode)
print(p1.stdout.strip())
lines = p1.stdout.strip().splitlines()
check("exit 0", p1.returncode == 0, p1.stderr)
check("first three lines in the contract format",
      lines[:3] == ["files: 3", "rows: 4", f"output: {target.resolve()}"], lines[:3])
check("quality counters at zero without flags",
      lines[3] == "quality: nulls=3 duplicates=0 removed=0 changed=0", lines[3])

d1 = read(target)
check("sheets = [consolidated, report]", d1["sheets"] == ["consolidated", "report"], d1["sheets"])
check("raw data without trim", d1["consolidated"][2] == ("  Ana  ", "1.234,56", "05/11/2026", "a.xlsx"),
      d1["consolidated"][2])
check("row of nulls preserved", d1["consolidated"][1] == (None, None, None, "a.xlsx"),
      d1["consolidated"][1])
rel1 = d1["report"]
check("report has no standardization section", not any(r[0] == "standardization" for r in rel1))
res1 = [r for r in rel1 if r[3] == "rows_read"]
check("summary rows_read per file",
      res1 == [("summary", "a.xlsx", None, "rows_read", 2),
               ("summary", "b.xlsx", None, "rows_read", 1),
               ("summary", "c.xlsx", None, "rows_read", 1)], res1)
nul1 = [(r[1], r[2], r[4]) for r in rel1 if r[0] == "nulls"]
check("nulls per column and file",
      nul1 == [("a.xlsx", "Name", 1), ("a.xlsx", "Amount", 1), ("a.xlsx", "Date", 1),
               ("b.xlsx", "Date", 0), ("b.xlsx", "Amount", 0), ("b.xlsx", "Name", 0),
               ("c.xlsx", "Name", 0), ("c.xlsx", "Amount", 0), ("c.xlsx", "Date", 0)], nul1)
dup1 = [r for r in rel1 if r[0] == "duplicates"]
check("duplicates without a key: 0",
      dup1 == [("duplicates", None, None, "mode", "identical_rows"),
               ("duplicates", None, None, "duplicate_rows", 0),
               ("duplicates", None, None, "rows_removed", 0)], dup1)

print("\n=========== run 2: standardisation plus dedup by key ===========")
p2 = run("--trim-text", "--normalize-numbers", "--dates-iso",
         "--key", " Name ", "--remove-duplicates")
print("exit:", p2.returncode)
print(p2.stdout.strip())
l2 = p2.stdout.strip().splitlines()
check("exit 0", p2.returncode == 0, p2.stderr)
check("rows = 3 after removing 1 duplicate", l2[1] == "rows: 3", l2)
check("counters checked by hand",
      l2[3] == "quality: nulls=3 duplicates=1 removed=1 changed=6", l2[3])

d2 = read(target)
rows2 = d2["consolidated"]
check("header with origin last", rows2[0] == ("Name", "Amount", "Date", "source_file"), rows2[0])
check("row of nulls preserved at the top", rows2[1] == (None, None, None, "a.xlsx"), rows2[1])
check("trim, number and date applied, duplicate removed (first kept)",
      rows2[2] == ("Ana", 1234.56, dt.datetime(2026, 11, 5), "a.xlsx"), rows2[2])
check("types: name str, amount float",
      isinstance(rows2[2][0], str) and isinstance(rows2[2][1], float), rows2[2])
check("int 42 preserved and date converted",
      rows2[3] == ("Bia", 42, dt.datetime(2026, 11, 5), "c.xlsx"), rows2[3])

rel2 = d2["report"]
dup2 = [r for r in rel2 if r[0] == "duplicates"]
check("report mode with a key",
      dup2 == [("duplicates", None, None, "mode", "key:Name"),
               ("duplicates", None, None, "duplicate_rows", 1),
               ("duplicates", None, None, "rows_removed", 1)], dup2)
pad = [r for r in rel2 if r[0] == "standardization"]
check("standardization = 3 rules x 3 columns x 3 files x 2 metrics",
      len(pad) == 54, len(pad))
check("changed_trim_text on a.Name = 1",
      ("standardization", "a.xlsx", "Name", "changed_trim_text", 1) in pad)
check("changed_normalize_numbers on b.Amount = 1",
      ("standardization", "b.xlsx", "Amount", "changed_normalize_numbers", 1) in pad)
check("changed_dates_iso on c.Date = 1",
      ("standardization", "c.xlsx", "Date", "changed_dates_iso", 1) in pad)
check("failed_dates_iso on the three Name columns (Ana and Bia are not dates)",
      [(r[1], r[2], r[4]) for r in pad if r[3] == "failed_dates_iso" and r[4]]
      == [("a.xlsx", "Name", 1), ("b.xlsx", "Name", 1), ("c.xlsx", "Name", 1)],
      [(r[1], r[2], r[4]) for r in pad if r[3] == "failed_dates_iso" and r[4]])
check("changed counters sum to 6", sum(r[4] for r in pad if r[3].startswith("changed_")) == 6)

print("\n=========== run 3: unknown key ===========")
hash_ok = hashlib.sha256(target.read_bytes()).hexdigest()
p3 = run("--key", "Missing", "--remove-duplicates")
print("exit:", p3.returncode, "| stderr:", p3.stderr.strip()[:160])
check("with removal: exit 1, stderr with error and column name",
      p3.returncode == 1 and p3.stderr.startswith("error: ") and "Missing" in p3.stderr)
check("previous output intact", hashlib.sha256(target.read_bytes()).hexdigest() == hash_ok)
check("no temporary files", output_files() == ["consolidated.xlsx"], output_files())

print("\n=========== run 3b: unknown key without removal ===========")
p3b = run("--key", "Missing")
print("exit:", p3b.returncode)
print(p3b.stdout.strip())
check("without removal: exit 0 and the key is ignored",
      p3b.returncode == 0 and p3b.stderr == "", (p3b.returncode, p3b.stderr))
check("duplicates counted as identical_rows",
      "duplicates=0 removed=0" in p3b.stdout, p3b.stdout.strip())
wb3 = load_workbook(target, data_only=True)
mode3 = [r for r in wb3["report"].values if r[3] == "mode"]
wb3.close()
check("report mode identical_rows", mode3 == [("duplicates", None, None, "mode", "identical_rows")], mode3)

print("\n=========== run 4: valid key without removal ===========")
p4 = run("--trim-text", "--normalize-numbers", "--key", "Name")
print("exit:", p4.returncode)
print(p4.stdout.strip())
l4 = p4.stdout.strip().splitlines()
check("keeps 4 rows when removal is off", l4[1] == "rows: 4", l4)
check("detects 1 duplicate without removing and counts 3 changes",
      l4[3] == "quality: nulls=3 duplicates=1 removed=0 changed=3", l4[3])

print("\n=========== general invariants ===========")
after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inp.iterdir())}
check("inputs byte for byte unchanged", before == after)
check("no extra file in the output directory", output_files() == ["consolidated.xlsx"], output_files())

print("\nFAILURES:", fails if fails else "none", f"({len(fails)} of {total})")
shutil.rmtree(root)
