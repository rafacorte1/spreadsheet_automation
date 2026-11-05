# Codex spec: Sprint 2, Stage C (pure quality module plus tests)

Repo root. Sprint 1 is approved and committed (`a4defda`); `reader.py`, `consolidator.py`, `writer.py` and `cli.py` exist and must not be touched in this stage.

GOAL: create `quality.py` with optional standardisation (change and failure counts per column) and duplicate detection, plus tests. No CLI, consolidator, writer or README change in this stage.

## DO NOT

- do not change `reader.py`, `consolidator.py`, `writer.py`, `cli.py`, `__main__.py` (stage D handles those)
- do not change `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `README.md`
- no `git add`, `git commit`, `git push`
- no new dependency (pandas, openpyxl and pytest are installed)
- do not implement casefold, accent removal, dedup without a flag, logging or external configuration
- no silent transformation: a value the rule cannot convert must **stay untouched** and be counted as a failure

## DELIVERABLES

1) `src/excel_consolidator/quality.py`

```python
TRIM_TEXT: str = "trim_text"
NORMALIZE_NUMBERS: str = "normalize_numbers"
DATES_ISO: str = "dates_iso"

@dataclass(frozen=True)
class QualityOptions:
    trim_text: bool = False
    normalize_numbers: bool = False
    dates_iso: bool = False
    key: tuple[str, ...] = ()           # empty = compare the whole row
    remove_duplicates: bool = False

    @property
    def any_standardization(self) -> bool

@dataclass(frozen=True)
class ColumnStats:
    changed: int = 0                    # changed values, summing all active rules
    failed: dict[str, int] = ...        # rule -> count of values not converted

@dataclass(frozen=True)
class StandardizationResult:
    sheet: SheetData
    stats: dict[str, ColumnStats]       # key = column name

def standardize(sheet: SheetData, options: QualityOptions) -> StandardizationResult
def find_duplicates(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series  # bool mask
def build_duplicate_report(frame, options) -> DuplicateReport   # optional; use it if it helps
```

Standardisation rules (apply **only** when the matching flag is on; fixed order per cell: trim, numbers, dates):

- `trim_text`: `str` only; strips spaces, tabs and line breaks at both ends (use `str.strip()`). Counted as changed only when the result differs from the original.
- `normalize_numbers`: `str` only. After `strip()`, accepts:
  - pt-BR with thousands separators: `1.234,56`, `-1.234`, `12.345.678,9`
  - pt-BR without thousands separators: `1234,56`, `-12,5`
  - plain integer: `42`, `-7`
  - The return is `int` when there is no decimal part and `float` when there is. No `Decimal`, no `NaN` in the data.
  - `R$`, `$`, negative parentheses, scientific notation and suffixes are not supported: they count as a failure and the value **remains the original string**.
  - A string that matches no pattern: failure, value untouched.
- `dates_iso`: `str` only. Accepted formats, tried in order: `%d/%m/%Y`, `%Y-%m-%d`, `%Y-%m-%d %H:%M:%S`, `%d/%m/%Y %H:%M:%S`. Returns `datetime.date` (or `datetime.datetime` when a time is present). Any other text: failure, value untouched. Do not invent formats; no two-digit years (ambiguous).
- A cell that is not `str` (number, `None`, `bool`, openpyxl date) is never touched by any rule.
- `stats` must have an entry for **every** column of the sheet (even with 0 changes), so the report stays stable.
- Never mutate the `SheetData` received: return a new `SheetData` with the transformed rows.

Duplicates:

- `find_duplicates(frame, columns)`: uses `frame.duplicated(subset=list(columns), keep="first")`; `None` counts as equal to `None`. The mask marks, for each group, every row **except the first occurrence**.
- `build_duplicate_report`: when `options.key` is empty, compare the whole row **excluding** `ORIGIN_COLUMN` (an identical row in different files is a duplicate); when a `key` is given, compare only those columns. Return counts: `total` (duplicate rows), `removed` (equal to `total` when `remove_duplicates` is True, otherwise 0) and the mode used (`"identical_rows"` or `"key:" + ",".join(key)`).

2) `tests/test_quality.py`, covering at least:

- no flags: `standardize` returns identical rows and `stats` with every column at zero
- trim: changes only strings with surrounding spaces, leaves numbers, `None` and dates alone; counts changes correctly; `"  a  b  "` becomes `"a  b"`
- numbers: `"1.234,56"` to `1234.56`; `"1.234"` to `1234` (int); `"-12,5"` to `-12.5`; `"42"` to `42` (int); `"12.345.678,9"` to `12345678.9`
- numbers with failure: `"R$ 1.234,56"`, `"abc"`, `"1,2,3"`, `"1.23.456"` keep the original value and increment the failure count
- dates: `"05/11/2026"` to `date(2026, 11, 5)`; `"2026-11-05"` to `date(2026, 11, 5)`; `"2026-11-05 14:30:00"` to `datetime(2026, 11, 5, 14, 30)`; `"31/02/2026"`, `"2026-13-01"` and `"05/11/26"` fail and stay untouched
- independent per-column counts (one column with 2 changes and another with 1)
- the original `sheet` is not mutated
- duplicates by whole row: equal rows in different files are marked; the first occurrence is not marked; rows differing in one column are not marked
- duplicates by key: `key=("name",)` marks the second occurrence even when other columns differ
- `remove_duplicates=False` gives `removed == 0`; `True` gives `removed == total`
- `ORIGIN_COLUMN` does not take part in the comparison when `key` is empty

## RULES

- Interpreter and tests: `.venv/bin/python -m pytest tests -q`
- Typed code, `from __future__ import annotations`, short docstrings, named constants, no magic numbers.
- **If a test fails, fix the code; never weaken the test.** Do not change the 36 Sprint 1 tests.
- Paste the real pytest output (total count including the older tests) and report the files created.
