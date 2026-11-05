"""Interface de linha de comando da consolidação."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import sys

from .config import DEFAULT_INPUT, DEFAULT_OUTPUT, RuntimeConfig, load_config, apply_overrides
from . import runlog
from .consolidator import ConsolidationResult, consolidate
from .errors import ConsolidationError
from .writer import write_atomic
from .quality import QualityOptions
from .report import summarize


def build_parser() -> argparse.ArgumentParser:
    """Defina os caminhos de entrada e saída da CLI."""
    parser = argparse.ArgumentParser(description="Consolide planilhas .xlsx verticalmente.")
    parser.add_argument("--input", type=Path, default=None, metavar="DIR")
    parser.add_argument("--output", type=Path, default=None, metavar="PATH")
    parser.add_argument("--trim-texto", action="store_true", default=None)
    parser.add_argument("--normalizar-numeros", action="store_true", default=None)
    parser.add_argument("--datas-iso", action="store_true", default=None)
    parser.add_argument("--chave", metavar="COL1,COL2")
    parser.add_argument("--remover-duplicados", action="store_true", default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--log-file", type=Path, default=None)
    return parser


def run(input_dir: Path, output_path: Path, options: QualityOptions | None = None) -> ConsolidationResult:
    """Consolide entradas validadas e publique o resultado atomicamente."""
    result = consolidate(input_dir, options)
    write_atomic(result.frame, output_path, result.report)
    return result


def run_config(config: RuntimeConfig) -> ConsolidationResult:
    """Execute a configuração sem logs nem saída de console."""
    return run(config.input_dir, config.output_path, config.options)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI e retorne seu código de saída."""
    args = build_parser().parse_args(argv)
    logger = None
    try:
        config = load_config(args.config)
        config = apply_overrides(
            config, input_dir=args.input, output_path=args.output, log_file=args.log_file,
            trim_text=args.trim_texto, normalize_numbers=args.normalizar_numeros,
            dates_iso=args.datas_iso, remove_duplicates=args.remover_duplicados,
        )
        logger = runlog.setup_logging(config.log_file, max_bytes=runlog.DEFAULT_MAX_BYTES,
                                      backup_count=runlog.DEFAULT_BACKUP_COUNT)
        if args.chave is not None:
            key = tuple(part.strip() for part in args.chave.split(",") if part.strip())
            if not key:
                raise ConsolidationError("chave vazia: informe pelo menos uma coluna")
            config = apply_overrides(config, key=key)
        options = config.options
        flags = ",".join(name for name, enabled in (
            ("trim_texto", options.trim_text), ("normalizar_numeros", options.normalize_numbers),
            ("datas_iso", options.dates_iso), ("remover_duplicados", options.remove_duplicates),
        ) if enabled) or "nenhum"
        logger.info("inicio input=%s output=%s flags=%s chave=%s",
                    config.input_dir.resolve(), config.output_path.resolve(), flags,
                    ",".join(options.key) or "-")
        result = run_config(config)
        for warning in result.warnings:
            logger.warning("%s", warning)
        lines_read = result.report.loc[result.report["metrica"] == "linhas_lidas", "valor"].sum()
        logger.info("leitura arquivos=%s linhas_lidas=%s", len(result.files), lines_read)
        summary = summarize(result.report)
        logger.info("gravado linhas=%s nulos=%s duplicados=%s removidos=%s alterados=%s saida=%s",
                    result.rows, summary.nulls, summary.duplicates, summary.removed,
                    summary.changed, config.output_path.resolve())
        print(f"arquivos: {len(result.files)}")
        print(f"linhas: {result.rows}")
        print(f"saida: {config.output_path.resolve()}")
        print(f"qualidade: nulos={summary.nulls} duplicados={summary.duplicates} removidos={summary.removed} alterados={summary.changed}")
        return 0
    except ConsolidationError as exc:
        if logger is not None:
            logger.error("erro=%s", exc)
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    finally:
        if logger is not None:
            runlog.close_logging(logger)
