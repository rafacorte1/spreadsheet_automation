# Codex spec: Sprint 3 fix (tests pollute the real log)

Repo root. 153 tests pass, but the suite writes to the production log file.

## DEFECT

`tests/test_cli.py`, `tests/test_end_to_end.py` and `tests/test_runlog.py` call `main()` without `--log-file`. Since the default is `data/output/consolidation.log` relative to the CWD, running `pytest` from the repository root creates and fills `data/output/consolidation.log` with dozens of test entries (`pytest-of-<user>/...`). The log of real runs is polluted.

Real evidence: after `pytest tests -q` from the root, `data/output/consolidation.log` contains lines with temporary paths from the pytest test directories.

## EXPECTED FIX

1. `tests/conftest.py`: a function-scoped autouse fixture that runs each test inside its own temporary directory (for example `monkeypatch.chdir(tmp_path)`), so no default CWD-relative path lands inside the repository. Existing tests already receive `tmp_path` and use absolute paths; adjust whatever breaks without weakening an assertion.
2. Make sure tests that depend on `config.toml` in the CWD stay valid (they already use `monkeypatch.chdir` or `tmp_path`).
3. Do not hide `--log-file` inside `main` and do not change the production default. The fix is test isolation.
4. Remove the `data/output/consolidation.log` file from the repository (it is generated, not versioned).

## DO NOT

- do not change `src/` at all (`reader.py`, `quality.py`, `report.py`, `writer.py`, `consolidator.py`, `config.py`, `runlog.py`, `cli.py`, `__main__.py`)
- do not change `README.md`, `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- no new dependency; no `git add/commit/push`
- do not weaken any existing assertion

## MANDATORY VERIFICATION (paste the real output)

```bash
cd spreadsheet_automation
rm -f data/output/consolidation.log
.venv/bin/python -m pytest tests -q
ls -la data/output/ ; test ! -e data/output/consolidation.log && echo "production log untouched"
```

- `pytest` with every test passing
- `data/output/consolidation.log` must **not** exist after the suite
- report which tests needed adjustment and why
