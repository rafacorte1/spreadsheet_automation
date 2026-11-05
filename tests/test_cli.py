"""Aceite dos argumentos, mensagens e códigos da CLI."""
from __future__ import annotations

import pytest

from excel_consolidator.cli import DEFAULT_INPUT, DEFAULT_OUTPUT, build_parser, main


def test_success_with_custom_paths(tmp_path, make_xlsx, capsys):
    folder = tmp_path / "custom"
    make_xlsx(folder / "a.xlsx", [["A"], [1], [2]])
    output = tmp_path / "export" / "custom.xlsx"
    assert main(["--input", str(folder), "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == f"arquivos: 1\nlinhas: 2\nsaida: {output.resolve()}\n"
    assert captured.err == ""
    assert output.is_file()


@pytest.mark.parametrize("existing", [False, True])
def test_input_error_preserves_output(tmp_path, capsys, existing):
    output = tmp_path / "result.xlsx"
    if existing:
        output.write_bytes(b"previous result")
    assert main(["--input", str(tmp_path / "missing"), "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"erro: nenhum arquivo .xlsx em {tmp_path / 'missing'}\n"
    assert "Traceback" not in captured.err
    assert output.read_bytes() == b"previous result" if existing else not output.exists()


def test_defaults():
    args = build_parser().parse_args([])
    assert args.input == DEFAULT_INPUT
    assert args.output == DEFAULT_OUTPUT


def test_argument_error(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--unknown"])
    assert caught.value.code == 2
    assert "error:" in capsys.readouterr().err
