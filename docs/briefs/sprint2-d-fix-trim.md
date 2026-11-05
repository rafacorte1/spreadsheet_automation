# Codex spec — Sprint 2, correção 2 da Etapa C (falha engolida pelo trim)

Repo: /home/hermes/spreadsheet_automation. Corrija apenas `src/excel_consolidator/quality.py` e adicione testes em `tests/test_quality.py`.

## DEFEITO

Em `standardize`, a gravação de falhas está condicionada a `if not cell_changes:`. Como `trim_texto` também incrementa `cell_changes`, uma célula que só foi aparada perde as falhas de conversão.

Reprodução:
```python
s = SheetData(Path("a.xlsx"), ("Nome",), (("  Ana  ",),))
standardize(s, QualityOptions(trim_text=True, normalize_numbers=True, dates_iso=True)).stats["Nome"]
# hoje: ColumnStats(changed=1, failed={}, changed_by_rule={'trim_texto': 1})
# correto: ColumnStats(changed=1, failed={'normalizar_numeros': 1, 'datas_iso': 1}, changed_by_rule={'trim_texto': 1})
```

`"Ana"` (aparado de `"  Ana  "`) não é número nem data: as duas conversões falharam e o relatório precisa dizer isso.

## REGRA CORRETA

A supressão de falha existe só para célula que uma regra de **conversão** (`normalizar_numeros` ou `datas_iso`) converteu com sucesso. Portanto:

- marque `converted = True` apenas quando um converter retornar valor (não quando trim alterar a string);
- registre as falhas acumuladas da célula quando `converted` for `False`, independentemente de trim ter alterado a célula;
- `changed` e `changed_by_rule` continuam como estão (trim + conversão na mesma célula somam 2).

Não altere o comportamento de string vazia/só espaços: elas continuam não sendo tentadas por conversores e não contam falha.

## TESTES A ADICIONAR (não remova nem relaxe os existentes)

1. `("  Ana  ",)` com `trim_text=True, normalize_numbers=True, dates_iso=True` -> valor `"Ana"`, `changed == 1`, `changed_by_rule == {'trim_texto': 1}`, `failed == {'normalizar_numeros': 1, 'datas_iso': 1}`.
2. `(" 42 ",)` com as três flags (caso já coberto) continua `changed == 2` e `failed == {}`.
3. `(" 05/11/2026 ",)` com as três flags -> `date(2026, 11, 5)`, `changed == 2`, `failed == {}`.
4. `(" abc ",)` com as três flags -> `"abc"`, `changed == 1`, `failed` com as duas regras.
5. Coluna mista `[("  Ana  ",), ("1.234,56",), ("",)]` com as três flags -> `changed == 4` (2 de trim + 1 de número + 0), `failed == {'normalizar_numeros': 1, 'datas_iso': 1}` (só a célula `"Ana"`), e o relatório com `falhas_*` coerentes.

## NÃO FAÇA

- não altere `reader.py`, `report.py`, `writer.py`, `consolidator.py`, `cli.py`, `README.md` nem os outros testes
- não mude assinaturas públicas
- sem dependência nova, sem `git add/commit/push`

## REGRAS

- `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- **Se um teste não passar, corrija o código; nunca relaxe o teste.**
- Cole a saída real do pytest (contagem total) e o trecho de código que mudou.
