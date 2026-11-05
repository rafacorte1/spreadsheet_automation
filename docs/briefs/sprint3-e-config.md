# Codex spec: Sprint 3, Stage E (TOML configuration)

Repo root, branch `main` (`accf997`). Sprints 1 and 2 approved, 115 tests passing.

GOAL: add `config.py` with validated `config.toml` loading, precedence CLI over file over default, and tests. **No** logging, CLI or README change in this stage.

## DO NOT

- do not change `reader.py`, `quality.py`, `report.py`, `writer.py`, `consolidator.py`, `cli.py`, `__main__.py`, `README.md`
- do not implement logging, scheduling, a graphical interface or environment variables
- no new dependency: use `tomllib` (stdlib, Python >= 3.11)
- no `git add/commit/push`
- do not create a real `config.toml` in the repository (only `config.example.toml`)

## DELIVERABLES

1) `src/excel_consolidator/config.py`

```python
CONFIG_FILENAME: str = "config.toml"
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidated.xlsx")
DEFAULT_LOG_FILE: Path = Path("data/output/consolidation.log")

@dataclass(frozen=True)
class RuntimeConfig:
    input_dir: Path
    output_path: Path
    log_file: Path
    options: QualityOptions

def load_config(path: Path | None = None) -> RuntimeConfig
def apply_overrides(config: RuntimeConfig, **overrides: object) -> RuntimeConfig
```

File format (every key optional):

```toml
input = "data/input"
output = "data/output/consolidated.xlsx"
log_file = "data/output/consolidation.log"

[quality]
trim_text = false
normalize_numbers = false
dates_iso = false
remove_duplicates = false
key = ["product", "date"]
```

Mandatory rules:

- `load_config(None)`: if `Path(CONFIG_FILENAME)` exists in the current directory, load it; if not, return the defaults. Never fail because the file is missing in this mode.
- `load_config(path)` with an explicit `path`: a missing file raises `ConsolidationError` naming the path. An unreadable file or invalid TOML raises `ConsolidationError` naming the path and the cause.
- Valid root keys: `input`, `output`, `log_file`, `quality`. Any other key (including inside `[quality]`) raises `ConsolidationError` listing the unknown keys. A typo cannot be ignored.
- Types: `input`, `output` and `log_file` must be non-empty `str`; the booleans must be `bool`; `key` must be a list of non-empty `str` (an empty list is accepted). A wrong type raises `ConsolidationError` naming the key, the expected type and the received type.
- A missing `[quality]` means all defaults (`False`, `key=()`). A `[quality]` that is present but not a table is an error.
- Relative paths in the file are resolved **relative to the directory of the configuration file**, not to the CWD. Absolute paths pass through unchanged. Defaults (no file) stay relative to the CWD.
- `apply_overrides(config, **overrides)`: `overrides` accepts only the names `input_dir`, `output_path`, `log_file`, `trim_text`, `normalize_numbers`, `dates_iso`, `key`, `remove_duplicates`; a `None` value means "do not override". An unknown name raises `TypeError`. Returns a new `RuntimeConfig` (frozen, no mutation).

2) `config.example.toml` at the root, with every key and short comments. Do **not** create `config.toml` (it is optional; the example is the documentation).

3) `.gitignore`: add `config.toml` (local user configuration must not be versioned).

4) `tests/test_config.py`, covering:

- no file in the current directory, so exact defaults (`data/input`, `data/output/consolidated.xlsx`, `data/output/consolidation.log`, `QualityOptions()`)
- a complete file, so every field read
- a file with only `input`, so the other fields at their defaults
- a partial `[quality]` (`key = ["a"]`, `trim_text = true`), so the other flags stay `False`
- `load_config(path)` on a missing file raises `ConsolidationError` with the path in the message
- invalid TOML raises `ConsolidationError` with the path
- an unknown key at the root and inside `[quality]` raises an error listing the key
- wrong types (`input = 5`, `trim_text = "yes"`, `key = "product"`, `key = [1]`, `input = ""`) raise an error with key and type
- a relative path resolved from the config directory (create the config in `tmp_path/sub`, use `input = "data"`, expect `tmp_path/sub/data`)
- an absolute path preserved
- `apply_overrides`: overrides only non-`None` values; `None` keeps the current value; an invalid name raises `TypeError`; the original is not mutated
- `load_config` finds `config.toml` in the CWD (use `monkeypatch.chdir(tmp_path)`)

## RULES

- `.venv/bin/python -m pytest tests -q`
- Typed code, `from __future__ import annotations`, short docstrings.
- **If a test fails, fix the code; never weaken the test.** Do not change the 115 existing tests.
- Paste the real pytest output and report the files created.
