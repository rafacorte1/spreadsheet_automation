# Codex spec: Sprint 1, Stage B (consolidation, atomic write, CLI, README)

Repo root. Stage A is approved: `reader.py` already provides `discover_input_files`, `read_sheet`, `validate_headers`, `SheetData`, `ORIGIN_COLUMN` and `ConsolidationError`. **Do not rewrite or weaken the reader API**; consume it.

GOAL: close Sprint 1. Consolidate the `.xlsx` files from `data/input` vertically, write `data/output/consolidated.xlsx` atomically and deliver the `python -m excel_consolidator` CLI, with acceptance tests and a README.

## DO NOT

- do not change `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- do not change the public signature of `reader.py` (minimal internal adjustments are allowed only if an acceptance test requires them; report it if it happens)
- no `git add`, `git commit` or `git push`
- no new dependency; do not create another virtualenv; do not install packages beyond what is already in `.venv`
- do not implement anything from Sprint 2 (normalisation, dedup, quality report) or Sprint 3 (configuration, logs, scheduling)
- do not hard-code test numbers or counts in production code

## DELIVERABLES

1) `src/excel_consolidator/consolidator.py`

```python
@dataclass(frozen=True)
class ConsolidationResult:
    files: tuple[SheetData, ...]
    frame: pd.DataFrame          # columns of the first file plus ORIGIN_COLUMN at the end
    @property
    def rows(self) -> int

def consolidate(input_dir: Path) -> ConsolidationResult
```

- `discover_input_files` returning an empty list raises `ConsolidationError("no .xlsx files in <dir>")`.
- Read every file with `read_sheet`; the **first** one in alphabetical order defines the column order; call `validate_headers` for all the others.
- Reorder each file's columns to the first file's order; concatenate vertically **without deduplicating**.
- Add `source_file` with **only the file name** (`path.name`), not the path.
- `frame` with `ignore_index=True`; keep the raw values (no type cast, no `None` conversion, no rounding). Order the columns so `source_file` is last.

2) `src/excel_consolidator/writer.py`

```python
def write_atomic(frame: pd.DataFrame, output_path: Path) -> None
```

- Create the output directory if missing (`parents=True, exist_ok=True`).
- Write first to a temporary file **in the same directory** as the destination (use `tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx")`), single sheet named `consolidated`, header on row 1, no pandas index.
- Only after the temporary file is closed and complete, `os.replace(temp, output_path)` (atomic replacement on the same filesystem).
- On any exception during the write, remove the temporary and re-raise as `ConsolidationError` naming `output_path`. A previous output file must stay byte for byte intact when the write fails.

3) `src/excel_consolidator/cli.py` plus `src/excel_consolidator/__main__.py`

```python
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidated.xlsx")

def build_parser() -> argparse.ArgumentParser
def run(input_dir: Path, output_path: Path) -> ConsolidationResult
def main(argv: Sequence[str] | None = None) -> int
```

- Flags: `--input DIR` (default `DEFAULT_INPUT`), `--output PATH` (default `DEFAULT_OUTPUT`).
- `main` returns `0` on success; on `ConsolidationError` it prints `error: <message>` on **stderr** and returns `1`; no traceback escapes. Argument errors remain argparse's (code 2).
- Success prints on stdout, exactly in this format:
  ```text
  files: <n>
  rows: <total>
  output: <absolute path of the generated file>
  ```
- `python -m excel_consolidator` calls `main()` and exits with the returned code (`raise SystemExit(main())`).

4) Tests under `tests/` (pytest, synthetic data in `tmp_path`):

- `tests/test_consolidator.py`: vertical concatenation with columns in different orders (all rows, first file's column order, `source_file` equal to the file name); deterministic alphabetical order; empty directory raises; `source_file` collision raises; no input file modified (compare bytes before and after).
- `tests/test_writer.py`: the generated file has one sheet, header on row 1 and the same cells and values as the frame; a missing output directory is created; no temporary `.xlsx` is left in the directory after success **and** after a forced failure (force it, for example with a frame that makes `os.replace` fail through monkeypatch, and confirm the previous destination content did not change).
- `tests/test_cli.py`: success prints the three lines in the format and returns 0; an input error returns 1, writes to stderr and **does not create or overwrite** the output; `--input` and `--output` are respected.
- `tests/test_end_to_end.py`: full scenario with 2 spreadsheets with swapped columns, producing `data/output/consolidated.xlsx` (under `tmp_path`) with the correct rows; and the "previous result stays intact" scenario: generate a valid output, run again with a corrupted input and confirm the previous file did not change byte for byte and the command failed with a non-zero code.

5) `README.md`: rewrite the file (today it has one line): what it does, requirements (Python >= 3.11), installation (`python -m venv .venv`, `pip install -e ".[dev]"`), folder structure, usage with `python -m excel_consolidator [--input DIR] [--output PATH]`, example output, how to run the tests (`.venv/bin/python -m pytest tests -q`), design decisions (reading through openpyxl to keep duplicate and blank headers detectable; literal header comparison; atomic write) and the **Sprint 1 limitations**: `.xlsx` and first sheet only, inputs with a formula and no cached value are read as empty (`data_only=True`), no `.xls` or `.csv`, no normalisation, no dedup, no value validation, no scheduling.

## ACCEPTANCE CRITERIA

- `source_file` contains only the file name.
- No row lost: output row count equals the sum of data rows across all input files.
- A failure at any step does not change the existing `data/output/consolidated.xlsx` and leaves no temporary files.
- Input files byte for byte unchanged.

## RULES

- Interpreter and tests: `.venv/bin/python -m pytest tests -q`
- `.venv/bin/python -m pip install -e . -q` if a reinstall is needed.
- Readable, typed code (`from __future__ import annotations`), short docstrings, named constants.
- **If a test fails, fix the code; never weaken the test.**
- At the end, paste the real pytest output and a real CLI run with synthetic data (including the resulting row count).
- Report: files created and changed, real commands, pytest output, CLI output.
