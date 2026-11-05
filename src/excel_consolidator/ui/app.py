"""CustomTkinter window: widgets only, all logic lives in the controller."""
from __future__ import annotations

import argparse
import queue
from pathlib import Path
import subprocess
import sys
import threading
from tkinter import filedialog, ttk

import customtkinter as ctk
import pandas as pd

from ..config import RuntimeConfig
from ..report import REPORT_COLUMNS
from . import controller
from .controller import FormFields, RunOutcome

WINDOW_TITLE: str = "Excel Consolidator"
WINDOW_SIZE: str = "1024x720"
_SECTION_PAD = {"padx": 16, "pady": (0, 10)}
_TABLE_STYLE = "Report.Treeview"
_COLUMN_WIDTHS = {"section": 110, "file": 150, "column": 150, "metric": 190, "value": 90}


class App(ctk.CTk):
    """Main consolidation screen."""

    def __init__(self, config_path: Path | None = None) -> None:
        super().__init__()
        self.config_path = config_path
        self.base: RuntimeConfig = controller.default_config()
        self.queue: queue.Queue[RunOutcome] = queue.Queue()
        self.running = False
        self._build_widgets()
        self._load_config(initial=True)
        self.after(120, self._poll_queue)

    # construction
    def _build_widgets(self) -> None:
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(880, 620)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        paths = ctk.CTkFrame(self)
        paths.grid(row=0, column=0, sticky="ew", **_SECTION_PAD)
        paths.grid_columnconfigure(1, weight=1)
        self.input_var = ctk.StringVar()
        self.output_var = ctk.StringVar()
        self.log_var = ctk.StringVar()
        labels = ("Input folder", "Output file", "Log file")
        for row, (label, variable) in enumerate(zip(
            labels, (self.input_var, self.output_var, self.log_var), strict=True
        )):
            ctk.CTkLabel(paths, text=label, width=130, anchor="w").grid(
                row=row, column=0, padx=(16, 8), pady=8, sticky="w")
            ctk.CTkEntry(paths, textvariable=variable).grid(
                row=row, column=1, padx=8, pady=8, sticky="ew")
            ctk.CTkButton(
                paths, text="Browse", width=100,
                command=lambda target=variable, kind=row: self._browse(target, kind),
            ).grid(row=row, column=2, padx=(8, 16), pady=8)

        quality = ctk.CTkFrame(self)
        quality.grid(row=1, column=0, sticky="ew", **_SECTION_PAD)
        quality.grid_columnconfigure(1, weight=1)
        self.trim_var = ctk.BooleanVar(value=False)
        self.numbers_var = ctk.BooleanVar(value=False)
        self.dates_var = ctk.BooleanVar(value=False)
        self.duplicates_var = ctk.BooleanVar(value=False)
        switches = (
            ("Trim text", self.trim_var),
            ("pt-BR numbers", self.numbers_var),
            ("ISO dates", self.dates_var),
            ("Remove duplicates", self.duplicates_var),
        )
        for column, (label, variable) in enumerate(switches):
            ctk.CTkSwitch(quality, text=label, variable=variable).grid(
                row=0, column=column, padx=(16, 8), pady=12, sticky="w")
        ctk.CTkLabel(quality, text="Key (comma separated)", anchor="w").grid(
            row=1, column=0, padx=(16, 8), pady=(0, 14), sticky="w")
        self.key_var = ctk.StringVar()
        ctk.CTkEntry(quality, textvariable=self.key_var, placeholder_text="product, date").grid(
            row=1, column=1, columnspan=2, padx=8, pady=(0, 14), sticky="ew")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", **_SECTION_PAD)
        self.consolidate_button = ctk.CTkButton(actions, text="Consolidate", width=150,
                                                command=self._start_run)
        self.consolidate_button.grid(row=0, column=0, padx=(16, 8), pady=8)
        ctk.CTkButton(actions, text="Reload config", width=160,
                      command=self._reload_config).grid(row=0, column=1, padx=8, pady=8)
        ctk.CTkButton(actions, text="Open output folder", width=170,
                      command=self._open_output_folder).grid(row=0, column=2, padx=8, pady=8)
        self.progress = ctk.CTkProgressBar(actions, width=160, mode="indeterminate")
        self.progress.grid(row=0, column=3, padx=8, pady=8)
        self.progress.set(0)
        self.status = ctk.CTkLabel(actions, text="ready", anchor="w")
        self.status.grid(row=0, column=4, padx=(8, 16), pady=8, sticky="w")
        actions.grid_columnconfigure(4, weight=1)

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=3, column=0, sticky="nsew", **_SECTION_PAD)
        summary = self.tabs.add("Summary")
        report = self.tabs.add("Report")
        log = self.tabs.add("Log")
        for tab in (summary, report, log):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(1, weight=1)

        self.summary_box = ctk.CTkTextbox(summary, wrap="word", font=ctk.CTkFont(family="Menlo", size=13))
        self.summary_box.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.summary_box.insert("1.0", "Choose the input folder and click Consolidate.")
        self.summary_box.configure(state="disabled")

        self._build_report_table(report)
        self.log_box = ctk.CTkTextbox(log, wrap="none", font=ctk.CTkFont(family="Menlo", size=12))
        self.log_box.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 0))
        self.log_box.configure(state="disabled")
        ctk.CTkButton(log, text="Refresh log", width=140, command=self._refresh_log).grid(
            row=1, column=0, sticky="e", padx=4, pady=4)

    def _build_report_table(self, parent: ctk.CTkFrame) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        dark = ctk.get_appearance_mode() == "Dark"
        background = "#2b2b2b" if dark else "#ffffff"
        heading = "#333333" if dark else "#e4e4e4"
        foreground = "#dce4ee" if dark else "#1a1a1a"
        style.configure(_TABLE_STYLE, background=background, fieldbackground=background,
                        foreground=foreground, rowheight=24, borderwidth=0)
        style.configure(f"{_TABLE_STYLE}.Heading", background=heading, foreground=foreground,
                        borderwidth=0)
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        self.report_tree = ttk.Treeview(frame, columns=REPORT_COLUMNS, show="headings",
                                        style=_TABLE_STYLE)
        for column in REPORT_COLUMNS:
            self.report_tree.heading(column, text=column)
            self.report_tree.column(column, width=_COLUMN_WIDTHS[column], anchor="w", stretch=True)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=scrollbar.set)
        self.report_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

    # config
    def _load_config(self, initial: bool = False) -> None:
        config, error = controller.load_base(self.config_path)
        if error is None:
            self.base = config
            self._fill_fields(FormFields.from_config(config))
            self.status.configure(text="config loaded")
            return
        self.status.configure(text="invalid config, using defaults")
        if initial:
            self.base = controller.default_config()
            self._fill_fields(FormFields.from_config(self.base))
        self._set_text(self.summary_box, f"error: {error}")

    def _reload_config(self) -> None:
        if self.running:
            return
        self._load_config()

    def _fill_fields(self, fields: FormFields) -> None:
        self.input_var.set(fields.input_dir)
        self.output_var.set(fields.output_path)
        self.log_var.set(fields.log_file)
        self.key_var.set(fields.key)
        self.trim_var.set(fields.trim_text)
        self.numbers_var.set(fields.normalize_numbers)
        self.dates_var.set(fields.dates_iso)
        self.duplicates_var.set(fields.remove_duplicates)

    def _fields(self) -> FormFields:
        return FormFields(
            input_dir=self.input_var.get(),
            output_path=self.output_var.get(),
            log_file=self.log_var.get(),
            key=self.key_var.get(),
            trim_text=bool(self.trim_var.get()),
            normalize_numbers=bool(self.numbers_var.get()),
            dates_iso=bool(self.dates_var.get()),
            remove_duplicates=bool(self.duplicates_var.get()),
        )

    # actions
    def _browse(self, target: ctk.StringVar, kind: int) -> None:
        if kind == 0:
            chosen = filedialog.askdirectory(title="Input folder", mustexist=True)
        else:
            chosen = filedialog.asksaveasfilename(
                title="Output file" if kind == 1 else "Log file",
                defaultextension=".xlsx" if kind == 1 else ".log",
                filetypes=[("Spreadsheet", "*.xlsx")] if kind == 1 else [("Log", "*.log")],
            )
        if chosen:
            target.set(chosen)

    def _start_run(self) -> None:
        if self.running:
            return
        self.running = True
        self.consolidate_button.configure(state="disabled")
        self.status.configure(text="running...")
        self.progress.start()
        threading.Thread(target=self._work, args=(self._fields(), self.base), daemon=True).start()

    def _work(self, fields: FormFields, base: RuntimeConfig) -> None:
        try:
            outcome = controller.run_from_fields(fields, base)
        except Exception as exc:  # the window must never die from an exception
            outcome = RunOutcome(ok=False, message=f"unexpected error: {exc}")
        self.queue.put(outcome)

    def _poll_queue(self) -> None:
        try:
            outcome = self.queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self._show(outcome)
        self.after(120, self._poll_queue)

    def _show(self, outcome: RunOutcome) -> None:
        self.running = False
        self.consolidate_button.configure(state="normal")
        self.progress.stop()
        self.progress.set(0)
        self.status.configure(text="done" if outcome.ok else "failed")
        message = outcome.message
        if outcome.warnings:
            message = message + "\n" + "\n".join(f"warning: {warning}" for warning in outcome.warnings)
        self._set_text(self.summary_box, message)
        self._fill_report(outcome.report)
        self._set_text(self.log_box, "\n".join(outcome.log_tail))
        self.tabs.set("Summary")

    def _fill_report(self, report: pd.DataFrame | None) -> None:
        self.report_tree.delete(*self.report_tree.get_children())
        if report is None:
            return
        for row in report.itertuples(index=False):
            values = ["" if value is None else str(value) for value in row]
            self.report_tree.insert("", "end", values=values)

    def _refresh_log(self) -> None:
        path = Path(self.log_var.get().strip() or str(self.base.log_file))
        self._set_text(self.log_box, "\n".join(controller.read_log_tail(path, lines=200)))

    def _open_output_folder(self) -> None:
        output = Path(self.output_var.get().strip() or str(self.base.output_path))
        folder = output.parent
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            elif sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            self.status.configure(text=f"could not open: {exc}")

    @staticmethod
    def _set_text(box: ctk.CTkTextbox, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")


def main(argv: list[str] | None = None) -> int:
    """Open the graphical interface window."""
    parser = argparse.ArgumentParser(description="Excel Consolidator graphical interface.")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    App(args.config).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
