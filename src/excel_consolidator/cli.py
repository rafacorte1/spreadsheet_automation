"""Interface de linha de comando da consolidação."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .consolidator import ConsolidationResult, consolidate
from .errors import ConsolidationError
from .writer import write_atomic

DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidado.xlsx")


def build_parser() -> argparse.ArgumentParser:
    """Defina os caminhos de entrada e saída da CLI."""
    parser = argparse.ArgumentParser(description="Consolide planilhas .xlsx verticalmente.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, metavar="DIR")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, metavar="PATH")
    return parser


def run(input_dir: Path, output_path: Path) -> ConsolidationResult:
    """Consolide entradas validadas e publique o resultado atomicamente."""
    result = consolidate(input_dir)
    write_atomic(result.frame, output_path)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI e retorne seu código de saída."""
    args = build_parser().parse_args(argv)
    try:
        result = run(args.input, args.output)
    except ConsolidationError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(f"arquivos: {len(result.files)}")
    print(f"linhas: {result.rows}")
    print(f"saida: {args.output.resolve()}")
    return 0
