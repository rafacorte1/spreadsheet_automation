"""Validated TOML configuration loading and explicit overrides."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tomllib

from .errors import ConsolidationError
from .quality import QualityOptions

CONFIG_FILENAME: str = "config.toml"
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidated.xlsx")
DEFAULT_LOG_FILE: Path = Path("data/output/consolidation.log")

_QUALITY_KEYS: tuple[str, ...] = (
    "trim_text", "normalize_numbers", "dates_iso", "remove_duplicates", "key",
)
_PATH_KEYS = {"input": "input_dir", "output": "output_path", "log_file": "log_file"}


@dataclass(frozen=True)
class RuntimeConfig:
    """Effective paths and options for one run."""

    input_dir: Path
    output_path: Path
    log_file: Path
    options: QualityOptions


def _type_error(key: str, expected: str, value: object) -> ConsolidationError:
    return ConsolidationError(
        f"key '{key}': expected {expected}; got {type(value).__name__} ({value!r})"
    )


def load_config(path: Path | None = None) -> RuntimeConfig:
    """Read the given file or the optional configuration of the current directory."""
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
        raise ConsolidationError(f"error reading configuration '{config_path}': {exc}") from exc
    except (OSError, ValueError) as exc:
        raise ConsolidationError(f"error reading configuration '{config_path}': {exc}") from exc

    quality = data.get("quality", {})
    unknown = set(data) - {*_PATH_KEYS, "quality"}
    if isinstance(quality, dict):
        unknown.update(f"quality.{key}" for key in quality.keys() - set(_QUALITY_KEYS))
    if unknown:
        raise ConsolidationError("unknown keys: " + ", ".join(sorted(unknown)))
    if not isinstance(quality, dict):
        raise _type_error("quality", "table (dict)", quality)

    paths: dict[str, Path] = {}
    for key, field in _PATH_KEYS.items():
        if key in data:
            value = data[key]
            if not isinstance(value, str) or not value.strip():
                raise _type_error(key, "non-empty str", value)
            parsed = Path(value)
            paths[field] = parsed if parsed.is_absolute() else config_path.absolute().parent / parsed

    options: dict[str, object] = {}
    for key, value in quality.items():
        name = f"quality.{key}"
        if key == "key":
            if not isinstance(value, list):
                raise _type_error(name, "list of non-empty str", value)
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise _type_error(name, "list of non-empty str (each item a non-empty str)", item)
            options["key"] = tuple(value)
        else:
            if not isinstance(value, bool):
                raise _type_error(name, "bool", value)
            options[key] = value
    return replace(config, **paths, options=replace(config.options, **options))


def apply_overrides(config: RuntimeConfig, **overrides: object) -> RuntimeConfig:
    """Apply explicit values over file and defaults without mutation."""
    path_fields = set(_PATH_KEYS.values())
    quality_fields = set(_QUALITY_KEYS)
    unknown = overrides.keys() - path_fields - quality_fields
    if unknown:
        raise TypeError("unknown overrides: " + ", ".join(sorted(unknown)))
    paths = {key: value for key, value in overrides.items() if key in path_fields and value is not None}
    options = {key: value for key, value in overrides.items() if key in quality_fields and value is not None}
    return replace(config, **paths, options=replace(config.options, **options))
