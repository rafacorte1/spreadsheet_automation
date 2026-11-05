"""Write the result with atomic replacement."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pandas as pd

from .errors import ConsolidationError
from .report import REPORT_COLUMNS, REPORT_SHEET

OUTPUT_SHEET: str = "consolidated"


def write_atomic(frame: pd.DataFrame, output_path: Path, report: pd.DataFrame | None = None) -> None:
    """Write a complete temporary file before replacing the target."""
    temporary: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx")
        temporary = Path(name)
        os.close(descriptor)
        with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name=OUTPUT_SHEET, index=False)
            if report is not None:
                report.loc[:, list(REPORT_COLUMNS)].to_excel(writer, sheet_name=REPORT_SHEET, index=False)
        os.replace(temporary, output_path)
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise ConsolidationError(f"could not write {output_path}: {exc}") from exc
