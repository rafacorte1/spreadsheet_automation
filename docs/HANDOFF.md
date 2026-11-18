# HANDOFF: Excel Consolidator

Restart document. Last updated 2026-11-18.

## What it is

A Python CLI and optional desktop GUI that consolidate `.xlsx`, legacy BIFF `.xls` and `.csv` inputs vertically into an `.xlsx` workbook. The tool keeps the origin of every row, optionally standardises values, writes a quality report and records runs in a rotating log.

- Repository: `git@github.com:rafacorte1/spreadsheet_automation.git` (public, branch `main`)
- Workflow: Product Owner (Rafael), then Hermes as Tech Lead and Scrum Master, then Codex CLI as implementer
- Governance: `SPEC.md` (scope and roadmap), `AGENTS.md` (roles and rules), `HERMES_MASTER_PROMPT.md` (per-increment workflow with an approval gate)

## Status

| Sprint | Scope | Status | Commit |
|---|---|---|---|
| 1 | reading, structural validation, atomic export | approved | `a4defda` |
| 2 | data quality: nulls, duplicates, standardisation, report | approved | `accf997` |
| 3 | TOML configuration plus rotating log (no scheduling) | approved | `06dc591` |
| 4 | customtkinter interface (Summary / Report / Log) | approved | `1b21f26` |
| | key validated only when used | approved | see `git log` |
| 5 | mixed `.xlsx`, `.xls` and `.csv` inputs with configurable CSV parsing | implemented, awaiting Product Owner approval | |
| | packaging (`.app`, double-click launcher) | deferred by the PO | |

Sprint 5 verification produced 230 passing tests and 4 window tests skipped on a headless machine. Three pre-existing tests changed. In `tests/test_reader.py` the discovery filter now passes `("xlsx",)` explicitly to retain its original expectation, and a separate mixed-input test exercises the new default. In `tests/test_cli.py` and `tests/test_consolidator.py` the empty-folder assertion now expects the message that names every enabled extension (`no .xlsx, .xls, .csv files in …`), because the previous text named one format while the default run looks for three.

Sample data in the repository: `data/input/branch_01.xlsx`, `branch_02.xlsx` and `branch_03.xlsx`, 7 rows in total, with `branch_02` using a different column order. Output goes to `data/output/consolidated.xlsx` and `data/output/consolidation.log`, both git-ignored.

## Architecture

```text
src/excel_consolidator/
  errors.py        ConsolidationError (displayable message, no traceback from the CLI)
  reader.py        ordered discovery, .xlsx reading and shared validation
  reader_options.py  frozen ReaderOptions for format selection and CSV settings
  csv_reader.py    decoding, delimiter selection and raw text records
  xls_reader.py    first BIFF worksheet, mapped cell types and cell errors
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

- **Reading `.xlsx` through openpyxl** exposes duplicate headers and blank cells directly. The common reader rejects both before pandas builds the DataFrame.
- **Reader options** travel from CLI or GUI through `RuntimeConfig.reader_options` and `run_config`. `ReaderOptions` is frozen and stores formats as a tuple. An unset CSV setting is represented by `None`, so specifying `utf-8` explicitly disables encoding fallback.
- **File discovery** uses a case-insensitive extension and sorts by the original file name. `--formats` takes space-separated names, TOML takes a nonempty list and the GUI takes comma-separated names. An empty input folder reports the enabled extensions, e.g. `no .xlsx, .xls, .csv files in …`, so the message never names a format the run was not looking for.
- **CSV detection and diagnostics** use the first 50 physical lines containing any content, then parse the sample with each candidate using Python's `csv` module. The consistent candidate with the most fields wins, with comma, semicolon, tab and pipe as the tie order. A single column or a sample with no qualifying delimiter falls back to comma. The full parse preserves quoted line breaks. Each automatic choice is recorded once per CSV in `SheetData.warnings`, aggregated into `ConsolidationResult.warnings` and logged by the CLI and GUI. With no BOM, a successful UTF-8 decode is logged as `utf-8`. Explicit decode errors report a zero-based byte offset.
- **Header width** uses the explicitly delimited fields of a CSV header. A trailing empty field there is a blank header. Excel readers may supply padding beyond the used headers, which is removed before validation.
- **GUI input fields** accept a comma-separated formats list and two CSV text entries. Blank formats means all three, blank CSV fields re-enable detection, and `\t` represents a tab delimiter. **From file** uses an input filter for Excel and CSV and fills in the selected file's parent folder. Consolidation still scans that folder. The output chooser is for Excel workbooks.
- **BIFF** uses xlrd at runtime. Synthetic `.xls` fixtures use xlwt from the dev extra. The reader converts BIFF dates using the workbook epoch and reports Excel error cells with one-based row and column numbers.
- **Literal header comparison**: no strip, no casefold, no accent removal. `"A"` is not `" A"` and is not `"a"`.
- **`dtype=object` on concatenation**: avoids `None` to `NaN` and numeric string to number conversion.
- **No silent transformation**: a value the rule cannot convert stays untouched and is counted as a failure. A failure is counted only when no conversion rule converted that cell.
- **Duplicates compare the data columns**: `source_file` is excluded, so an identical row in two different files is a duplicate. Removal keeps the first occurrence.
- **Long-format report** (`section, file, column, metric, value`): parseable and stable. Computed **before** duplicate removal.
- **Atomic output** uses a temporary file in the same directory and `os.replace`. A failure keeps the previous result and removes the temporary. Existing files selected as inputs are rejected as workbook or log destinations. The log also rejects an existing output workbook as its destination.
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

Sprint 5 was verified on Linux x86_64 with Python 3.14.9, pandas 3.1.1, openpyxl 3.1.5, pytest 9.2.0, customtkinter 6.0.0, xlrd 2.0.2 and xlwt 1.3.0. The previous macOS environment used Python 3.14.6 and Tk 9.0.

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

Restrict a run to CSV and provide an explicit separator and encoding for a known export.

```bash
.venv/bin/python -m excel_consolidator --input /path/to/exports --formats csv \
  --csv-encoding cp1252 --csv-delimiter ';' --normalize-numbers
```

Independent checks that build their own synthetic inputs:

```bash
.venv/bin/python docs/verification/verify-sprint1.py
.venv/bin/python docs/verification/verify-sprint2.py
.venv/bin/python docs/verification/verify-sprint3.py
```

## Sprint 5 benchmark

Generated 20 synthetic `.xlsx` files in a temporary directory using openpyxl in write-only mode. Each workbook contained a header and 5,000 data rows across five columns (`id`, `branch`, `amount`, `item`, `active`), for 100,000 data rows total.

```bash
/usr/bin/time -v -o "$bench/time.txt" .venv/bin/python -m excel_consolidator \
  --input "$bench/input" --output "$bench/output/consolidated.xlsx" \
  --log-file "$bench/output/run.log"
```

| Metric | Measured result |
|---|---:|
| Wall-clock time | 8.12 s |
| Peak resident memory | 336,448 KiB (328.6 MiB); an independent rerun measured 336,272 KiB |
| CLI exit status | 0 |
| Consolidated files and data rows | 20 files, 100,000 rows |

The recorded run used the default quality options and includes Python startup, input reading, report generation and workbook writing. Input generation and verification ran outside the timed command. Reopening the output confirmed the two worksheets, row count and first and last `source_file` values.

## Next steps (candidates, not approved)

1. A separate load test with representative large spreadsheets remains a candidate. The Sprint 5 benchmark used synthetic data.
2. Packaging (`.app`, double-click launcher) is deferred by the PO.
3. Output permissions: 600 is kept by PO decision; reopen only if another local account needs to read the report.

## Known pitfalls

- **Python 3.14 ignores a `.pth` file carrying the macOS `UF_HIDDEN` flag.** On the previous macOS environment, the editable install `.pth` acquired that flag and imports failed with `No module named excel_consolidator`. If that recurs on macOS, inspect the file with `ls -lO` and clear the flag with `chflags nohidden`.
- `data_only=True`: a cell with a formula and no cached value is read as empty.
- Excel's stored precision limits `.xls` numeric values. Integer conversion cannot restore rounded digits. BIFF readers also require actual Excel contents in an `.xls` file. HTML exports using the same suffix must be converted.
- CSV preserves text, including leading zeros, until a quality rule converts it. Set `--csv-delimiter` if a non-comma CSV has short rows in its detection sample, and use `--csv-encoding` for known encodings outside the UTF-8 and CP1252 fallback sequence. If reporting or duplicate detection should treat CSV numbers and dates like Excel values, enable the corresponding conversion rules.
- `--normalize-numbers` turns `"007"` into `7`, losing the leading zero. Do not use it on code columns.
- Unsupported notations become failures and the value stays untouched: `R$`, `(10)`, `1e5`, `1.23.456`, `05/11/26`.
- `--key` is literal and case sensitive: `name` does not match a column called `Name`. An unknown column is an error only with removal enabled; without it the key is ignored with a `WARNING` in the log.
- A fully empty trailing row is dropped by the reader (Sprint 1 rule); an empty row in the middle is preserved.
- `write_atomic(frame, output)` without a report writes one sheet; with a report it writes two (`consolidated`, `report`).
- Log rotation keeps only `consolidation.log.1`.
- Sprint 5 verification ran without a display. With a display available, `tests/test_ui_app.py` builds the window, runs consolidation and reads the widgets.
- GUI tests skip without a display (`pytest.importorskip` plus `TclError`). In CI without X or VNC they do not run; the controller tests do.

## Artifacts

- `docs/briefs/` contains the briefs through `sprint5-i-input-formats.md`.
- `docs/verification/`: independent verification scripts, with paths derived from the script location
