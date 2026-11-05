# Codex spec: Sprint 2, Stage D (report, integration and CLI)

Repo root. Sprint 1 (commit `a4defda`) and Stage C (`quality.py`, 95 tests) are approved. Integrate data quality into the consolidation and the CLI.

## DO NOT

- do not change `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- do not change `reader.py` or the behaviour documented for Sprint 1 (literal header validation, reserved column, atomic write, inputs untouched)
- do not implement casefold, accent removal, logging, external configuration or scheduling
- no new dependency, no `git add/commit/push`
- do not invent acceptance numbers in production code

## 1) `src/excel_consolidator/report.py`

```python
REPORT_SHEET: str = "report"
REPORT_COLUMNS: tuple[str, ...] = ("section", "file", "column", "metric", "value")

@dataclass(frozen=True)
class QualitySummary:
    nulls: int
    duplicates: int
    removed: int
    changed: int

def count_nulls(sheet: SheetData) -> dict[str, int]        # column -> nulls (None or "")
def build_report(
    sheets: Sequence[SheetData],                            # already standardised
    stats: Mapping[str, Mapping[str, ColumnStats]],         # file name -> column -> stats
    duplicates: DuplicateReport,
    options: QualityOptions,
) -> pd.DataFrame
def summarize(report: pd.DataFrame) -> QualitySummary
```

`report` layout (exact columns `section, file, column, metric, value`), in this section order, files in alphabetical order and columns in sheet order:

- `("summary", file, "", "rows_read", n)`, one row per file
- `("nulls", file, column, "nulls", n)`, every column, including zero
- `("standardization", file, column, "changed_<rule>", n)` and `("standardization", file, column, "failed_<rule>", n)`, **only** for rules active in `options`, every column, including zero
- `("duplicates", "", "", "mode", "<identical_rows|key:a,b>")`
- `("duplicates", "", "", "duplicate_rows", n)`
- `("duplicates", "", "", "rows_removed", n)`

`nulls` means `None` or an empty or whitespace-only `str`, counted in the data **after** standardisation and **before** duplicate removal, in the data columns only (never in `ORIGIN_COLUMN`). `summarize` sums the `nulls` section, reads the three `duplicates` rows and sums `changed_*` from the `standardization` section.

## 2) `src/excel_consolidator/writer.py`

Change it to:

```python
def write_atomic(frame: pd.DataFrame, output_path: Path, report: pd.DataFrame | None = None) -> None
```

Same atomicity as Sprint 1 (temporary file in the destination directory plus `os.replace`, cleanup on failure). Sheet `consolidated` first; when `report` is not `None`, sheet `report` with `REPORT_COLUMNS` in order. `write_atomic(frame, output)` must keep working and produce a **single** sheet (the Sprint 1 tests depend on it).

## 3) `src/excel_consolidator/consolidator.py`

```python
def consolidate(input_dir: Path, options: QualityOptions | None = None) -> ConsolidationResult

@dataclass(frozen=True)
class ConsolidationResult:
    files: tuple[SheetData, ...]      # already standardised sheets
    frame: pd.DataFrame               # final data (after duplicate removal, when requested)
    report: pd.DataFrame
    options: QualityOptions
    @property
    def rows(self) -> int
```

Flow: discover, read, standardise (only when `options.any_standardization`), validate headers, build frames in the first file's order plus `source_file`, concatenate, count duplicates, remove when `options.remove_duplicates` (keeping the first occurrence in file and row order), then build the report from the data **before** removal for the null and duplicate counts.

Key validation in `options.key`: a key column missing from the first file's data columns raises `ConsolidationError` listing the unknown columns (message containing the key and the reference directory or file). Duplicates compare the key columns, without `ORIGIN_COLUMN`.

> Note added after delivery: the approved key-validation decision later narrowed this. An unknown key column is an error only when duplicates are removed; without removal the key is ignored with a `WARNING` in the log and the report falls back to `identical_rows`. An empty key is always rejected.

## 4) `src/excel_consolidator/cli.py`

New flags: `--trim-text`, `--normalize-numbers`, `--dates-iso`, `--key COL1,COL2`, `--remove-duplicates` (all off by default). `--key` accepts spaces and drops empty entries; `--key ""` or `--key ,` raises `ConsolidationError`.

Stdout on success, exactly:

```text
files: <n>
rows: <rows in the final file>
output: <absolute path>
quality: nulls=<X> duplicates=<Y> removed=<Z> changed=<W>
```

`rows` reflects the final file, after removal. On `ConsolidationError`: `error: <message>` on stderr, exit 1, no traceback, the previous output untouched.

## 5) Tests

`tests/test_report.py`: exact layout (columns and section order) for a fixed scenario; nulls counted only in data and excluding `source_file`; `None` and `"   "` count; standardisation sections absent when no rule is active; `summarize` closing with the counts.

`tests/test_consolidator.py` (add, without breaking the 4 existing tests): `consolidate` with no options produces the same rows as Sprint 1; an invalid `--key` raises `ConsolidationError` naming the column; removal keeps the first occurrence; `report` contains `rows_read` per file.

`tests/test_cli.py` (add): the `quality:` line with the four correct numbers in a scenario with a null, a duplicate and standardisation; `--trim-text` changing data in the output; `--remove-duplicates` reducing `rows`; an invalid `--key` giving exit 1 with stderr and the previous output intact; no flags, zeroed counters when the data is clean.

`tests/test_end_to_end.py` (add one test, keep the existing one): two spreadsheets with a null, a row duplicated across files and a value `" 1.234,56 "`; run with `--trim-text --normalize-numbers --remove-duplicates` and check **in the generated workbook** the values, the two sheets and the report; run again without flags and check the data returns to the original.

## 6) `README.md`

Add: the new flags with a usage example, the `report` sheet format, the definition of `rows` (final output) versus `rows_read` (input), the rule that an unconverted value stays untouched and is counted as a failure, and the new limitations (no casefold or accent handling; no similarity dedup; `"007"` becomes `7` with `--normalize-numbers`).

## RULES

- `.venv/bin/python -m pytest tests -q`
- **If a test fails, fix the code; never weaken the test.** Do not remove or weaken existing tests; if a stdout format changed, update the assertion to the new format specified above.
- Paste the real pytest output and a real CLI run with synthetic data showing the four stdout lines.
