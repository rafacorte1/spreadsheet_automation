"""Carregamento validado de configuração TOML e overrides explícitos."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tomllib

from .errors import ConsolidationError
from .quality import QualityOptions

CONFIG_FILENAME: str = "config.toml"
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidado.xlsx")
DEFAULT_LOG_FILE: Path = Path("data/output/consolidacao.log")

_QUALITY_KEYS = {
    "trim_texto": "trim_text",
    "normalizar_numeros": "normalize_numbers",
    "datas_iso": "dates_iso",
    "remover_duplicados": "remove_duplicates",
    "chave": "key",
}
_PATH_KEYS = {"input": "input_dir", "output": "output_path", "log_file": "log_file"}


@dataclass(frozen=True)
class RuntimeConfig:
    """Caminhos e opções efetivos para uma execução."""

    input_dir: Path
    output_path: Path
    log_file: Path
    options: QualityOptions


def _type_error(key: str, expected: str, value: object) -> ConsolidationError:
    return ConsolidationError(
        f"Chave '{key}': esperado {expected}; recebido {type(value).__name__} ({value!r})"
    )


def load_config(path: Path | None = None) -> RuntimeConfig:
    """Leia o arquivo indicado ou a configuração opcional do diretório atual."""
    config = RuntimeConfig(DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_LOG_FILE, QualityOptions())
    optional = path is None
    config_path = Path(CONFIG_FILENAME) if optional else path
    assert config_path is not None
    try:
        with config_path.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as exc:
        if optional:
            return config
        raise ConsolidationError(f"Erro ao ler configuração '{config_path}': {exc}") from exc
    except (OSError, ValueError) as exc:
        raise ConsolidationError(f"Erro ao ler configuração '{config_path}': {exc}") from exc

    quality = data.get("qualidade", {})
    unknown = set(data) - {*_PATH_KEYS, "qualidade"}
    if isinstance(quality, dict):
        unknown.update(f"qualidade.{key}" for key in quality.keys() - _QUALITY_KEYS.keys())
    if unknown:
        raise ConsolidationError("Chaves desconhecidas: " + ", ".join(sorted(unknown)))
    if not isinstance(quality, dict):
        raise _type_error("qualidade", "tabela (dict)", quality)

    paths: dict[str, Path] = {}
    for key, field in _PATH_KEYS.items():
        if key in data:
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise _type_error(key, "str não vazia", value)
            parsed = Path(value)
            paths[field] = parsed if parsed.is_absolute() else config_path.absolute().parent / parsed

    options: dict[str, object] = {}
    for key, value in quality.items():
        name = f"qualidade.{key}"
        if key == "chave":
            if not isinstance(value, list):
                raise _type_error(name, "lista de str não vazias", value)
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise _type_error(name, "lista de str não vazias (item str não vazia)", item)
            options["key"] = tuple(value)
        else:
            if not isinstance(value, bool):
                raise _type_error(name, "bool", value)
            options[_QUALITY_KEYS[key]] = value
    return replace(config, **paths, options=replace(config.options, **options))


def apply_overrides(config: RuntimeConfig, **overrides: object) -> RuntimeConfig:
    """Aplique valores explícitos sobre arquivo e defaults sem mutação."""
    path_fields = set(_PATH_KEYS.values())
    quality_fields = set(_QUALITY_KEYS.values())
    unknown = overrides.keys() - path_fields - quality_fields
    if unknown:
        raise TypeError("Overrides desconhecidos: " + ", ".join(sorted(unknown)))
    paths = {key: value for key, value in overrides.items() if key in path_fields and value is not None}
    options = {key: value for key, value in overrides.items() if key in quality_fields and value is not None}
    return replace(config, **paths, options=replace(config.options, **options))
