"""Escrita do resultado com substituição atômica."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

import pandas as pd

from .errors import ConsolidationError

OUTPUT_SHEET: str = "consolidado"


def write_atomic(frame: pd.DataFrame, output_path: Path) -> None:
    """Grave um temporário completo antes de substituir o destino."""
    temporary: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx")
        temporary = Path(name)
        os.close(descriptor)
        with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
            frame.to_excel(writer, sheet_name=OUTPUT_SHEET, index=False)
        os.replace(temporary, output_path)
    except Exception as exc:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise ConsolidationError(f"Não foi possível escrever {output_path}: {exc}") from exc
