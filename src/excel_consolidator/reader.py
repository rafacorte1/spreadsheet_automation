"""Descoberta e leitura de entradas sem modificar os arquivos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from .errors import ConsolidationError

ORIGIN_COLUMN: str = "arquivo_origem"
HEADER_REJECTED_SUFFIX: str = ".xlsx"


@dataclass(frozen=True)
class SheetData:
    """Conteúdo bruto da primeira aba de um arquivo."""

    path: Path
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]


def discover_input_files(input_dir: Path) -> list[Path]:
    """Liste entradas diretamente no diretório, ordenadas pelo nome."""
    if not input_dir.exists():
        return []
    return sorted(
        (path for path in input_dir.glob("*.xlsx")
         if path.is_file() and not path.name.startswith("~$")),
        key=lambda path: path.name,
    )


def _is_empty(value: object) -> bool:
    return value is None or value == ""


def read_sheet(path: Path) -> SheetData:
    """Leia a primeira aba e valide cabeçalhos e largura dos registros."""
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            sheet = workbook.worksheets[0]
            # Sem padding pela dimensão global: ela pode incluir dados excedentes.
            lines = sheet.iter_rows(values_only=True)
            header = next((row for row in lines if any(
                not _is_empty(value) for value in row
            )), None)
            if header is None:
                raise ConsolidationError(f"{path}: sem cabeçalho.")
            # openpyxl completa cada linha até a maior coluna da aba.
            width = len(header)
            while width and header[width - 1] is None:
                width -= 1
            header = header[:width]
            if any(value is None or not str(value).strip() for value in header):
                raise ConsolidationError(f"{path}: cabeçalho em branco.")
            columns = tuple(str(value) for value in header)
            if len(set(columns)) != len(columns):
                raise ConsolidationError(f"{path}: cabeçalhos duplicados.")
            if ORIGIN_COLUMN in columns:
                raise ConsolidationError(f"{path}: coluna reservada {ORIGIN_COLUMN}.")

            rows: list[tuple[object, ...]] = []
            for row in lines:
                if any(not _is_empty(value) for value in row[width:]):
                    raise ConsolidationError(
                        f"{path}: valor além da última coluna do cabeçalho."
                    )
                rows.append(tuple(row[:width]) + (None,) * max(0, width - len(row)))
            while rows and all(_is_empty(value) for value in rows[-1]):
                rows.pop()
            if not rows:
                raise ConsolidationError(f"{path}: sem linhas de dados.")
            return SheetData(path, columns, tuple(rows))
        finally:
            workbook.close()
    except ConsolidationError:
        raise
    except Exception as exc:
        raise ConsolidationError(f"Não foi possível ler {path}: {exc}") from exc


def validate_headers(reference: SheetData, candidate: SheetData) -> None:
    """Compare os nomes literalmente, independentemente da ordem."""
    missing = sorted(set(reference.columns) - set(candidate.columns))
    extra = sorted(set(candidate.columns) - set(reference.columns))
    if missing or extra:
        raise ConsolidationError(
            f"{candidate.path}: colunas faltantes: {missing}; excedentes: {extra}."
        )
