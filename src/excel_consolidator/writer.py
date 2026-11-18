"""Stage complete exports before replacing any destination."""
from __future__ import annotations

from contextlib import ExitStack
import csv
import os
from pathlib import Path
import shutil
import tempfile
from typing import TextIO

import pandas as pd

from .errors import ConsolidationError
from .report import REPORT_COLUMNS, REPORT_SHEET

OUTPUT_SHEET: str = "consolidated"


def write_atomic(frame: pd.DataFrame, output_path: Path, report: pd.DataFrame | None = None) -> None:
    """Write a workbook with the consolidated sheet and an optional report sheet."""
    _write_outputs(frame, report, {"xlsx": output_path})


def write_outputs(frame: pd.DataFrame, report: pd.DataFrame, outputs: dict[str, Path]) -> None:
    """Write the requested workbook and/or CSV files as one set."""
    _write_outputs(frame, report, outputs)


def _write_xlsx(frame: pd.DataFrame, report: pd.DataFrame | None, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=OUTPUT_SHEET, index=False)
        if report is not None:
            report.to_excel(writer, sheet_name=REPORT_SHEET, index=False)


class _CsvStream:
    """Preserve quoting for CR and LF inside cells while ending records with LF."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def write(self, record: str) -> int:
        # csv.writer uses its configured line terminator to decide which cells to quote.
        return self.stream.write(record.removesuffix("\r\n") + "\n")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(_CsvStream(stream), delimiter=",", quoting=csv.QUOTE_MINIMAL,
                            lineterminator="\r\n")
        writer.writerow(frame.columns)
        writer.writerows(frame.itertuples(index=False, name=None))


def _write_outputs(
    frame: pd.DataFrame, report: pd.DataFrame | None, outputs: dict[str, Path],
) -> None:
    staged: dict[Path, Path] = {}
    with ExitStack() as cleanup:
        for kind, destination in outputs.items():
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                suffix = ".xlsx" if kind == "xlsx" else ".csv"
                descriptor, name = tempfile.mkstemp(dir=destination.parent, suffix=suffix)
                temporary = Path(name)
                cleanup.callback(temporary.unlink, missing_ok=True)
                os.close(descriptor)
                if kind == "xlsx":
                    report_sheet = report.loc[:, list(REPORT_COLUMNS)] if report is not None else None
                    _write_xlsx(frame, report_sheet, temporary)
                elif kind == "csv":
                    _write_csv(frame, temporary)
                else:
                    assert report is not None
                    _write_csv(report.loc[:, list(REPORT_COLUMNS)], temporary)
                staged[destination] = temporary
            except Exception as exc:
                raise ConsolidationError(f"could not write {destination}: {exc}") from exc
        _publish(staged)


def _publish(staged: dict[Path, Path]) -> None:
    """Replace complete files and roll back earlier replacements if one fails."""
    destination = next(iter(staged))
    backup_dir: Path | None = None
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    recovery_errors: list[str] = []
    try:
        if len(staged) > 1:
            backup_dir = Path(tempfile.mkdtemp(dir=destination.parent))
            for index, destination in enumerate(staged):
                if destination.is_symlink() or destination.exists():
                    if not destination.is_symlink() and not destination.is_file():
                        raise OSError("destination is not a regular file")
                    backup = backup_dir / str(index)
                    shutil.copy2(destination, backup, follow_symlinks=False)
                    backups[destination] = backup
        for destination, temporary in staged.items():
            os.replace(temporary, destination)
            published.append(destination)
    except Exception as exc:
        for path in reversed(published):
            try:
                if path in backups:
                    os.replace(backups[path], path)
                else:
                    path.unlink(missing_ok=True)
            except OSError as recovery_error:
                recovery_errors.append(f"{path}: {recovery_error}")
        message = f"could not write {destination}: {exc}"
        if recovery_errors:
            message += f"; could not roll back output (backups in {backup_dir}): "
            message += ", ".join(recovery_errors)
        raise ConsolidationError(message) from exc
    finally:
        if backup_dir is not None and not recovery_errors:
            shutil.rmtree(backup_dir)
