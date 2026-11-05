# Codex spec: Sprint 2, Stage C fix 2 (failure swallowed by trim)

Repo root. Fix only `src/excel_consolidator/quality.py` and add tests in `tests/test_quality.py`.

## DEFECT

In `standardize`, failures are recorded only under `if not cell_changes:`. Because `trim_text` also increments `cell_changes`, a cell that was only trimmed loses its conversion failures.

Reproduction:
```python
s = SheetData(Path("a.xlsx"), ("Name",), (("  Ana  ",),))
standardize(s, QualityOptions(trim_text=True, normalize_numbers=True, dates_iso=True)).stats["Name"]
# current: ColumnStats(changed=1, failed={}, changed_by_rule={'trim_text': 1})
# correct: ColumnStats(changed=1, failed={'normalize_numbers': 1, 'dates_iso': 1}, changed_by_rule={'trim_text': 1})
```

`"Ana"` (trimmed from `"  Ana  "`) is neither a number nor a date: both conversions failed and the report has to say so.

## CORRECT RULE

Failure suppression exists only for a cell that a **conversion** rule (`normalize_numbers` or `dates_iso`) converted successfully. Therefore:

- set `converted = True` only when a converter returns a value, not when trim changes the string;
- record the accumulated failures for the cell when `converted` is `False`, regardless of trim having changed the cell;
- `changed` and `changed_by_rule` stay as they are (trim plus conversion on the same cell sums 2).

Do not change the behaviour for empty or whitespace-only strings: they are still not tried by the converters and count no failure.

## TESTS TO ADD (do not remove or weaken the existing ones)

1. `("  Ana  ",)` with `trim_text=True, normalize_numbers=True, dates_iso=True` gives `"Ana"`, `changed == 1`, `changed_by_rule == {'trim_text': 1}`, `failed == {'normalize_numbers': 1, 'dates_iso': 1}`.
2. `(" 42 ",)` with the three flags (already covered) stays `changed == 2` and `failed == {}`.
3. `(" 05/11/2026 ",)` with the three flags gives `date(2026, 11, 5)`, `changed == 2`, `failed == {}`.
4. `(" abc ",)` with the three flags gives `"abc"`, `changed == 1`, `failed` with both rules.
5. Mixed column `[("  Ana  ",), ("1.234,56",), ("",)]` with the three flags gives `changed == 4` (2 from trim, 1 from numbers, 0), `failed == {'normalize_numbers': 1, 'dates_iso': 1}` (only the `"Ana"` cell), and the report with coherent `failed_*` metrics.

## DO NOT

- do not change `reader.py`, `report.py`, `writer.py`, `consolidator.py`, `cli.py`, `README.md` or the other tests
- do not change public signatures
- no new dependency, no `git add/commit/push`

## RULES

- `.venv/bin/python -m pytest tests -q`
- **If a test fails, fix the code; never weaken the test.**
- Paste the real pytest output (total count) and the code snippet that changed.
