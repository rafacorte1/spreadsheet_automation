"""Consolidação vertical dos valores brutos das entradas."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pandas as pd

from .quality import QualityOptions, build_duplicate_report, find_duplicates, standardize
from .report import build_report
from .reader import (
    ORIGIN_COLUMN, ConsolidationError, SheetData, discover_input_files,
    read_sheet, validate_headers,
)


@dataclass(frozen=True)
class ConsolidationResult:
    """Entradas validadas e seu conteúdo consolidado."""

    files: tuple[SheetData, ...]
    frame: pd.DataFrame
    report: pd.DataFrame
    options: QualityOptions
    warnings: tuple[str, ...] = ()

    @property
    def rows(self) -> int:
        """Retorne o total de linhas consolidadas."""
        return len(self.frame)


def consolidate(input_dir: Path, options: QualityOptions | None = None) -> ConsolidationResult:
    """Valide todas as entradas e concatene preservando valores e ordem."""
    options = options if options is not None else QualityOptions()
    paths = discover_input_files(input_dir)
    if not paths:
        raise ConsolidationError(f"nenhum arquivo .xlsx em {input_dir}")
    files = tuple(read_sheet(path) for path in paths)
    stats = {}
    if options.any_standardization:
        results = tuple(standardize(sheet, options) for sheet in files)
        files = tuple(result.sheet for result in results)
        stats = {result.sheet.path.name: result.stats for result in results}
    reference = files[0]
    unknown = [column for column in options.key if column not in reference.columns]
    warnings: list[str] = []
    if unknown and options.remove_duplicates:
        raise ConsolidationError(f"chave {options.key}: colunas desconhecidas {unknown} em {reference.path}")
    if unknown:
        # A chave só é usada para remover: sem remoção, ela é ignorada e o relatório
        # volta a comparar linhas idênticas, com aviso explícito em vez de erro.
        warnings.append(
            f"chave {options.key} ignorada: colunas desconhecidas {unknown} em {reference.path}; "
            "duplicados contados no modo linhas_identicas"
        )
        options = replace(options, key=())
    frames: list[pd.DataFrame] = []
    for sheet in files:
        if sheet is not reference:
            validate_headers(reference, sheet)
        # object evita inferência numérica e a conversão de None em NaN.
        frame = pd.DataFrame(sheet.rows, columns=sheet.columns, dtype=object)
        frame = frame.loc[:, list(reference.columns)].copy()
        frame[ORIGIN_COLUMN] = sheet.path.name
        frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    duplicates = build_duplicate_report(frame, options)
    report = build_report(files, stats, duplicates, options)
    if options.remove_duplicates:
        frame = frame.loc[~find_duplicates(frame, options.key or reference.columns)].reset_index(drop=True)
    return ConsolidationResult(files, frame, report, options, tuple(warnings))
