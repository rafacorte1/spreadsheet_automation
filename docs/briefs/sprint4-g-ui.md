# Brief — Sprint 4: interface customtkinter

Aprovado pelo PO nesta sessão. Este brief registra o que foi pedido e com quais critérios foi aceito.

## Decisões do PO

1. Abas: **Resumo + Relatório + Log**.
2. `config.toml` é carregado ao abrir a janela, com botão **Recarregar config**.
3. A UI **grava log em arquivo**, no caminho do config, igual à CLI.

## Escopo entregue

- `ui/controller.py`: `FormFields`, `build_config`, `load_base`, `split_key`, `read_log_tail`, `format_summary`, `run_from_fields` → `RunOutcome`. Sem importar tkinter.
- `ui/app.py`: campos de caminho (entrada, saída, log) com "Procurar", quatro interruptores de qualidade, campo de chave, botões Consolidar / Recarregar config / Abrir pasta de saída, barra de progresso, status, e as abas Resumo (texto), Relatório (Treeview com `secao, arquivo, coluna, metrica, valor`) e Log (rabo do arquivo + Atualizar).
- `ui/__main__.py`: `python -m excel_consolidator.ui`, com `--config PATH` opcional.
- `pyproject.toml`: extra opcional `ui = ["customtkinter>=5.2"]`.

## Critérios de aceite e evidência

| Critério | Evidência |
|---|---|
| Suíte verde, incluindo controller sem abrir janela | `pytest tests -q` → 179 passed |
| `python -m excel_consolidator.ui` abre a janela | processo sobe sem erro; janela "Excel Consolidator" 1024x752 visível na árvore de acessibilidade do macOS; captura de tela bloqueada pelo SO nesta máquina |
| Consolidar pela janela gera o mesmo resultado da CLI | `test_run_from_window_writes_output_and_fills_tabs`: 2 arquivos, 2 linhas, abas preenchidas, log com `gravado` |
| Erro mostra mensagem e preserva saída anterior | `test_error_is_shown_without_closing` + `test_error_preserves_previous_output` |
| Não congela durante a execução | execução em thread com resultado por `queue.Queue` + `after` |

## Fora de escopo

Empacotamento `.app`, ícone, agendamento, múltiplas abas de planilha, `.xls`/`.csv`, edição dos dados na tela.
