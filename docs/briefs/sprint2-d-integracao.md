# Codex spec — Sprint 2, Etapa D (relatório, integração e CLI)

Repo: /home/hermes/spreadsheet_automation. Sprint 1 (commit `e0e5d36`) e Etapa C (`quality.py`, 95 testes) estão aprovados. Integre a qualidade de dados na consolidação e na CLI.

## NÃO FAÇA

- não altere `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- não altere `reader.py` nem o comportamento documentado do Sprint 1 (validação literal de cabeçalhos, coluna reservada, escrita atômica, entradas intocadas)
- não implemente casefold, remoção de acentos, log, config externa ou agendamento
- sem dependência nova, sem `git add/commit/push`
- não invente números de aceite no código de produção

## 1) `src/excel_consolidator/report.py`

```python
REPORT_SHEET: str = "relatorio"
REPORT_COLUMNS: tuple[str, ...] = ("secao", "arquivo", "coluna", "metrica", "valor")

@dataclass(frozen=True)
class QualitySummary:
    nulls: int
    duplicates: int
    removed: int
    changed: int

def count_nulls(sheet: SheetData) -> dict[str, int]        # coluna -> nulos (None ou "")
def build_report(
    sheets: Sequence[SheetData],                            # já padronizadas
    stats: Mapping[str, Mapping[str, ColumnStats]],         # nome do arquivo -> coluna -> stats
    duplicates: DuplicateReport,
    options: QualityOptions,
) -> pd.DataFrame
def summarize(report: pd.DataFrame) -> QualitySummary
```

Layout do `relatorio` (colunas exatas `secao, arquivo, coluna, metrica, valor`), nesta ordem de seções, arquivos em ordem alfabética e colunas na ordem da planilha:

- `("resumo", arquivo, "", "linhas_lidas", n)` — uma linha por arquivo
- `("nulos", arquivo, coluna, "nulos", n)` — todas as colunas, inclusive zero
- `("padronizacao", arquivo, coluna, "alterados_<regra>", n)` e `("padronizacao", arquivo, coluna, "falhas_<regra>", n)` — **somente** para regras ativas em `options`, todas as colunas, inclusive zero
- `("duplicados", "", "", "modo", "<linhas_identicas|chave:a,b>")`
- `("duplicados", "", "", "linhas_duplicadas", n)`
- `("duplicados", "", "", "linhas_removidas", n)`

`nulos` = `None` ou `str` vazia/`"   "`, contado no dado **após** padronização e **antes** de remover duplicados, apenas nas colunas de dados (nunca em `ORIGIN_COLUMN`). `summarize` soma a seção `nulos`, lê as três linhas de `duplicados` e soma `alterados_*` da seção `padronizacao`.

## 2) `src/excel_consolidator/writer.py`

Mude para:

```python
def write_atomic(frame: pd.DataFrame, output_path: Path, report: pd.DataFrame | None = None) -> None
```

Mesma atomicidade do Sprint 1 (temporário no diretório do destino + `os.replace`, limpeza em falha). Aba `consolidado` primeiro; se `report` não for `None`, aba `relatorio` com `REPORT_COLUMNS` na ordem. `write_atomic(frame, output)` deve continuar funcionando e gerar **uma única** aba (os testes do Sprint 1 dependem disso).

## 3) `src/excel_consolidator/consolidator.py`

```python
def consolidate(input_dir: Path, options: QualityOptions | None = None) -> ConsolidationResult

@dataclass(frozen=True)
class ConsolidationResult:
    files: tuple[SheetData, ...]      # planilhas já padronizadas
    frame: pd.DataFrame               # dados finais (após remoção de duplicados, se pedida)
    report: pd.DataFrame
    options: QualityOptions
    @property
    def rows(self) -> int
```

Fluxo: descobrir -> ler -> padronizar (só se `options.any_standardization`) -> validar cabeçalhos -> montar frames na ordem do primeiro arquivo + `arquivo_origem` -> concatenar -> contar duplicados -> remover se `options.remove_duplicates` (mantendo a primeira ocorrência na ordem de arquivo/linha) -> montar relatório com os dados **antes** da remoção para as contagens de nulos e duplicados.

Validação de `options.key`: se alguma coluna da chave não existir nas colunas de dados do primeiro arquivo, `ConsolidationError` listando as colunas desconhecidas (mensagem contendo a chave e o diretório/arquivo de referência). Duplicados comparam as colunas da chave, sem `ORIGIN_COLUMN`.

## 4) `src/excel_consolidator/cli.py`

Flags novas: `--trim-texto`, `--normalizar-numeros`, `--datas-iso`, `--chave COL1,COL2`, `--remover-duplicados` (todas off por padrão). `--chave` aceita espaços e remove entradas vazias; `--chave ""` ou `--chave ,` -> `ConsolidationError`.

Stdout em sucesso, exatamente:

```
arquivos: <n>
linhas: <linhas do arquivo final>
saida: <caminho absoluto>
qualidade: nulos=<X> duplicados=<Y> removidos=<Z> alterados=<W>
```

`linhas` reflete o arquivo final (após remoção). Em `ConsolidationError`: `erro: <mensagem>` em stderr, código 1, sem traceback, sem tocar a saída anterior.

## 5) Testes

`tests/test_report.py`: layout exato (colunas e ordem das seções) para um cenário fixo; nulos contados só em dados e excluindo `arquivo_origem`; `None` e `"   "` contam; seções de padronização ausentes quando nenhuma regra está ativa; `summarize` fechando com as contagens.

`tests/test_consolidator.py` (adicione, sem quebrar os 4 existentes): `consolidate` sem opções = mesmas linhas do Sprint 1; `--chave` inválida -> `ConsolidationError` citando a coluna; remoção mantém a primeira ocorrência; `report` contém `linhas_lidas` por arquivo.

`tests/test_cli.py` (adicione): linha `qualidade:` com os quatro números corretos em um cenário com nulo, duplicado e padronização; `--trim-texto` alterando dado na saída; `--remover-duplicados` reduzindo `linhas`; `--chave` inválida -> exit 1 com stderr e saída anterior intacta; sem flags -> contadores zerados quando os dados estão limpos.

`tests/test_end_to_end.py` (adicione um teste, preserve o existente): duas planilhas com um nulo, uma linha duplicada entre arquivos e um valor `" 1.234,56 "`; rodar com `--trim-texto --normalizar-numeros --remover-duplicados` e conferir **na planilha gerada** os valores, as duas abas e o relatório; rodar de novo sem flags e conferir que o dado volta ao original.

## 6) `README.md`

Adicione: as flags novas com exemplo de uso, o formato da aba `relatorio`, a definição de `linhas` (saída final) vs `linhas_lidas` (entrada), a regra de que valor não convertido fica intocado e é contado como falha, e as limitações novas (sem casefold/acentos; sem dedup por semelhança; `"007"` vira `7` com `--normalizar-numeros`).

## REGRAS

- `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- **Se um teste não passar, corrija o código; nunca relaxe o teste.** Não remova nem enfraqueça testes existentes; se um formato de stdout mudou, atualize a asserção para o formato novo especificado acima.
- Cole a saída real do pytest e uma execução real da CLI com dados sintéticos mostrando as quatro linhas de stdout.
