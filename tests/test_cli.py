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
    assert args.input is None
    assert args.output is None


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


@pytest.mark.parametrize("key", ["", ","])
def test_empty_key_preserves_output(tmp_path, make_xlsx, capsys, key):
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


@pytest.mark.parametrize("key", ["missing", "arquivo_origem"])
def test_unknown_key_without_removal_is_warned(tmp_path, make_xlsx, capsys, key):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A"], [1]])
    output = tmp_path / "out.xlsx"
    assert main(["--input", str(folder), "--output", str(output), "--chave", key]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "linhas: 1" in captured.out
    log = (tmp_path / "data/output/consolidacao.log").read_text()
    assert "WARNING chave" in log and "ignorada" in log and "linhas_identicas" in log


def test_key_spaces_and_empty_entries(tmp_path, make_xlsx, capsys):
    folder = tmp_path / "input"
    make_xlsx(folder / "a.xlsx", [["A", "B"], [1, "x"], [1, "y"]])
    assert main(["--input", str(folder), "--output", str(tmp_path / "out.xlsx"),
                 "--chave", " , A, ,", "--remover-duplicados"]) == 0
    assert "linhas: 1\n" in capsys.readouterr().out


def test_config_flags_and_overrides(tmp_path, make_xlsx, capsys):
    from openpyxl import load_workbook
    make_xlsx(tmp_path / 'input' / 'a.xlsx', [['A'], [' x '], ['x']])
    make_xlsx(tmp_path / 'other' / 'b.xlsx', [['A'], [' y ']])
    config = tmp_path / 'config.toml'
    config.write_text('input="input"\noutput="out.xlsx"\nlog_file="configured.log"\n[qualidade]\ntrim_texto=true\nnormalizar_numeros=true\ndatas_iso=true\nremover_duplicados=true\nchave=["A"]\n')
    assert main(['--config', str(config)]) == 0
    assert capsys.readouterr().out == f'arquivos: 1\nlinhas: 1\nsaida: {tmp_path / "out.xlsx"}\nqualidade: nulos=0 duplicados=1 removidos=1 alterados=1\n'
    explicit = tmp_path / 'explicit.log'
    assert main(['--config', str(config), '--input', str(tmp_path / 'other'), '--log-file', str(explicit)]) == 0
    assert 'flags=trim_texto,normalizar_numeros,datas_iso,remover_duplicados chave=A' in explicit.read_text()
    book = load_workbook(tmp_path / 'out.xlsx')
    try:
        assert book['consolidado']['A2'].value == 'y'
    finally:
        book.close()


@pytest.mark.parametrize('contents, message', [(None, 'missing.toml'), ('unknown=true', 'unknown')])
def test_config_error(tmp_path, capsys, contents, message):
    config = tmp_path / 'missing.toml'
    if contents is not None:
        config.write_text(contents)
    assert main(['--config', str(config), '--output', str(tmp_path / 'out.xlsx')]) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert message in captured.err
    assert not (tmp_path / 'out.xlsx').exists()


def test_default_config_and_error_log(tmp_path, make_xlsx, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    make_xlsx(tmp_path / 'data/input/a.xlsx', [['A'], [1]])
    assert main([]) == 0
    assert len(capsys.readouterr().out.splitlines()) == 4
    log = tmp_path / 'data/output/consolidacao.log'
    assert len(log.read_text().splitlines()) == 3
    assert main(['--input', 'missing']) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'ERROR erro=' in log.read_text()
    assert 'missing' in captured.err


def test_unknown_key_without_removal_warns_in_log(tmp_path, make_xlsx, capsys):
    make_xlsx(tmp_path / 'input/a.xlsx', [['produto'], ['Mouse']])
    assert main(['--input', str(tmp_path / 'input'), '--output', str(tmp_path / 'out.xlsx'),
                 '--chave', 'data']) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert captured.out.splitlines() == [
        'arquivos: 1', 'linhas: 1', f'saida: {(tmp_path / "out.xlsx").resolve()}',
        'qualidade: nulos=0 duplicados=0 removidos=0 alterados=0',
    ]
    log = (tmp_path / 'data/output/consolidacao.log').read_text()
    assert 'WARNING chave (\'data\',) ignorada' in log
    assert 'linhas_identicas' in log


def test_unknown_key_with_removal_fails(tmp_path, make_xlsx, capsys):
    make_xlsx(tmp_path / 'input/a.xlsx', [['produto'], ['Mouse']])
    assert main(['--input', str(tmp_path / 'input'), '--output', str(tmp_path / 'out.xlsx'),
                 '--chave', 'data', '--remover-duplicados']) == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'colunas desconhecidas' in captured.err
    assert not (tmp_path / 'out.xlsx').exists()
