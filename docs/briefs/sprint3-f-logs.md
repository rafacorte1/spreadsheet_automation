# Codex spec: Sprint 3, Stage F (logs, CLI integration and README)

Repo root, branch `main`. Stage E approved (`config.py` with `load_config`, `apply_overrides`, `RuntimeConfig`; 144 tests).

GOAL: add a rotating file log, wire `config.toml` into the CLI and document it. **No scheduling.** Product Owner decision: recurring execution will be done from a future graphical interface, so the core must stay importable and silent.

## DO NOT

- do not change `reader.py`, `quality.py`, `report.py`, `writer.py`, `consolidator.py`, `config.py`, `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- do not create cron jobs, systemd units, launchd plists, scheduling scripts or a CI workflow
- do not add a new dependency (use `logging` and `logging.handlers` from the stdlib)
- do not change the 4 stdout lines already documented (files, rows, output, quality)
- no `git add/commit/push`

## 1) `src/excel_consolidator/runlog.py`

```python
LOGGER_NAME: str = "excel_consolidator"
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES: int = 1_000_000
DEFAULT_BACKUP_COUNT: int = 1

def setup_logging(
    log_file: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger
def close_logging(logger: logging.Logger) -> None
```

- Logger named `excel_consolidator`, level `INFO`, `propagate = False`, **no** console handler (stdout and stderr belong to the CLI).
- `RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")`; create the parent directory (`parents=True, exist_ok=True`). Failure to create the directory or file raises `ConsolidationError` naming the path.
- `setup_logging` must be **idempotent**: calling it twice does not duplicate handlers (remove and close the previous handlers of the same logger).
- `close_logging` closes and removes the logger handlers.

## 2) `src/excel_consolidator/cli.py`

Signatures:

```python
def run(input_dir: Path, output_path: Path, options: QualityOptions | None = None) -> ConsolidationResult
def run_config(config: RuntimeConfig) -> ConsolidationResult
def main(argv: Sequence[str] | None = None) -> int
```

- `run` keeps the current behaviour (used by the tests and by a future UI). `run_config` does `consolidate(input_dir, options)` plus `write_atomic(frame, output, report)`.
- New arguments: `--config PATH` (default `None`, meaning look for `config.toml` in the CWD) and `--log-file PATH` (default `None`).
- `--input`, `--output`, `--trim-text`, `--normalize-numbers`, `--dates-iso` and `--remove-duplicates` move to `default=None` so "not given" can be told apart from "false". `--key` stays `default=None`; an empty string or a string of commas raises `ConsolidationError`.
- Precedence: explicit CLI, then `config.toml`, then defaults, resolved with `load_config` plus `apply_overrides`. `--config` pointing to a missing file exits 1.
- `main` must load the config, open the log, write the log lines below, run, print **exactly** the 4 existing stdout lines and return 0. On `ConsolidationError` it writes `error=<message>` to the log, prints `error: <message>` on stderr and returns 1 (no traceback, previous output intact). Always close the log, including on the error path.
- Log lines (one per call, INFO level except the last):
  ```text
  start input=<resolved input> output=<resolved output> flags=<trim_text,normalize_numbers,dates_iso,remove_duplicates when active, comma separated, or none> key=<a,b or ->
  read files=<n> rows_read=<sum of rows_read>
  written rows=<final rows> nulls=<n> duplicates=<n> removed=<n> changed=<n> output=<absolute path>
  ```
  on error: `ERROR error=<message>`.

## 3) `.gitignore`

Add `data/output/*.log` and `data/output/*.log.1`.

## 4) Tests

`tests/test_runlog.py`:

- creates the directory and the file; the content holds the three log lines of a real run (through `main`), with a date prefix in `%Y-%m-%d %H:%M:%S` format
- a second run **appends** (the file grows, the previous content is preserved) and does not duplicate the handler (the line count per run is exact)
- rotation: with a small `max_bytes` through monkeypatching the default, after two runs `<log>.1` exists and the current log is smaller
- `setup_logging` in an impossible directory (a regular file occupying the directory name) raises `ConsolidationError`
- `close_logging` removes the handlers (a second call does not fail)

`tests/test_cli.py` (add, without breaking the existing tests):

- `--config` with a complete file sets input, output and flags, and stdout remains the 4 lines
- an explicit `--input` beats `config.toml`
- an explicit `--log-file` beats the config; the log is created at the given path
- a missing `--config` gives exit 1, stderr with the path, and no output created
- a config with an unknown key gives exit 1, stderr mentions the key
- with no `config.toml` in the CWD the CLI still works with defaults and creates the default log
- an error case with logging on: `error=` appears in the log file and stdout stays empty

`tests/test_end_to_end.py` (add one test, keep the existing ones):

- run through `subprocess` with `--config` and `--log-file` in `tmp_path`, check the 4-line stdout, the sheets, the content and the log with the three lines; check that the input files did not change.

## 5) `README.md`

Add: a configuration section (with the TOML block from `config.example.toml`, the CLI over file over default precedence and the path-relative-to-file rule), a logging section (default path, rotation at about 1 MB keeping one backup, line format, a real three-line example) and a note that there is **no scheduling**: the automation is triggered by a command and the core (`run_config`) is importable for a future graphical interface.

## RULES

- `.venv/bin/python -m pytest tests -q`
- **If a test fails, fix the code; never weaken the test.** Do not weaken the existing stdout assertions.
- At the end paste the real pytest output and a real run showing the 4 stdout lines plus the content of the log file.
