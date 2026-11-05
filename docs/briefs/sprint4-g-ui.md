# Brief: Sprint 4, customtkinter interface

Approved by the PO in the session that produced it. This brief records what was asked and the criteria it was accepted against.

## PO decisions

1. Tabs: **Summary + Report + Log**.
2. `config.toml` is loaded when the window opens, with a **Reload config** button.
3. The UI **writes a log file**, at the path from the config, like the CLI.

## Delivered scope

- `ui/controller.py`: `FormFields`, `build_config`, `load_base`, `split_key`, `read_log_tail`, `format_summary`, `run_from_fields` returning `RunOutcome`. No tkinter import.
- `ui/app.py`: path fields (input, output, log) with a browse button, four quality switches, a key field, the Consolidate / Reload config / Open output folder buttons, a progress bar, a status line, and the Summary tab (text), Report tab (Treeview with `section, file, column, metric, value`) and Log tab (file tail plus a refresh button).
- `ui/__main__.py`: `python -m excel_consolidator.ui`, with an optional `--config PATH`.
- `pyproject.toml`: optional extra `ui = ["customtkinter>=5.2"]`.

## Acceptance criteria and evidence

| Criterion | Evidence |
|---|---|
| Green suite, including the controller without opening a window | `pytest tests -q` gives 179 passed |
| `python -m excel_consolidator.ui` opens the window | process starts without error; window "Excel Consolidator" 1024x752 visible in the macOS accessibility tree; screen capture blocked by the OS on this machine |
| Consolidating from the window produces the same result as the CLI | `test_run_from_window_writes_output_and_fills_tabs`: 2 files, 2 rows, tabs filled, log with `written` |
| An error shows a message and preserves the previous output | `test_error_is_shown_without_closing` and `test_error_preserves_previous_output` |
| Does not freeze during the run | execution in a thread with the result delivered through `queue.Queue` and `after` |

## Out of scope

`.app` packaging, icon, scheduling, multiple spreadsheet sheets, `.xls` or `.csv`, editing data in the window.
