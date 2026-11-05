"""Relatório de qualidade sobre os dados anteriores à deduplicação."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

from .quality import DATES_ISO, NORMALIZE_NUMBERS, TRIM_TEXT, ColumnStats, DuplicateReport, QualityOptions
from .reader import ORIGIN_COLUMN, SheetData

REPORT_SHEET: str = "relatorio"
REPORT_COLUMNS: tuple[str, ...] = ("secao", "arquivo", "coluna", "metrica", "valor")


@dataclass(frozen=True)
class QualitySummary:
    nulls: int
    duplicates: int
    removed: int
    changed: int


def count_nulls(sheet: SheetData) -> dict[str, int]:
    """Conte None e textos vazios, ignorando a coluna de origem."""
    return {
        column: sum(row[index] is None or (isinstance(row[index], str) and not row[index].strip())
                    for row in sheet.rows)
        for index, column in enumerate(sheet.columns) if column != ORIGIN_COLUMN
    }


def build_report(
    sheets: Sequence[SheetData],
    stats: Mapping[str, Mapping[str, ColumnStats]],
    duplicates: DuplicateReport,
    options: QualityOptions,
) -> pd.DataFrame:
    """Monte seções em ordem estável, incluindo contadores zerados."""
    ordered = sorted(sheets, key=lambda sheet: sheet.path.name)
    rows: list[tuple[object, ...]] = [
        ("resumo", sheet.path.name, "", "linhas_lidas", len(sheet.rows)) for sheet in ordered
    ]
    for sheet in ordered:
        rows.extend(("nulos", sheet.path.name, column, "nulos", count)
                    for column, count in count_nulls(sheet).items())
    for sheet in ordered:
        for column in sheet.columns:
            if column == ORIGIN_COLUMN:
                continue
            column_stats = stats.get(sheet.path.name, {}).get(column, ColumnStats())
            for enabled, rule in ((options.trim_text, TRIM_TEXT),
                                  (options.normalize_numbers, NORMALIZE_NUMBERS),
                                  (options.dates_iso, DATES_ISO)):
                if enabled:
                    rows.append(("padronizacao", sheet.path.name, column, f"alterados_{rule}",
                                 column_stats.changed_by_rule.get(rule, 0)))
                    rows.append(("padronizacao", sheet.path.name, column, f"falhas_{rule}",
                                 column_stats.failed.get(rule, 0)))
    rows.extend(("duplicados", "", "", metric, value) for metric, value in (
        ("modo", duplicates.mode), ("linhas_duplicadas", duplicates.total),
        ("linhas_removidas", duplicates.removed),
    ))
    return pd.DataFrame(rows, columns=REPORT_COLUMNS)


def summarize(report: pd.DataFrame) -> QualitySummary:
    """Extraia os quatro contadores exibidos pela CLI."""
    duplicates = report.loc[report["secao"] == "duplicados"].set_index("metrica")["valor"]
    changed = (report["secao"] == "padronizacao") & report["metrica"].str.startswith("alterados_")
    return QualitySummary(
        int(report.loc[report["secao"] == "nulos", "valor"].sum()),
        int(duplicates["linhas_duplicadas"]), int(duplicates["linhas_removidas"]),
        int(report.loc[changed, "valor"].sum()),
    )
