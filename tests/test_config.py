"""Configuração com arquivos sintéticos e diretórios temporários."""
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
    assert config == RuntimeConfig(Path("data/input"), Path("data/output/consolidado.xlsx"),
                                   Path("data/output/consolidacao.log"), QualityOptions())
    assert (DEFAULT_INPUT, DEFAULT_OUTPUT, DEFAULT_LOG_FILE) == (
        config.input_dir, config.output_path, config.log_file)
    with pytest.raises(FrozenInstanceError):
        config.input_dir = Path("other")


def test_complete(tmp_path: Path) -> None:
    path = write_config(tmp_path, '''input = "in"
output = "out.xlsx"
log_file = "run.log"
[qualidade]
trim_texto = true
normalizar_numeros = true
datas_iso = true
remover_duplicados = true
chave = ["produto", "data"]
''')
    assert load_config(path) == RuntimeConfig(
        tmp_path / "in", tmp_path / "out.xlsx", tmp_path / "run.log",
        QualityOptions(True, True, True, ("produto", "data"), True))


def test_only_input(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path, 'input = "dados"'))
    assert config == RuntimeConfig(tmp_path / "dados", DEFAULT_OUTPUT, DEFAULT_LOG_FILE, QualityOptions())


@pytest.mark.parametrize("text, options", [
    ('[qualidade]\nchave = ["a"]\ntrim_texto = true', QualityOptions(trim_text=True, key=("a",))),
    ('[qualidade]\nchave = []', QualityOptions()),
    ('[qualidade]', QualityOptions()),
])
def test_partial_quality(tmp_path: Path, text: str, options: QualityOptions) -> None:
    assert load_config(write_config(tmp_path, text)).options == options


@pytest.mark.parametrize("text, key, expected, received", [
    ('input = 5', 'input', 'str', 'int'),
    ('output = false', 'output', 'str', 'bool'),
    ('log_file = []', 'log_file', 'str', 'list'),
    ('input = ""', 'input', 'str não vazia', 'str'),
    ('[qualidade]\ntrim_texto = "sim"', 'trim_texto', 'bool', 'str'),
    ('[qualidade]\nnormalizar_numeros = 1', 'normalizar_numeros', 'bool', 'int'),
    ('[qualidade]\ndatas_iso = 0', 'datas_iso', 'bool', 'int'),
    ('[qualidade]\nremover_duplicados = "false"', 'remover_duplicados', 'bool', 'str'),
    ('[qualidade]\nchave = "produto"', 'chave', 'lista', 'str'),
    ('[qualidade]\nchave = [1]', 'chave', 'str', 'int'),
    ('[qualidade]\nchave = [""]', 'chave', 'str não vazia', 'str'),
    ('qualidade = false', 'qualidade', 'tabela', 'bool'),
])
def test_invalid_types(tmp_path: Path, text: str, key: str, expected: str, received: str) -> None:
    with pytest.raises(ConsolidationError) as error:
        load_config(write_config(tmp_path, text))
    message = str(error.value)
    assert key in message
    assert expected in message
    assert f"recebido {received}" in message


@pytest.mark.parametrize("text, keys", [
    ('typo = 1\nother = 2', ('typo', 'other')),
    ('[qualidade]\ntrim_text = true', ('qualidade.trim_text',)),
    ('typo = 1\n[qualidade]\nother = true', ('typo', 'qualidade.other')),
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
    write_config(sub, 'input = "dados"')
    monkeypatch.chdir(tmp_path)
    assert load_config(Path("sub/settings.toml")).input_dir == sub / "dados"


def test_absolute_paths(tmp_path: Path) -> None:
    absolute = tmp_path / "dados"
    path = write_config(tmp_path, f'input = "{absolute}"\noutput = "{absolute}"\nlog_file = "{absolute}"')
    config = load_config(path)
    assert (config.input_dir, config.output_path, config.log_file) == (absolute,) * 3


def test_cwd_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.toml").write_text('input = "auto"', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert load_config().input_dir == tmp_path / "auto"


def test_overrides(tmp_path: Path) -> None:
    original = load_config(write_config(tmp_path, 'input = "file"\n[qualidade]\ntrim_texto = true'))
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
