# Codex spec — Sprint 3, correção (testes sujam o log real)

Repo: /home/hermes/spreadsheet_automation. 153 testes passam, mas a suíte grava no arquivo de log de produção.

## DEFEITO

`tests/test_cli.py`, `tests/test_end_to_end.py` e `tests/test_runlog.py` chamam `main()` sem `--log-file`. Como o default é `data/output/consolidacao.log` relativo ao CWD, rodar `pytest` da raiz do repositório cria e preenche `data/output/consolidacao.log` com dezenas de entradas de teste (`pytest-of-hermes/...`). O log de execuções reais fica contaminado.

Evidência real: após `pytest tests -q` da raiz, `data/output/consolidacao.log` contém linhas com caminhos `.../pytest-of-hermes/pytest-N/...`.

## CORREÇÃO ESPERADA

1. `tests/conftest.py`: fixture autouse, com escopo de função, que roda cada teste dentro de um diretório temporário próprio (ex.: `monkeypatch.chdir(tmp_path)`), de modo que nenhum caminho default relativo ao CWD caia dentro do repositório. Os testes existentes já recebem `tmp_path` e usam caminhos absolutos; ajuste o que quebrar sem enfraquecer asserção.
2. Garanta que testes que dependem de `config.toml` no CWD continuem válidos (eles já usam `monkeypatch.chdir` ou `tmp_path`).
3. Não use `--log-file` escondido dentro de `main` nem mude o default de produção. A correção é no isolamento dos testes.
4. Remova o arquivo `data/output/consolidacao.log` do repositório (é gerado, não versionado).

## NÃO FAÇA

- não altere `src/` em absoluto (`reader.py`, `quality.py`, `report.py`, `writer.py`, `consolidator.py`, `config.py`, `runlog.py`, `cli.py`, `__main__.py`)
- não altere `README.md`, `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- sem dependência nova; sem `git add/commit/push`
- não relaxe nenhuma asserção existente

## VERIFICAÇÃO OBRIGATÓRIA (cole a saída real)

```bash
cd /home/hermes/spreadsheet_automation
rm -f data/output/consolidacao.log
.venv/bin/python -m pytest tests -q
ls -la data/output/ ; test ! -e data/output/consolidacao.log && echo "log de produção intocado"
```

- `pytest` com todos os testes passando
- `data/output/consolidacao.log` **não** deve existir depois da suíte
- relate quais testes precisaram de ajuste e por quê
