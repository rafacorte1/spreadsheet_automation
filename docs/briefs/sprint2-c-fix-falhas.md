# Codex spec — Sprint 2, correção da Etapa C (atribuição de falhas)

Repo: /home/hermes/spreadsheet_automation, branch main. `quality.py` e `tests/test_quality.py` existem e passam (81 testes).

Defeitos encontrados na revisão do Tech Lead. Corrija **somente** `src/excel_consolidator/quality.py` e adicione testes em `tests/test_quality.py`.

## DEFEITO 1 — falha falsa quando outra regra converteu a célula

Com `normalize_numbers=True` e `dates_iso=True`, a célula `"05/11/2026"` é convertida em `date` pela regra de datas, mas também registra `failed={'normalizar_numeros': 1}`.

Reprodução (hoje):
```python
standardize(sheet(["data"], [["05/11/2026"]]), QualityOptions(normalize_numbers=True, dates_iso=True)).stats
# {'data': ColumnStats(changed=1, failed={'normalizar_numeros': 1})}
```

Correto: nenhuma falha, porque a célula foi convertida. Regra: uma falha de uma regra só conta se **nenhuma** regra ativa converteu a célula; se qualquer regra converteu, `failed` daquela célula é vazio. A contagem de `changed` continua por regra (trim + número na mesma célula soma 2).

## DEFEITO 2 — string vazia conta como falha de conversão

`""` e `"   "` são células vazias, não valores não convertidos. Hoje `""` com `dates_iso=True` produz `failed={'datas_iso': 1}` e `""` com `normalize_numbers=True` produz `failed={'normalizar_numeros': 1}`.

Correto: valor `str` vazio ou só com espaços nunca é tentado por `normalizar_numeros` nem por `datas_iso` e nunca incrementa falha. Com `trim_texto` ativo, `"   "` -> `""` conta 1 alteração em `trim_texto` e nada mais.

## NÃO FAÇA

- não altere `reader.py`, `consolidator.py`, `writer.py`, `cli.py`, `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `README.md`
- não altere as assinaturas públicas (`QualityOptions`, `ColumnStats`, `StandardizationResult`, `standardize`, `find_duplicates`, `build_duplicate_report`)
- não relaxe nem remova nenhum teste existente; não mude o comportamento documentado de números/datas válidos
- sem dependência nova, sem `git add/commit/push`

## TESTES A ADICIONAR

1. `"05/11/2026"` com `normalize_numbers=True, dates_iso=True` -> `date(2026, 11, 5)`, `changed == 1`, `failed == {}`.
2. `"1.234,56"` com as duas regras -> `1234.56`, `changed == 1`, `failed == {}`.
3. `""` com `normalize_numbers=True` -> valor `""`, `changed == 0`, `failed == {}`.
4. `""` com `dates_iso=True` -> idem.
5. `"   "` com `trim_texto=True, dates_iso=True` -> valor `""`, `changed == 1`, `failed == {}`.
6. `"abc"` com as duas regras -> valor intocado, `changed == 0`, `failed == {'normalizar_numeros': 1, 'datas_iso': 1}` (nada converteu, ambas falharam).
7. Caso misto: coluna com `["05/11/2026", "abc"]` e as duas regras -> `changed == 1`, `failed['datas_iso'] == 1` e `failed['normalizar_numeros'] == 1` (a string `abc` falhou nas duas; a data converteu e não conta falha).

## REGRAS

- `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- **Se um teste não passar, corrija o código; nunca relaxe o teste.**
- Cole a saída real do pytest e relate o diff conceitual (o que mudou em `quality.py`).
