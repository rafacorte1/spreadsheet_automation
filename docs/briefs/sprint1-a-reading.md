# Codex spec: Sprint 1, Stage A (skeleton plus reading and validation)

Repo root, branch `main`. Work from the repository root.

GOAL: deliver the skeleton of the `excel_consolidator` package and the `.xlsx` reading and validation layer, with passing pytest tests. Do NOT implement consolidation, output writing or the CLI in this stage (stage B handles those).

## DO NOT

- do not create `consolidator.py`, `writer.py` or `cli.py`; do not write anything into `data/output/`
- do not modify `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `README.md`
- no `git add`, `git commit` or `git push`
- no new dependency (use the pandas, openpyxl and pytest already in `.venv`)
- do not create another virtualenv, do not install packages

## MANDATORY CONTEXT (read first)

- `SPEC.md`, Sprint 1 requirements 1, 2, 3 and 5 (file discovery, first sheet, header validation, `source_file` collision) and items 8 and 9 (controlled errors, do not modify input).
- Interpreter: `.venv/bin/python` (Python 3.14, pandas 3.1.1, openpyxl 3.1.5, pytest 9.2.0).

## DELIVERABLES

1) `pyproject.toml`: setuptools, `name = "excel-consolidator"`, `requires-python = ">=3.11"`, dependencies `pandas` and `openpyxl`; `dev` extra with `pytest`; `src/` layout; package `excel_consolidator`; **no** console script yet.

2) `src/excel_consolidator/__init__.py`: exports `ConsolidationError`.

3) `src/excel_consolidator/errors.py`:

```python
class ConsolidationError(Exception):
    """Input or validation error with a message the user can read."""
```

4) `src/excel_consolidator/reader.py`: exact public API:

```python
ORIGIN_COLUMN: str = "source_file"
HEADER_REJECTED_SUFFIX: str = ".xlsx"

@dataclass(frozen=True)
class SheetData:
    path: Path
    columns: tuple[str, ...]      # header in file order
    rows: tuple[tuple[object, ...], ...]  # data rows only, len == len(columns)

def discover_input_files(input_dir: Path) -> list[Path]
def read_sheet(path: Path) -> SheetData
def validate_headers(reference: SheetData, candidate: SheetData) -> None
```

Mandatory behaviour:

- `discover_input_files`: `*.xlsx` files **directly** in `input_dir`, no recursion; ignore names starting with `~$`; ignore directories; return in deterministic alphabetical order by file name (`sorted(..., key=lambda p: p.name)`); a missing or empty directory returns `[]` without raising (stage B handles absence).
- `read_sheet`: reads **only the first sheet** through `openpyxl.load_workbook(path, read_only=True, data_only=True)` (use `values_only=True` to iterate). Every header and cell is treated as raw openpyxl data.
- Header: the first non-empty row of the sheet. Each cell must be a non-empty `str` after `str(value)`; a cell that is `None`, `""` or `"   "` raises `ConsolidationError` with the file name in the message.
- Names are **compared literally**, with no strip, no casefold and no accent removal. Normalise nothing.
- Duplicate headers in the same file (after conversion to `str`) raise `ConsolidationError`.
- A column named exactly `source_file` raises `ConsolidationError` (collision with the column stage B adds).
- Data rows: every row after the header; discard **only** fully empty rows at the end of the sheet. Short rows are padded with `None`. A row with a non-empty value beyond the last header column raises `ConsolidationError`.
- A file with no data rows raises `ConsolidationError` ("no data rows").
- A file that does not open (not a zip or xlsx, corrupted, password protected) raises `ConsolidationError` wrapping the cause; the message must contain the file path. Do not let `zipfile.BadZipFile` or `openpyxl.utils.exceptions.InvalidFileException` escape.
- Never write to, move or delete input files (open with `read_only`).
- `validate_headers`: identical name sets, order irrelevant, literal comparison. If `candidate` is missing columns or has columns absent from `reference`, raise `ConsolidationError` listing the missing and the extra columns and the path of the candidate file.

5) `tests/test_reader.py`, covering at least: ordered discovery ignoring `~$` and non-`.xlsx`; empty directory; reading with a valid header; blank header; duplicate header; header containing `source_file`; corrupted file (garbage bytes with an `.xlsx` extension); file with a header only; short rows padded with `None`; same headers in a different order passing `validate_headers`; incompatible headers failing with a message that names the diverging column. Build the test workbooks with `openpyxl` in `tmp_path`.

6) `tests/conftest.py` if it helps (xlsx creation helpers). Synthetic data only.

7) `.gitignore`: `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `data/output/*.xlsx`.

8) `data/input/.gitkeep` and `data/output/.gitkeep`.

## RULES

- Readable, typed code (use `from __future__ import annotations`), short docstrings, no magic numbers.
- No new dependency, no new file outside `src/excel_consolidator/`, `tests/`, `data/`, `pyproject.toml`, `.gitignore`.
- At the end run, with the `.venv` interpreter:
  `.venv/bin/python -m pip install -e . -q && .venv/bin/python -m pytest tests -q`
- **If a test fails, fix the code, never weaken the test.** Paste the real pytest output in the final report.
- Report: files created, commands executed and the real result.
