# Codex spec — Sprint 1, Etapa A (esqueleto + leitura/validação)

Repo: /home/hermes/spreadsheet_automation (git já iniciado, branch main). Trabalhe no root do repo.

OBJETIVO: entregar o esqueleto do pacote `excel_consolidator` e a camada de leitura/validação de `.xlsx`, com testes pytest passando. NÃO implemente consolidação, escrita de saída nem CLI nesta etapa (etapa B cuida disso).

## NÃO FAÇA

- não crie `consolidator.py`, `writer.py` nem `cli.py`; não escreva nada em `data/output/`
- não modifique `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `README.md`
- nada de `git add`, `git commit` ou `git push`
- sem dependência nova (use pandas, openpyxl, pytest que já estão no `.venv`)
- não crie outro virtualenv, não instale pacotes

## CONTEXTO OBRIGATÓRIO (leia antes)

- `SPEC.md` -> Sprint 1, requisitos 1, 2, 3 e 5 (descoberta de arquivos, primeira aba, validação de cabeçalhos, colisão de `arquivo_origem`) e itens 8/9 (erros controlados, não alterar entrada).
- Interpretador: `/home/hermes/spreadsheet_automation/.venv/bin/python` (Python 3.14, pandas 3.1.1, openpyxl 3.1.5, pytest 9.2.0).

## ENTREGÁVEIS

1) `pyproject.toml` — setuptools, `name = "excel-consolidator"`, `requires-python = ">=3.11"`, deps `pandas`, `openpyxl`; extra `dev` com `pytest`; layout `src/`; package `excel_consolidator`; **sem** console script ainda.

2) `src/excel_consolidator/__init__.py` — exporta `ConsolidationError`.

3) `src/excel_consolidator/errors.py`:

```python
class ConsolidationError(Exception):
    """Erro de entrada/validação com mensagem exibível ao usuário."""
```

4) `src/excel_consolidator/reader.py` — API pública exata:

```python
ORIGIN_COLUMN: str = "arquivo_origem"
HEADER_REJECTED_SUFFIX: str = ".xlsx"

@dataclass(frozen=True)
class SheetData:
    path: Path
    columns: tuple[str, ...]      # cabeçalho na ordem do arquivo
    rows: tuple[tuple[object, ...], ...]  # só linhas de dados, len == len(columns)

def discover_input_files(input_dir: Path) -> list[Path]
def read_sheet(path: Path) -> SheetData
def validate_headers(reference: SheetData, candidate: SheetData) -> None
```

Regras de comportamento (obrigatórias):

- `discover_input_files`: arquivos `*.xlsx` **diretamente** em `input_dir`, sem recursão; ignora nomes que começam com `~$`; ignora diretórios; retorna em ordem alfabética determinística por nome de arquivo (`sorted(..., key=lambda p: p.name)`); diretório inexistente ou vazio -> retorna `[]` sem exceção (quem trata ausência é a etapa B).
- `read_sheet`: lê **somente a primeira aba** via `openpyxl.load_workbook(path, read_only=True, data_only=True)` (use `values_only=True` para iterar). Todos os cabeçalhos e células são tratados como dados crus do openpyxl.
- Cabeçalho = primeira linha não vazia da aba. Cada célula precisa ser `str` não vazia depois de `str(value)`; célula `None`, `""` ou `"   "` -> `ConsolidationError` com o nome do arquivo no texto.
- Nomes **comparados literalmente**, sem strip, sem casefold, sem remoção de acento. Não normalizar nada.
- Cabeçalhos duplicados no mesmo arquivo (após conversão para `str`) -> `ConsolidationError`.
- Coluna chamada exatamente `arquivo_origem` -> `ConsolidationError` (colisão com a coluna que a etapa B adiciona).
- Linhas de dados: todas as linhas após o cabeçalho; descarte **apenas** linhas totalmente vazias no fim da aba. Linhas curtas são completadas com `None`. Linha com valor não vazio além da última coluna do cabeçalho -> `ConsolidationError`.
- Arquivo sem nenhuma linha de dados -> `ConsolidationError` (mensagem "sem linhas de dados").
- Arquivo que não abre (não é zip/xlsx, corrompido, protegido por senha) -> `ConsolidationError` embrulhando a causa; a mensagem deve conter o caminho do arquivo. Não deixar vazar `zipfile.BadZipFile`/`openpyxl.utils.exceptions.InvalidFileException`.
- Não escrever, mover ou apagar arquivos de entrada (abrir em read_only).
- `validate_headers`: conjuntos de nomes iguais, ordem irrelevante, comparação literal. Se faltarem colunas em `candidate` ou sobrarem colunas não presentes em `reference`, `ConsolidationError` listando as colunas faltantes e as excedentes e o caminho do arquivo candidato.

5) `tests/test_reader.py` — cobre, no mínimo: descoberta ordenada ignorando `~$` e não-`.xlsx`; diretório vazio; leitura com cabeçalho válido; cabeçalho em branco; cabeçalho duplicado; cabeçalho com coluna `arquivo_origem`; arquivo corrompido (bytes lixo com extensão `.xlsx`); arquivo só com cabeçalho; linhas curtas completadas com `None`; cabeçalhos com mesma ordem trocada passando em `validate_headers`; cabeçalhos incompatíveis falhando com mensagem que cita a coluna divergente. Crie as planilhas de teste com `openpyxl` em `tmp_path`.

6) `tests/conftest.py` se ajudar (helpers de criação de xlsx). Use dados sintéticos apenas.

7) `.gitignore` — `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `data/output/*.xlsx`.

8) `data/input/.gitkeep` e `data/output/.gitkeep`.

## REGRAS

- Código legível, tipado (use `from __future__ import annotations`), docstrings curtas, sem números mágicos.
- Sem dependência nova, sem arquivo novo fora de `src/excel_consolidator/`, `tests/`, `data/`, `pyproject.toml`, `.gitignore`.
- Ao final rode, com o interpretador do `.venv`:
  `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pip install -e . -q && .venv/bin/python -m pytest tests -q`
- **Se um teste não passar, corrija o código, nunca relaxe o teste.** Cole a saída real do pytest no relatório final.
- Relate: arquivos criados, comandos executados e resultado real.
