"""Interface de linha de comando da consolidação."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .consolidator import ConsolidationResult, consolidate
from .errors import ConsolidationError
from .writer import write_atomic
from .quality import QualityOptions
from .report import summarize

DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidado.xlsx")


def build_parser() -> argparse.ArgumentParser:
    """Defina os caminhos de entrada e saída da CLI."""
    parser = argparse.ArgumentParser(description="Consolide planilhas .xlsx verticalmente.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, metavar="DIR")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, metavar="PATH")
    parser.add_argument("--trim-texto", action="store_true")
    parser.add_argument("--normalizar-numeros", action="store_true")
    parser.add_argument("--datas-iso", action="store_true")
    parser.add_argument("--chave", metavar="COL1,COL2")
    parser.add_argument("--remover-duplicados", action="store_true")
    return parser


def run(input_dir: Path, output_path: Path, options: QualityOptions | None = None) -> ConsolidationResult:
    """Consolide entradas validadas e publique o resultado atomicamente."""
    result = consolidate(input_dir, options)
    write_atomic(result.frame, output_path, result.report)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI e retorne seu código de saída."""
    args = build_parser().parse_args(argv)
    try:
        key = tuple(part.strip() for part in args.chave.split(",") if part.strip()) if args.chave is not None else ()
        if args.chave is not None and not key:
            raise ConsolidationError("chave vazia: informe pelo menos uma coluna")
        options = QualityOptions(args.trim_texto, args.normalizar_numeros, args.datas_iso, key, args.remover_duplicados)
        result = run(args.input, args.output, options)
    except ConsolidationError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"arquivos: {len(result.files)}")
    print(f"linhas: {result.rows}")
    print(f"saida: {args.output.resolve()}")
    summary = summarize(result.report)
    print(f"qualidade: nulos={summary.nulls} duplicados={summary.duplicates} removidos={summary.removed} alterados={summary.changed}")
    return 0
