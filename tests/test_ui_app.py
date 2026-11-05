"""Aceite da janela: monta a tela, executa e confere widgets. Pula sem display."""
from __future__ import annotations

import time
import tkinter

import pytest

pytest.importorskip("customtkinter")

from excel_consolidator.ui.app import App  # noqa: E402


@pytest.fixture
def app():
    try:
        instance = App()
    except tkinter.TclError as exc:
        pytest.skip(f"sem display para tkinter: {exc}")
    instance.withdraw()
    yield instance
    instance.destroy()


def pump_until_done(app: App, timeout: float = 30.0) -> None:
    """Rode o laço de eventos até a thread de trabalho entregar o resultado."""
    deadline = time.monotonic() + timeout
    while app.running and time.monotonic() < deadline:
        app.update()
        time.sleep(0.03)
    app.update()
    assert not app.running, "a execução não terminou no prazo"


def test_tabs_and_initial_fields(app):
    for name in ("Resumo", "Relatório", "Log"):
        app.tabs.set(name)
    assert app.tabs.get() == "Log"
    assert app.input_var.get() == "data/input"
    assert app.output_var.get() == "data/output/consolidado.xlsx"


def test_run_from_window_writes_output_and_fills_tabs(app, tmp_path, make_xlsx):
    make_xlsx(tmp_path / "entrada" / "a.xlsx", [["produto", "valor"], ["Mouse", 50]])
    make_xlsx(tmp_path / "entrada" / "b.xlsx", [["valor", "produto"], [100, "Teclado"]])
    app.input_var.set(str(tmp_path / "entrada"))
    app.output_var.set(str(tmp_path / "saida" / "consolidado.xlsx"))
    app.log_var.set(str(tmp_path / "saida" / "consolidacao.log"))
    app._start_run()
    pump_until_done(app)
    assert app.status.cget("text") == "concluído"
    assert (tmp_path / "saida" / "consolidado.xlsx").is_file()
    resumo = app.resumo_box.get("1.0", "end")
    assert "arquivos: 2" in resumo and "linhas: 2" in resumo
    assert len(app.report_tree.get_children()) == 9
    assert "gravado" in app.log_box.get("1.0", "end")
    assert app.consolidar.cget("state") == "normal"


def test_error_is_shown_without_closing(app, tmp_path):
    app.input_var.set(str(tmp_path / "inexistente"))
    app.output_var.set(str(tmp_path / "saida.xlsx"))
    app._start_run()
    pump_until_done(app)
    assert app.status.cget("text") == "falhou"
    assert app.resumo_box.get("1.0", "end").strip().startswith("erro: ")
    assert app.report_tree.get_children() == ()


def test_refresh_log_reads_file(app, tmp_path):
    log = tmp_path / "registro.log"
    log.write_text("linha um\nlinha dois\n", encoding="utf-8")
    app.log_var.set(str(log))
    app._refresh_log()
    assert app.log_box.get("1.0", "end").strip() == "linha um\nlinha dois"
