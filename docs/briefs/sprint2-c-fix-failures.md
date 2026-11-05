# Codex spec: Sprint 2, Stage C fix (failure attribution)

Repo root, branch `main`. `quality.py` and `tests/test_quality.py` exist and pass (81 tests).

Defects found in the tech lead review. Fix **only** `src/excel_consolidator/quality.py` and add tests in `tests/test_quality.py`.

## DEFECT 1: false failure when another rule converted the cell

With `normalize_numbers=True` and `dates_iso=True`, the cell `"05/11/2026"` is converted to `date` by the date rule, but also records `failed={'normalize_numbers': 1}`.

Reproduction (current behaviour):
```python
standardize(sheet(["data"], [["05/11/2026"]]), QualityOptions(normalize_numbers=True, dates_iso=True)).stats
# {'data': ColumnStats(changed=1, failed={'normalize_numbers': 1})}
```

Correct: no failure, because the cell was converted. Rule: a rule failure counts only if **no** active rule converted the cell; if any rule converted it, `failed` for that cell is empty. The `changed` count stays per rule (trim plus number on the same cell sums 2).

## DEFECT 2: empty string counted as a conversion failure

`""` and `"   "` are empty cells, not unconverted values. Today `""` with `dates_iso=True` produces `failed={'dates_iso': 1}` and `""` with `normalize_numbers=True` produces `failed={'normalize_numbers': 1}`.

Correct: an empty or whitespace-only `str` value is never tried by `normalize_numbers` or `dates_iso` and never increments a failure. With `trim_text` active, `"   "` becomes `""` and counts 1 change under `trim_text`, nothing else.

## DO NOT

- do not change `reader.py`, `consolidator.py`, `writer.py`, `cli.py`, `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `README.md`
- do not change the public signatures (`QualityOptions`, `ColumnStats`, `StandardizationResult`, `standardize`, `find_duplicates`, `build_duplicate_report`)
- do not weaken or remove any existing test; do not change the documented behaviour for valid numbers and dates
- no new dependency, no `git add/commit/push`

## TESTS TO ADD

1. `"05/11/2026"` with `normalize_numbers=True, dates_iso=True` gives `date(2026, 11, 5)`, `changed == 1`, `failed == {}`.
2. `"1.234,56"` with both rules gives `1234.56`, `changed == 1`, `failed == {}`.
3. `""` with `normalize_numbers=True` gives the value `""`, `changed == 0`, `failed == {}`.
4. `""` with `dates_iso=True` gives the same.
5. `"   "` with `trim_text=True, dates_iso=True` gives the value `""`, `changed == 1`, `failed == {}`.
6. `"abc"` with both rules keeps the value untouched, `changed == 0`, `failed == {'normalize_numbers': 1, 'dates_iso': 1}` (nothing converted, both failed).
7. Mixed case: a column with `["05/11/2026", "abc"]` and both rules gives `changed == 1`, `failed['dates_iso'] == 1` and `failed['normalize_numbers'] == 1` (the string `abc` failed both; the date converted and counts no failure).

## RULES

- `.venv/bin/python -m pytest tests -q`
- **If a test fails, fix the code; never weaken the test.**
- Paste the real pytest output and describe the conceptual diff (what changed in `quality.py`).
