# Codex spec — Sprint 1, Etapa B (consolidação + escrita atômica + CLI + README)

Repo: /home/hermes/spreadsheet_automation. A Etapa A está aprovada: `reader.py` já existe com `discover_input_files`, `read_sheet`, `validate_headers`, `SheetData`, `ORIGIN_COLUMN`, `ConsolidationError`. **Não reescreva nem relaxe a API do reader**; só a consuma.

OBJETIVO: fechar o Sprint 1 — consolidar verticalmente os `.xlsx` de `data/input`, gravar `data/output/consolidado.xlsx` de forma atômica e entregar a CLI `python -m excel_consolidator`, com testes de aceite e README.

## NÃO FAÇA

- não altere `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- não altere a assinatura pública de `reader.py` (ajustes internos mínimos são permitidos só se um teste de aceite exigir; relate se acontecer)
- nada de `git add`, `git commit` ou `git push`
- sem dependência nova; não crie outro virtualenv; não instale pacotes além do que já está no `.venv`
- não implemente nada de Sprint 2 (normalização, dedup, relatório de qualidade) nem Sprint 3 (configuração, logs, agendamento)
- não escreva números/contagens de teste no código de produção

## ENTREGÁVEIS

1) `src/excel_consolidator/consolidator.py`

```python
@dataclass(frozen=True)
class ConsolidationResult:
    files: tuple[SheetData, ...]
    frame: pd.DataFrame          # colunas do 1º arquivo + ORIGIN_COLUMN ao final
    @property
    def rows(self) -> int

def consolidate(input_dir: Path) -> ConsolidationResult
```

- `discover_input_files` -> se lista vazia, `ConsolidationError("nenhum arquivo .xlsx em <dir>")`.
- Lê todos os arquivos com `read_sheet`; o **primeiro** (ordem alfabética) é a referência de ordem de colunas; `validate_headers` para todos os demais.
- Reordena as colunas de cada arquivo para a ordem do primeiro; concatena verticalmente **sem deduplicar**.
- Adiciona `arquivo_origem` com **apenas o nome do arquivo** (`path.name`), não o caminho.
- `frame` com `ignore_index=True`; preserve os valores crus (sem cast de tipo, sem conversão de `None`, sem arredondamento). Ordene para que a coluna `arquivo_origem` seja a última.

2) `src/excel_consolidator/writer.py`

```python
def write_atomic(frame: pd.DataFrame, output_path: Path) -> None
```

- Cria o diretório de saída se não existir (`parents=True, exist_ok=True`).
- Grava primeiro em arquivo temporário **no mesmo diretório** do destino (use `tempfile.mkstemp(dir=output_path.parent, suffix=".xlsx")`), aba única chamada `consolidado`, cabeçalho na linha 1, sem índice do pandas.
- Só depois de o arquivo temporário estar fechado e completo, `os.replace(temp, output_path)` (substituição atômica no mesmo filesystem).
- Em qualquer exceção durante a escrita, remova o temporário e re-lance a exceção como `ConsolidationError` citando `output_path`. O arquivo de saída anterior deve permanecer byte a byte intacto quando a escrita falhar.

3) `src/excel_consolidator/cli.py` + `src/excel_consolidator/__main__.py`

```python
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidado.xlsx")

def build_parser() -> argparse.ArgumentParser
def run(input_dir: Path, output_path: Path) -> ConsolidationResult
def main(argv: Sequence[str] | None = None) -> int
```

- Flags: `--input DIR` (default `DEFAULT_INPUT`), `--output PATH` (default `DEFAULT_OUTPUT`).
- `main` retorna `0` em sucesso; em `ConsolidationError` imprime `erro: <mensagem>` em **stderr** e retorna `1`; não deixa traceback vazar. Erro de argumento continua sendo do argparse (código 2).
- Sucesso imprime em stdout, exatamente neste formato:
  ```
  arquivos: <n>
  linhas: <total>
  saida: <caminho absoluto do arquivo gerado>
  ```
- `python -m excel_consolidator` chama `main()` e sai com o código retornado (`raise SystemExit(main())`).

4) Testes em `tests/` (pytest, dados sintéticos em `tmp_path`):

- `tests/test_consolidator.py`: concatenação vertical com colunas em ordens diferentes (todas as linhas, ordem de colunas do 1º arquivo, `arquivo_origem` = nome do arquivo); ordem alfabética determinística; diretório vazio -> erro; colisão de `arquivo_origem` -> erro; nenhum arquivo de entrada alterado (compare bytes antes/depois).
- `tests/test_writer.py`: arquivo gerado tem uma aba, cabeçalho na linha 1 e mesmas células/valores do frame; diretório de saída inexistente é criado; nenhum `.xlsx` temporário sobra no diretório após sucesso **e** após falha forçada (force falha, por exemplo com um frame que faça `os.replace` falhar via monkeypatch, e confirme que o conteúdo anterior do destino não mudou).
- `tests/test_cli.py`: sucesso imprime as três linhas no formato e retorna 0; erro de entrada retorna 1, escreve em stderr e **não cria/sobrescreve** a saída; `--input`/`--output` são respeitados.
- `tests/test_end_to_end.py`: cenário completo com 2 planilhas de colunas trocadas -> `data/output/consolidado.xlsx` (em `tmp_path`) com linhas corretas; e cenário "resultado anterior permanece intacto": gera saída válida, depois roda de novo com um insumo corrompido e confirma que o arquivo anterior não mudou byte a byte e que o comando falhou com código != 0.

5) `README.md` — reescreva o arquivo (hoje tem uma linha): o que faz, requisitos (Python >= 3.11), instalação (`python -m venv .venv`, `pip install -e ".[dev]"`), estrutura de pastas, uso com `python -m excel_consolidator [--input DIR] [--output PATH]`, exemplo de saída, como rodar os testes (`.venv/bin/python -m pytest tests -q`), decisões de projeto (leitura via openpyxl para não perder cabeçalhos duplicados/em branco; comparação literal de cabeçalhos; escrita atômica) e **limitações do Sprint 1**: só `.xlsx` e primeira aba, entradas com fórmula sem valor em cache são lidas como vazias (`data_only=True`), sem `.xls`/`.csv`, sem normalização/dedup/validação de valores, sem agendamento.

## CRITÉRIO DE ACEITE

- `arquivo_origem` contém só o nome do arquivo.
- Nenhuma linha perdida: total de linhas de saída = soma das linhas de dados de todos os arquivos de entrada.
- Falha em qualquer etapa não altera `data/output/consolidado.xlsx` existente e não deixa temporários.
- Arquivos de entrada byte a byte inalterados.

## REGRAS

- Interpretador e testes: `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pip install -e . -q` se precisar reinstalar.
- Código legível, tipado (`from __future__ import annotations`), docstrings curtas, constantes nomeadas.
- **Se um teste não passar, corrija o código; nunca relaxe o teste.**
- Ao final, cole a saída real do pytest e um exemplo real de execução da CLI com dados sintéticos (com a contagem de linhas resultante).
- Relate: arquivos criados/alterados, comandos reais, saída do pytest, saída da CLI.
