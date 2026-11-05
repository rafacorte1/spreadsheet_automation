"""Window acceptance: builds the screen, runs and checks widgets. Skips without a display."""
from __future__ import annotations

import time
import tkinter

import pytest

pytest.importorskip("customtkinter")

from excel_consolidator.ui.app import App  # noqa: E402


@pytest.fixture
def app():
    try:
        instance = App()
    except tkinter.TclError as exc:
        pytest.skip(f"no display for tkinter: {exc}")
    instance.withdraw()
    yield instance
    instance.destroy()


def pump_until_done(app: App, timeout: float = 30.0) -> None:
    """Run the event loop until the worker thread delivers the result."""
    deadline = time.monotonic() + timeout
    while app.running and time.monotonic() < deadline:
        app.update()
        time.sleep(0.03)
    app.update()
    assert not app.running, "the run did not finish in time"


def test_tabs_and_initial_fields(app):
    for name in ("Summary", "Report", "Log"):
        app.tabs.set(name)
    assert app.tabs.get() == "Log"
    assert app.input_var.get() == "data/input"
    assert app.output_var.get() == "data/output/consolidated.xlsx"


def test_run_from_window_writes_output_and_fills_tabs(app, tmp_path, make_xlsx):
    make_xlsx(tmp_path / "input" / "a.xlsx", [["product", "amount"], ["Mouse", 50]])
    make_xlsx(tmp_path / "input" / "b.xlsx", [["amount", "product"], [100, "Keyboard"]])
    app.input_var.set(str(tmp_path / "input"))
    app.output_var.set(str(tmp_path / "output" / "consolidated.xlsx"))
    app.log_var.set(str(tmp_path / "output" / "consolidation.log"))
    app._start_run()
    pump_until_done(app)
    assert app.status.cget("text") == "done"
    assert (tmp_path / "output" / "consolidated.xlsx").is_file()
    summary = app.summary_box.get("1.0", "end")
    assert "files: 2" in summary and "rows: 2" in summary
    assert len(app.report_tree.get_children()) == 9
    assert "written" in app.log_box.get("1.0", "end")
    assert app.consolidate_button.cget("state") == "normal"


def test_error_is_shown_without_closing(app, tmp_path):
    app.input_var.set(str(tmp_path / "missing"))
    app.output_var.set(str(tmp_path / "output.xlsx"))
    app._start_run()
    pump_until_done(app)
    assert app.status.cget("text") == "failed"
    assert app.summary_box.get("1.0", "end").strip().startswith("error: ")
    assert app.report_tree.get_children() == ()


def test_refresh_log_reads_file(app, tmp_path):
    log = tmp_path / "app.log"
    log.write_text("line one\nline two\n", encoding="utf-8")
    app.log_var.set(str(log))
    app._refresh_log()
    assert app.log_box.get("1.0", "end").strip() == "line one\nline two"
