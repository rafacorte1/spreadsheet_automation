"""Configuration with synthetic files and temporary directories."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from excel_consolidator.config import (
    DEFAULT_INPUT, DEFAULT_LOG_FILE, DEFAULT_OUTPUT, RuntimeConfig,
    apply_overrides, load_config,
)
from excel_consolidator.errors import ConsolidationError
from excel_consolidator.quality import QualityOptions


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "settings.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config()
    assert config == RuntimeConfig(Path("data/input"), Path("data/output/consolidated.xlsx"),
                                   Path("data/output/consolidation.log"), QualityOptions())
    assert (DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_LOG_FILE) == (
        config.input_dir, config.output_path, config.log_file)
    with pytest.raises(FrozenInstanceError):
        config.input_dir = Path("other")


def test_complete(tmp_path: Path) -> None:
    path = write_config(tmp_path, '''input = "in"
output = "out.xlsx"
log_file = "run.log"
[quality]
trim_text = true
normalize_numbers = true
dates_iso = true
remove_duplicates = true
key = ["product", "date"]
''')
    assert load_config(path) == RuntimeConfig(
        tmp_path / "in", tmp_path / "out.xlsx", tmp_path / "run.log",
        QualityOptions(True, True, True, ("product", "date"), True))


def test_only_input(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, 'input = "data_dir"'))
    assert config == RuntimeConfig(tmp_path / "data_dir", DEFAULT_OUTPUT, DEFAULT_LOG_FILE, QualityOptions())


@pytest.mark.parametrize("text, options", [
    ('[quality]\nkey = ["a"]\ntrim_text = true', QualityOptions(trim_text=True, key=("a",))),
    ('[quality]\nkey = []', QualityOptions()),
    ('[quality]', QualityOptions()),
])
def test_partial_quality(tmp_path: Path, text: str, options: QualityOptions) -> None:
    assert load_config(write_config(tmp_path, text)).options == options


@pytest.mark.parametrize("text, key, expected, received", [
    ('input = 5', 'input', 'str', 'int'),
    ('output = false', 'output', 'str', 'bool'),
    ('log_file = []', 'log_file', 'str', 'list'),
    ('input = ""', 'input', 'non-empty str', 'str'),
    ('[quality]\ntrim_text = "yes"', 'trim_text', 'bool', 'str'),
    ('[quality]\nnormalize_numbers = 1', 'normalize_numbers', 'bool', 'int'),
    ('[quality]\ndates_iso = 0', 'dates_iso', 'bool', 'int'),
    ('[quality]\nremove_duplicates = "false"', 'remove_duplicates', 'bool', 'str'),
    ('[quality]\nkey = "product"', 'key', 'list', 'str'),
    ('[quality]\nkey = [1]', 'key', 'str', 'int'),
    ('[quality]\nkey = [""]', 'key', 'non-empty str', 'str'),
    ('quality = false', 'quality', 'table', 'bool'),
])
def test_invalid_types(tmp_path: Path, text: str, key: str, expected: str, received: str) -> None:
    with pytest.raises(ConsolidationError) as error:
        load_config(write_config(tmp_path, text))
    message = str(error.value)
    assert key in message
    assert expected in message
    assert f"got {received}" in message


@pytest.mark.parametrize("text, keys", [
    ('typo = 1\nother = 2', ('typo', 'other')),
    ('[quality]\ntrim_txt = true', ('quality.trim_txt',)),
    ('typo = 1\n[quality]\nother = true', ('typo', 'quality.other')),
])
def test_unknown_keys(tmp_path: Path, text: str, keys: tuple[str, ...]) -> None:
    with pytest.raises(ConsolidationError) as error:
        load_config(write_config(tmp_path, text))
    assert all(key in str(error.value) for key in keys)


def test_missing_explicit(tmp_path: Path) -> None:
    path = tmp_path / "missing.toml"
    with pytest.raises(ConsolidationError, match=str(path)):
        load_config(path)


def test_invalid_toml(tmp_path: Path) -> None:
    path = write_config(tmp_path, 'input = [')
    with pytest.raises(ConsolidationError, match=str(path)) as error:
        load_config(path)
    assert error.value.__cause__ is not None


def test_unreadable(tmp_path: Path) -> None:
    with pytest.raises(ConsolidationError, match=str(tmp_path)) as error:
        load_config(tmp_path)
    assert isinstance(error.value.__cause__, OSError)


def test_invalid_encoding(tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    path.write_bytes(b'input = "\xff"')
    with pytest.raises(ConsolidationError, match=str(path)):
        load_config(path)


def test_relative_to_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    write_config(sub, 'input = "data_dir"')
    monkeypatch.chdir(tmp_path)
    assert load_config(Path("sub/settings.toml")).input_dir == sub / "data_dir"


def test_absolute_paths(tmp_path: Path) -> None:
    absolute = tmp_path / "data_dir"
    path = write_config(tmp_path, f'input = "{absolute}"\noutput = "{absolute}"\nlog_file = "{absolute}"')
    config = load_config(path)
    assert (config.input_dir, config.output_path, config.log_file) == (absolute,) * 3


def test_cwd_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.toml").write_text('input = "auto"', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert load_config().input_dir == tmp_path / "auto"


def test_overrides(tmp_path: Path) -> None:
    original = load_config(write_config(tmp_path, 'input = "file"\n[quality]\ntrim_text = true'))
    result = apply_overrides(original, input_dir=Path("cli"), output_path=Path("cli.xlsx"),
                             log_file=Path("cli.log"), trim_text=False, normalize_numbers=True,
                             dates_iso=True, key=("a",), remove_duplicates=True)
    assert result == RuntimeConfig(Path("cli"), Path("cli.xlsx"), Path("cli.log"),
                                   QualityOptions(False, True, True, ("a",), True))
    assert original.input_dir == tmp_path / "file"
    assert original.options == QualityOptions(trim_text=True)
    assert apply_overrides(original, **dict.fromkeys((
        "input_dir", "output_path", "log_file", "trim_text", "normalize_numbers",
        "dates_iso", "key", "remove_duplicates"))) == original
    assert apply_overrides(original) is not original
    with pytest.raises(TypeError, match="typo"):
        apply_overrides(original, typo=None)
