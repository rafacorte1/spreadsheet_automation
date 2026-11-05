# Codex spec — Sprint 2, Etapa C (módulo de qualidade puro + testes)

Repo: /home/hermes/spreadsheet_automation. Sprint 1 está aprovado e commitado (`e0e5d36`); `reader.py`, `consolidator.py`, `writer.py`, `cli.py` existem e não devem ser tocados nesta etapa.

OBJETIVO: criar `quality.py` com padronização opcional (contagem de alterações e falhas por coluna) e detecção de duplicados, mais testes. Nenhuma mudança de CLI, consolidador, writer ou README nesta etapa.

## NÃO FAÇA

- não altere `reader.py`, `consolidator.py`, `writer.py`, `cli.py`, `__main__.py` (etapa D cuida disso)
- não altere `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `README.md`
- nada de `git add`, `git commit`, `git push`
- sem dependência nova (pandas, openpyxl, pytest já instalados)
- não implemente casefold, remoção de acentos, dedup sem flag, log ou configuração externa
- nada de transformação silenciosa: valor que a regra não conseguir converter deve **ficar intocado** e ser contado como falha

## ENTREGÁVEIS

1) `src/excel_consolidator/quality.py`

```python
TRIM_TEXT: str = "trim_texto"
NORMALIZE_NUMBERS: str = "normalizar_numeros"
DATES_ISO: str = "datas_iso"

@dataclass(frozen=True)
class QualityOptions:
    trim_text: bool = False
    normalize_numbers: bool = False
    dates_iso: bool = False
    key: tuple[str, ...] = ()           # vazio = comparação por linha inteira
    remove_duplicates: bool = False

    @property
    def any_standardization(self) -> bool

@dataclass(frozen=True)
class ColumnStats:
    changed: int = 0                    # valores alterados, somando todas as regras ativas
    failed: dict[str, int] = ...        # regra -> quantidade de valores não convertidos

@dataclass(frozen=True)
class StandardizationResult:
    sheet: SheetData
    stats: dict[str, ColumnStats]       # chave = nome da coluna

def standardize(sheet: SheetData, options: QualityOptions) -> StandardizationResult
def find_duplicates(frame: pd.DataFrame, columns: Sequence[str]) -> pd.Series  # máscara bool
def build_duplicate_report(frame, options) -> DuplicateReport   # opcional; use se ajudar
```

Regras de padronização (aplicar **somente** quando a flag correspondente estiver ligada; ordem fixa por célula: trim -> números -> datas):

- `trim_texto`: só em `str`; remove espaço/tab/quebra nas pontas (use `str.strip()`). Conta como alterado apenas quando o resultado difere do original.
- `normalizar_numeros`: só em `str`. Aceita, depois de `strip()`:
  - pt-BR com milhar: `1.234,56`, `-1.234`, `12.345.678,9`
  - pt-BR sem milhar: `1234,56`, `-12,5`
  - inteiro simples: `42`, `-7`
  - O retorno é `int` quando não há parte decimal e `float` quando há. Nada de `Decimal`/`NaN` no dado.
  - `R$`, `$`, parênteses negativos, notação científica e sufixos não são suportados: contam como falha e o valor **permanece a string original**.
  - String que não casa com nenhum padrão: falha, valor intocado.
- `datas_iso`: só em `str`. Formatos aceitos, tentados em ordem: `%d/%m/%Y`, `%Y-%m-%d`, `%Y-%m-%d %H:%M:%S`, `%d/%m/%Y %H:%M:%S`. Retorno `datetime.date` (ou `datetime.datetime` quando houver hora). Qualquer outro texto: falha, valor intocado. Não invente formatos; sem ano de 2 dígitos (ambíguo).
- Célula que não é `str` (número, `None`, `bool`, data do openpyxl) nunca é tocada por nenhuma regra.
- `stats` deve ter uma entrada para **todas** as colunas da planilha (mesmo com 0 alterações), para o relatório ficar estável.
- Nunca mutar o `SheetData` recebido: devolva um novo `SheetData` com as linhas transformadas.

Duplicados:

- `find_duplicates(frame, columns)`: usa `frame.duplicated(subset=list(columns), keep="first")`; `None` conta como igual a `None`. A máscara marca, para cada grupo, todas as linhas **exceto a primeira ocorrência**.
- `build_duplicate_report`: se `options.key` estiver vazio, compara a linha inteira **excluindo** `ORIGIN_COLUMN` (linha idêntica em arquivos diferentes é duplicada); se houver `key`, compara só essas colunas. Retorne contagens: `total` (linhas duplicadas), `removed` (igual a `total` quando `remove_duplicates` é True, senão 0) e o modo usado (`"linhas_identicas"` ou `"chave:" + ",".join(key)`).

2) `tests/test_quality.py` — cobrir no mínimo:

- sem flags: `standardize` devolve linhas idênticas e `stats` com todas as colunas zeradas
- trim: altera só strings com espaço nas pontas, não toca número/`None`/data; conta alterações corretamente; `"  a  b  "` -> `"a  b"`
- números: `"1.234,56"` -> `1234.56`; `"1.234"` -> `1234` (int); `"-12,5"` -> `-12.5`; `"42"` -> `42` int; `"12.345.678,9"` -> `12345678.9`
- números com falha: `"R$ 1.234,56"`, `"abc"`, `"1,2,3"`, `"1.23.456"` -> valor original preservado e contagem de falha incrementada
- datas: `"05/11/2026"` -> `date(2026, 11, 5)`; `"2026-11-05"` -> `date(2026, 11, 5)`; `"2026-11-05 14:30:00"` -> `datetime(2026, 11, 5, 14, 30)`; `"31/02/2026"`, `"2026-13-01"`, `"05/11/26"` -> falha, intocado
- contagem por coluna independente (coluna com 2 alterações e outra com 1)
- `sheet` original não mutado
- duplicados por linha inteira: linhas iguais em arquivos diferentes são marcadas; a primeira ocorrência não é marcada; linhas diferentes em uma coluna não são marcadas
- duplicados por chave: `key=("nome",)` marca a segunda ocorrência mesmo com outras colunas diferentes
- `remove_duplicates=False` -> `removed == 0`; `True` -> `removed == total`
- `ORIGIN_COLUMN` não participa da comparação quando `key` está vazio

## REGRAS

- Interpretador/testes: `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- Tipado, `from __future__ import annotations`, docstrings curtas, constantes nomeadas, sem números mágicos.
- **Se um teste não passar, corrija o código; nunca relaxe o teste.** Não altere os 36 testes do Sprint 1.
- Cole a saída real do pytest (contagem total incluindo os testes antigos) e relate arquivos criados.
