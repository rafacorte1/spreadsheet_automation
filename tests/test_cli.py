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
    assert captured.out == f"arquivos: 1\nlinhas: 2\nsaida: {output.resolve()}\nqualidade: nulos=0 duplicados=0 removidos=0 alterados=0\n"
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


def test_quality_flags_and_final_rows(tmp_path, make_xlsx, capsys):
    from openpyxl import load_workbook
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A", "B"], [" x ", None], ["x", None]])
    output = tmp_path / "out.xlsx"
    assert main(["--input", str(folder), "--output", str(output), "--trim-texto", "--remover-duplicados"]) == 0
    assert capsys.readouterr().out == f"arquivos: 1\nlinhas: 1\nsaida: {output}\nqualidade: nulos=2 duplicados=1 removidos=1 alterados=1\n"
    workbook = load_workbook(output)
    try:
        assert workbook["consolidado"]["A2"].value == "x"
    finally:
        workbook.close()


@pytest.mark.parametrize("key", ["missing", "", ",", "arquivo_origem"])
def test_invalid_key_preserves_output(tmp_path, make_xlsx, capsys, key):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A"], [1]])
    output = tmp_path / "out.xlsx"
    output.write_bytes(b"previous")
    assert main(["--input", str(folder), "--output", str(output), "--chave", key]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("erro: ")
    assert "chave" in captured.err
    assert "Traceback" not in captured.err
    assert output.read_bytes() == b"previous"


def test_key_spaces_and_empty_entries(tmp_path, make_xlsx, capsys):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A", "B"], [1, "x"], [1, "y"]])
    assert main(["--input", str(folder), "--output", str(tmp_path / "out.xlsx"),
                 "--chave", " , A, ,", "--remover-duplicados"]) == 0
    assert "linhas: 1\n" in capsys.readouterr().out
