"""Consolidação vertical dos valores brutos das entradas."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .reader import (
    ORIGIN_COLUMN, ConsolidationError, SheetData, discover_input_files,
    read_sheet, validate_headers,
)


@dataclass(frozen=True)
class ConsolidationResult:
    """Entradas validadas e seu conteúdo consolidado."""

    files: tuple[SheetData, ...]
    frame: pd.DataFrame

    @property
    def rows(self) -> int:
        """Retorne o total de linhas consolidadas."""
        return len(self.frame)


def consolidate(input_dir: Path) -> ConsolidationResult:
    """Valide todas as entradas e concatene preservando valores e ordem."""
    paths = discover_input_files(input_dir)
    if not paths:
        raise ConsolidationError(f"nenhum arquivo .xlsx em {input_dir}")
    files = tuple(read_sheet(path) for path in paths)
    reference = files[0]
    frames: list[pd.DataFrame] = []
    for sheet in files:
        if sheet is not reference:
            validate_headers(reference, sheet)
        # object evita inferência numérica e a conversão de None em NaN.
        frame = pd.DataFrame(sheet.rows, columns=sheet.columns, dtype=object)
        frame = frame.loc[:, list(reference.columns)].copy()
        frame[ORIGIN_COLUMN] = sheet.path.name
        frames.append(frame)
    return ConsolidationResult(files, pd.concat(frames, ignore_index=True))
