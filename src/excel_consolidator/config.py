"""Validated TOML configuration loading and explicit overrides."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tomllib

from .errors import ConsolidationError
from .quality import QualityOptions
from .reader_options import ReaderOptions

CONFIG_FILENAME: str = "config.toml"
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidated.xlsx")
DEFAULT_LOG_FILE: Path = Path("data/output/consolidation.log")
DEFAULT_OUTPUT_FORMAT: str = "xlsx"
OUTPUT_FORMATS: tuple[str, ...] = ("xlsx", "csv", "both")

_QUALITY_KEYS: tuple[str, ...] = (
    "trim_text", "normalize_numbers", "dates_iso", "remove_duplicates", "key",
)
_PATH_KEYS = {"input": "input_dir", "output": "output_path", "log_file": "log_file"}
_RUN_FIELDS = {*_PATH_KEYS.values(), "output_format"}
_CSV_KEYS = {"encoding", "delimiter"}
_READER_FIELDS = {"formats", "csv_encoding", "csv_delimiter"}


@dataclass(frozen=True)
class RuntimeConfig:
    """Effective paths and options for one run."""

    input_dir: Path
    output_path: Path
    log_file: Path
    options: QualityOptions
    reader_options: ReaderOptions = ReaderOptions()
    output_format: str = DEFAULT_OUTPUT_FORMAT

    def __post_init__(self) -> None:
        _validate_output_format(self.output_format)

    @property
    def outputs(self) -> dict[str, Path]:
        """Return the destinations for this run."""
        return output_paths(self.output_path, self.output_format)


def _type_error(key: str, expected: str, value: object) -> ConsolidationError:
    return ConsolidationError(
        f"key '{key}': expected {expected}; got {type(value).__name__} ({value!r})"
    )


def _validate_output_format(value: object) -> None:
    if not isinstance(value, str):
        raise _type_error("output_format", "str", value)
    if value not in OUTPUT_FORMATS:
        raise ConsolidationError(
            f"key 'output_format': expected one of {', '.join(OUTPUT_FORMATS)}; got {value!r}"
        )


def output_paths(output: Path, output_format: str) -> dict[str, Path]:
    """Derive the export paths from the primary destination and chosen format."""
    _validate_output_format(output_format)
    if output_format == "xlsx":
        return {"xlsx": output}
    report = output.parent / f"{output.stem}_report.csv"
    if output_format == "csv":
        return {"csv": output, "report": report}
    if not output.name.endswith(".xlsx"):
        raise ConsolidationError("--output must end in .xlsx when output_format is 'both'")
    return {"xlsx": output, "csv": output.parent / f"{output.stem}.csv", "report": report}


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
    csv = data.get("csv", {})
    unknown = set(data) - {*_PATH_KEYS, "quality", "formats", "csv", "output_format"}
    if isinstance(quality, dict):
        unknown.update(f"quality.{key}" for key in quality.keys() - set(_QUALITY_KEYS))
    if isinstance(csv, dict):
        unknown.update(f"csv.{key}" for key in csv.keys() - _CSV_KEYS)
    if unknown:
        raise ConsolidationError("unknown keys: " + ", ".join(sorted(unknown)))
    if not isinstance(quality, dict):
        raise _type_error("quality", "table (dict)", quality)
    if not isinstance(csv, dict):
        raise _type_error("csv", "table (dict)", csv)

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
    reader: dict[str, object] = {}
    if "formats" in data:
        formats = data["formats"]
        if not isinstance(formats, list) or any(not isinstance(item, str) for item in formats):
            raise _type_error("formats", "list of str", formats)
        reader["formats"] = tuple(formats)
    for key, value in csv.items():
        if not isinstance(value, str):
            raise _type_error(f"csv.{key}", "str", value)
        reader[f"csv_{key}"] = value
    return replace(config, **paths, options=replace(config.options, **options),
                   reader_options=replace(config.reader_options, **reader),
                   output_format=data.get("output_format", config.output_format))


def apply_overrides(config: RuntimeConfig, **overrides: object) -> RuntimeConfig:
    """Apply explicit values over file and defaults without mutation."""
    quality_fields = set(_QUALITY_KEYS)
    unknown = overrides.keys() - _RUN_FIELDS - quality_fields - _READER_FIELDS
    if unknown:
        raise TypeError("unknown overrides: " + ", ".join(sorted(unknown)))
    fields = {key: value for key, value in overrides.items() if key in _RUN_FIELDS and value is not None}
    options = {key: value for key, value in overrides.items() if key in quality_fields and value is not None}
    reader = {key: value for key, value in overrides.items() if key in _READER_FIELDS and value is not None}
    return replace(config, **fields, options=replace(config.options, **options),
                   reader_options=replace(config.reader_options, **reader))
