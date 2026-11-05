"""Padronização opcional e identificação de duplicados sem efeitos externos."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import math
import re

import pandas as pd

from .reader import ORIGIN_COLUMN, SheetData

TRIM_TEXT: str = "trim_texto"
NORMALIZE_NUMBERS: str = "normalizar_numeros"
DATES_ISO: str = "datas_iso"

_NUMBER_PATTERN = re.compile(r"-?(?:[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+)(?:,[0-9]+)?")
_DATE_FORMATS: tuple[tuple[str, str, bool], ...] = (
    (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "%d/%m/%Y", False),
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d", False),
    (r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", "%Y-%m-%d %H:%M:%S", True),
    (r"[0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}", "%d/%m/%Y %H:%M:%S", True),
)


@dataclass(frozen=True)
class QualityOptions:
    """Regras explícitas de qualidade de dados."""

    trim_text: bool = False
    normalize_numbers: bool = False
    dates_iso: bool = False
    key: tuple[str, ...] = ()
    remove_duplicates: bool = False

    @property
    def any_standardization(self) -> bool:
        """Indique se alguma regra de padronização está ativa."""
        return self.trim_text or self.normalize_numbers or self.dates_iso


@dataclass(frozen=True)
class ColumnStats:
    """Alterações acumuladas e falhas por regra em uma coluna."""

    changed: int = 0
    failed: dict[str, int] = field(default_factory=dict)
    changed_by_rule: dict[str, int] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class StandardizationResult:
    """Nova planilha e contadores por coluna."""

    sheet: SheetData
    stats: dict[str, ColumnStats]


@dataclass(frozen=True)
class DuplicateReport:
    """Contagens de duplicados para a política solicitada."""

    total: int
    removed: int
    mode: str


def _normalize_number(value: str) -> int | float:
    """Converta somente números nos formatos brasileiros aceitos."""
    stripped = value.strip()
    if _NUMBER_PATTERN.fullmatch(stripped) is None:
        raise ValueError("Formato numérico não suportado")
    normalized = stripped.replace(".", "").replace(",", ".")
    if "," not in stripped:
        return int(normalized)
    result = float(normalized)
    if not math.isfinite(result):
        raise ValueError("Número fora do intervalo finito")
    return result


def _parse_date(value: str) -> date | datetime:
    """Converta datas apenas nos formatos explícitos, com ano completo."""
    for pattern, date_format, has_time in _DATE_FORMATS:
        if re.fullmatch(pattern, value) is not None:
            parsed = datetime.strptime(value, date_format)
            return parsed if has_time else parsed.date()
    raise ValueError("Formato de data não suportado")


def standardize(sheet: SheetData, options: QualityOptions) -> StandardizationResult:
    """Aplique regras em ordem e conte falhas apenas em células sem conversão."""
    changes = {column: 0 for column in sheet.columns}
    failures: dict[str, dict[str, int]] = {column: {} for column in sheet.columns}
    rule_changes: dict[str, dict[str, int]] = {column: {} for column in sheet.columns}
    rows: list[tuple[object, ...]] = []
    for row in sheet.rows:
        values: list[object] = []
        for column, original in zip(sheet.columns, row, strict=True):
            value = original
            cell_changes = 0
            converted = False
            cell_failures: list[str] = []
            if options.trim_text and isinstance(value, str):
                trimmed = value.strip()
                if trimmed != value:
                    rule_changes[column][TRIM_TEXT] = rule_changes[column].get(TRIM_TEXT, 0) + 1
                cell_changes += int(trimmed != value)
                value = trimmed
            for enabled, rule, converter in (
                (options.normalize_numbers, NORMALIZE_NUMBERS, _normalize_number),
                (options.dates_iso, DATES_ISO, _parse_date),
            ):
                if enabled and isinstance(value, str) and value.strip():
                    try:
                        value = converter(value)
                    except ValueError:
                        cell_failures.append(rule)
                    else:
                        converted = True
                        cell_changes += 1
                        rule_changes[column][rule] = rule_changes[column].get(rule, 0) + 1
            changes[column] += cell_changes
            if not converted:
                for rule in cell_failures:
                    failures[column][rule] = failures[column].get(rule, 0) + 1
            values.append(value)
        rows.append(tuple(values))
    result_sheet = SheetData(sheet.path, sheet.columns, tuple(rows))
    stats = {
        column: ColumnStats(changes[column], failures[column], rule_changes[column])
        for column in sheet.columns
    }
    return StandardizationResult(result_sheet, stats)


def find_duplicates(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series:
    """Marque ocorrências duplicadas posteriores à primeira."""
    return frame.duplicated(subset=list(columns), keep="first")


def build_duplicate_report(frame: pd.DataFrame, options: QualityOptions) -> DuplicateReport:
    """Conte duplicados por chave ou por linha sem a coluna de origem."""
    columns = options.key or tuple(column for column in frame.columns if column != ORIGIN_COLUMN)
    total = int(find_duplicates(frame, columns).sum())
    mode = "chave:" + ",".join(options.key) if options.key else "linhas_identicas"
    return DuplicateReport(total, total if options.remove_duplicates else 0, mode)
