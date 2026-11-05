# HANDOFF: Excel Consolidator

Restart document. Last updated: 2026-11-05.

## What it is

A Python CLI that consolidates `.xlsx` spreadsheets from a folder vertically, keeps the origin of every row, and optionally standardises values, reports data quality, writes a rotating log and offers a desktop GUI.

- Repository: `git@github.com:rafacorte1/spreadsheet_automation.git` (public, branch `main`)
- Workflow: Product Owner (Rafael), then Hermes as Tech Lead and Scrum Master, then Codex CLI as implementer
- Governance: `SPEC.md` (scope and roadmap), `AGENTS.md` (roles and rules), `HERMES_MASTER_PROMPT.md` (per-increment workflow with an approval gate)

## Status

| Sprint | Scope | Status | Commit |
|---|---|---|---|
| 1 | reading, structural validation, atomic export | approved | `e0e5d36` |
| 2 | data quality: nulls, duplicates, standardisation, report | approved | `aed12bd` |
| 3 | TOML configuration plus rotating log (no scheduling) | approved | `d15a02e` |
| 4 | customtkinter interface (Summary / Report / Log) | approved | `343f06c` |
| | key validated only when used | approved | see `git log` |
| | packaging (`.app`, double-click launcher) | deferred by the PO | |

Suite: 182 pytest tests (153 earlier tests, 26 for the GUI and 3 for the key behaviour).

Sample data in the repository: `data/input/branch_01.xlsx`, `branch_02.xlsx` and `branch_03.xlsx`, 7 rows in total, with `branch_02` using a different column order. Output goes to `data/output/consolidated.xlsx` and `data/output/consolidation.log`, both git-ignored.

## Architecture

```text
src/excel_consolidator/
  errors.py        ConsolidationError (displayable message, no traceback from the CLI)
  reader.py        ordered discovery, first sheet, literal headers, raw rows
  quality.py       trim / pt-BR numbers / ISO dates, per-column and per-rule counters, duplicates
  report.py        long-format report sheet (section, file, column, metric, value)
  consolidator.py  concatenation, key validation, optional dedup, result plus report
  writer.py        two-sheet write with a temporary file in the destination plus os.replace
  config.py        optional config.toml, key and type validation, precedence CLI over file over default
  runlog.py        RotatingFileHandler (about 1 MB, 1 backup), no console handler
  cli.py           argparse, config merge, logs, four stdout lines, exit codes, run_config
  __main__.py      python -m excel_consolidator
  ui/controller.py fields to RuntimeConfig to run_config to RunOutcome (no tkinter)
  ui/app.py        customtkinter widgets, thread plus queue, 3 tabs
  ui/__main__.py   python -m excel_consolidator.ui
```

CLI contract, stdout on success:

```text
files: <n>
rows: <rows in the final output>
output: <absolute path>
quality: nulls=<X> duplicates=<Y> removed=<Z> changed=<W>
```

A consolidation or configuration error prints `error: <message>` on stderr with exit 1, no traceback, and leaves the previous output byte for byte intact. An invalid argument exits 2 through argparse.

## Decisions and reasons

- **Reading through openpyxl, not `pandas.read_excel`**: pandas renames duplicate headers (`id`, `id.1`) and turns an empty cell into `Unnamed: N`, which would hide two rejections the specification requires.
- **Literal header comparison**: no strip, no casefold, no accent removal. `"A"` is not `" A"` and is not `"a"`.
- **`dtype=object` on concatenation**: avoids `None` to `NaN` and numeric string to number conversion.
- **No silent transformation**: a value the rule cannot convert stays untouched and is counted as a failure. A failure is counted only when no conversion rule converted that cell.
- **Duplicates compare the data columns**: `source_file` is excluded, so an identical row in two different files is a duplicate. Removal keeps the first occurrence.
- **Long-format report** (`section, file, column, metric, value`): parseable and stable. Computed **before** duplicate removal.
- **Atomic output**: temporary file in the same directory plus `os.replace`; a failure keeps the previous result and removes the temporary.
- **TOML paths relative to the file itself**: running from another directory does not change the target. Defaults and CLI paths stay relative to the CWD.
- **No scheduling** (PO decision): recurring execution is done from the GUI, one run per click.
- **`run_config(RuntimeConfig)`**: the core entry point for the GUI, importable and silent (no print, no log setup, no `sys.exit`).
- **Tests isolated by CWD** (autouse fixture in `tests/conftest.py`): without it the suite writes to the production `data/output/consolidation.log`.
- **GUI with three tabs, Summary plus Report plus Log** (PO decision). The report is the product differentiator; hiding it behind "open spreadsheet" would lose the value.
- **GUI loads `config.toml` on open, with a Reload button** (PO decision). An invalid file shows the error and keeps the defaults instead of opening empty.
- **GUI writes the log file at the configured path** (PO decision): the same audit trail as the CLI, not a memory-only log.
- **Controller separated from tkinter**: `ui/controller.py` validates, runs and formats, so everything is testable without a window, and `ui/app.py` keeps only widgets.
- **Thread plus `queue.Queue` plus `after`**: the work runs outside the Tk thread and the result comes back by polling; a widget is never touched from another thread.
- **`customtkinter` as the `[ui]` extra**: the package stays installable and testable without a GUI.
- **Unexpected exception in the thread becomes an error `RunOutcome`**: the window does not die silently.
- **Mode 600 output is intentional** (PO decision): `mkstemp` creates the temporary at 0600 and `os.replace` preserves it. The report can contain sensitive data and the machine has a single user; 644 would only be needed if another local account had to read the file.
- **Key validated only when it is used** (PO decision): without `remove_duplicates`, an unknown key column does not stop the run. It becomes a `WARNING` in the log, the key is discarded (`options.key = ()`) and the report falls back to `identical_rows` mode. With removal enabled it is still an error. Reason: a stale key in `config.toml` used to kill a run that deduplicated nothing. An empty key is always rejected.

## Environment

macOS 26.6.2, Python 3.14.6 in `.venv`, tkinter 9.0, pandas 3.1.1, openpyxl 3.1.5, pytest 9.2.0, customtkinter 6.0.0. Codex CLI 0.166.0 is installed and authenticated; the last increment was implemented directly by Hermes and checked against the test suite, which is the accepted working mode for this project.

## How to run

```bash
git clone git@github.com:rafacorte1/spreadsheet_automation.git
cd spreadsheet_automation
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,ui]"
.venv/bin/python -m pytest tests -q
.venv/bin/python -m excel_consolidator --config config.example.toml
.venv/bin/python -m excel_consolidator.ui
```

Independent checks that build their own synthetic inputs:

```bash
.venv/bin/python docs/verification/verify-sprint1.py
.venv/bin/python docs/verification/verify-sprint2.py
.venv/bin/python docs/verification/verify-sprint3.py
```

## Next steps (candidates, not approved)

1. Load test with large real spreadsheets; the suite only uses small synthetic data.
2. Packaging (`.app`, double-click launcher) is deferred by the PO.
3. Output permissions: 600 is kept by PO decision; reopen only if another local account needs to read the report.

## Known pitfalls

- **Python 3.14 ignores a `.pth` file carrying the macOS `UF_HIDDEN` flag.** The editable install `.pth` from setuptools acquired that flag on this machine and imports started failing with `No module named excel_consolidator`, including in the tests. Applied workaround: a symlink `site-packages/excel_consolidator -> src/excel_consolidator` inside `.venv`, and the `.pth` removed. If `pip install -e .` recreates the `.pth`, check with `ls -lO` and remove it again (or run `chflags nohidden`).
- `data_only=True`: a cell with a formula and no cached value is read as empty.
- `--normalize-numbers` turns `"007"` into `7`, losing the leading zero. Do not use it on code columns.
- Unsupported notations become failures and the value stays untouched: `R$`, `(10)`, `1e5`, `1.23.456`, `05/11/26`.
- `--key` is literal and case sensitive: `name` does not match a column called `Name`. An unknown column is an error only with removal enabled; without it the key is ignored with a `WARNING` in the log.
- A fully empty trailing row is dropped by the reader (Sprint 1 rule); an empty row in the middle is preserved.
- `write_atomic(frame, output)` without a report writes one sheet; with a report it writes two (`consolidated`, `report`).
- Log rotation keeps only `consolidation.log.1`.
- Screen capture fails on this machine (`screencapture: could not create image from display`), so the window is verified by an automated test (`tests/test_ui_app.py` builds the App, runs it and reads the widgets), not by a screenshot.
- GUI tests skip without a display (`pytest.importorskip` plus `TclError`). In CI without X or VNC they do not run; the controller tests do.

## Artifacts

- `docs/briefs/`: the briefs each sprint was implemented against (sprint1-a to sprint4-g-ui)
- `docs/verification/`: independent verification scripts, with paths derived from the script location
