# Brief — Sprint 5: novos formatos de entrada (`.xls` legado e `.csv`)

Incremento aprovado pelo PO em 2026-11-18. Escopo fechado: **somente** leitura de `.xls` e `.csv` como entrada, com o `.xlsx` atual intacto. Não implemente nada do item "packaging" nem do teste de carga como funcionalidade (o benchmark é evidência, não código de produto).

Leia antes de começar: `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `docs/HANDOFF.md` e o código em `src/excel_consolidator/`.

## Contexto do produto

Ferramenta CLI + GUI que consolida verticalmente planilhas de uma pasta, preservando a origem de cada linha (`source_file`), com padronização opcional e relatório de qualidade. Hoje `reader.discover_input_files` só aceita `*.xlsx` e `reader.read_sheet` assume workbook com abas. O objetivo do sprint é consolidar também `.xls` legado (BIFF, o que bancos exportam) e `.csv` (o que sistemas exportam), na mesma pasta, mantendo as mesmas invariantes.

## Decisões já tomadas (não reabra)

1. **Formatos aceitos**: `xlsx`, `xls`, `csv`. Detecção por extensão, case-insensitive (`.XLSX` conta). Default: as três juntas. `--formats` / config restringem.
2. **`.xls` via `xlrd`** (runtime dependency, `xlrd>=2.0`). `xlwt` entra só em `[project.optional-dependencies] dev` para gerar fixtures nos testes.
3. **`.csv` com flags explícitas e detecção apenas como fallback**:
   - `--csv-encoding` (config `[csv].encoding`), default `utf-8`, com tentativa automática `utf-8-sig` → `utf-8` → `cp1252` **somente quando o usuário não informar encoding**.
   - `--csv-delimiter` (config `[csv].delimiter`), default automático. Candidatos, nesta ordem de desempate: `,` `;` `\t` `|`.
   - Quando detecção automática for usada, registre WARNING em `result.warnings` com arquivo e escolha (`csv <path>: encoding=cp1252 delimiter=';'`). Sem adivinhação silenciosa.
   - Encoding explícito com erro de decode = `ConsolidationError` nomeando arquivo e posição. Sem fallback quando explícito.
4. **Detecção de delimitador determinística**, regra exata a implementar: para cada candidato, parseie as primeiras 50 linhas não vazias com `csv.reader(delimiter=cand)`; o candidato é aceito só se **todas** essas linhas tiverem a **mesma largura** e essa largura for `> 1`. Se nenhum candidato for aceito, use `,` e registre WARNING. Se mais de um for aceito, escolha o de maior largura; empate → ordem `,` `;` `\t` `|`.
5. **Semântica de valores do CSV**: campo vazio vira `None` (igual a célula vazia do xlsx), campos ficam `str`, nenhuma inferência de tipo — `--normalize-numbers` e `--dates-iso` são o caminho para converter.
6. **Semântica de valores do `.xls`**: `XL_CELL_EMPTY`/`XL_CELL_BLANK` → `None`; `XL_CELL_TEXT` → `str` literal (sem strip); `XL_CELL_NUMBER` → `int` quando `float.is_integer()`, senão `float`; `XL_CELL_DATE` → `datetime` via `xlrd.xldate_as_datetime(value, datemode)`; `XL_CELL_BOOLEAN` → `bool`; `XL_CELL_ERROR` → `ConsolidationError` nomeando arquivo, linha e coluna.
7. **Mesmas invariantes dos sprints anteriores**: cabeçalho literal (sem normalização), `source_file` reservado, linha curta preenchida com `None`, valor além da última coluna de cabeçalho = erro, linhas vazias no fim descartadas, pelo menos 1 linha de dados, entradas não são modificadas, saída atômica.
8. **Contrato de stdout da CLI não muda**: continuam exatamente as 4 linhas `files:`, `rows:`, `output:`, `quality:`. Formato/encoding/delimiter vão para o log, não para o stdout.
9. **Config TOML**: novas chaves de topo `formats` (lista de str, valores em `{xlsx,xls,csv}`) e tabela `[csv]` com `encoding` (str) e `delimiter` (str de 1 caractere). Chave desconhecida ou tipo errado = `ConsolidationError`, como hoje. Precedência CLI > arquivo > default continua valendo.

## Arquitetura exigida

- `reader.py` mantém a API pública: `SheetData`, `discover_input_files(input_dir, formats)`, `read_sheet(path, csv_options)`, `validate_headers(reference, candidate)`, `ORIGIN_COLUMN`. `SheetData` ganha `warnings: tuple[str, ...] = ()`.
- Leitura de `.xlsx` continua em `reader.py`; crie `csv_reader.py` e `xls_reader.py` com função pública `read(path, csv_options) -> tuple[tuple[object, ...], list[tuple[object, ...]]]` (cabeçalho cru, linhas cruas), **sem importar `reader`** (evita ciclo). A validação comum (cabeçalho vazio/duplicado/reservado, largura, linhas vazias) fica num único lugar em `reader.py`, usada pelos três formatos — nada de duplicar regra.
- `ReaderOptions` (ou nome equivalente, documente) carrega `formats`, `csv_encoding`, `csv_delimiter` e é thread-safe/imutável; entra em `RuntimeConfig` e chega ao núcleo via `run_config`. `consolidator.consolidate` recebe essas opções e agrega os `warnings` dos arquivos em `ConsolidationResult.warnings`.
- GUI: campos de formato e CSV na janela (mesmo padrão dos campos atuais), filtros de arquivo nos diálogos incluindo `*.xls`/`*.csv`, e `ui/controller.py` continuando sem importar tkinter. Se um campo da GUI for ambíguo, use o mais simples e documente.

## Entregáveis

1. Código acima, tipado, docstrings em inglês, sem dependência nova além de `xlrd` (runtime) e `xlwt` (dev).
2. Testes novos, sintéticos, gerados em runtime (`.xls` via `xlwt`, `.csv` via `pathlib`), nos arquivos que você julgar adequados. Cobertura mínima obrigatória:
   - `.csv`: vírgula, ponto e vírgula com números pt-BR (`1.234,56`), tab, pipe; Latin-1 com acentos; BOM UTF-8; campo vazio → `None`; linha curta preenchida com `None`; linha com campo além do cabeçalho → erro; só cabeçalho → erro; cabeçalho duplicado → erro; coluna `source_file` → erro; `--csv-delimiter` explícito vence a detecção; encoding explícito errado → erro nomeando o arquivo; detecção de delimitador produz o WARNING esperado; arquivo de uma coluna só.
   - `.xls`: números inteiros e fracionários, datas, booleanos, células vazias, linhas vazias no fim, arquivo corrompido → erro, planilha sem dados → erro, `XL_CELL_ERROR` → erro.
   - Misto: pasta com `.xlsx` + `.xls` + `.csv` consolidados juntos, `validate_headers` atravessando formatos, ordenação por nome, `source_file` por arquivo.
   - `--formats csv` restringe a descoberta; valor inválido na CLI → exit 2 pelo argparse; valor inválido no TOML → exit 1.
   - Paridade: os mesmos dados como `.xlsx` e como `.csv` produzem o mesmo `frame` (compare valores célula a célula, normalizando o que o formato impõe).
   - Invariantes: entradas byte a byte intactas (sha256 antes/depois); falha preserva a saída anterior byte a byte e não deixa `tmp*` para trás.
   - Config: `formats` e `[csv]` válidos, chave desconhecida rejeitada, tipo errado rejeitado, precedência CLI > arquivo.
   - GUI: controller recebendo as opções novas; testes de janela continuam pulando sem display.
3. `config.example.toml` atualizado com `formats` e `[csv]` comentados.
4. `README.md` e `docs/HANDOFF.md` atualizados: formatos suportados, limitações novas (precisão numérica do `.xls`, CSV sem tipo, detecção), estado dos sprints (sprint 5 implementado, aguardando aprovação do PO), como rodar, armadilhas.
5. Benchmark de evidência: gere 20 arquivos `.xlsx` sintéticos de 5.000 linhas e rode a consolidação; reporte tempo e pico de memória (`/usr/bin/time -v` ou `resource`) no `docs/HANDOFF.md`. Não é teste automatizado.

## Não faça

- Não rode `git add`, `git commit` nem `git push`. Deixe a árvore suja para revisão.
- Não altere `data/input/*`, `data/output/*` nem os arquivos de exemplo do repo.
- Não mude as 4 linhas de stdout da CLI nem o texto de erro já contratado nos testes existentes.
- Não relaxe nem apague asserção existente. Se um teste antigo falhar por mudança de assinatura que este brief exige, ajuste só a chamada e registre no relatório qual arquivo e por quê.
- Não adicione dependência além de `xlrd`/`xlwt`; nada de `pandas.read_csv` para o núcleo (o projeto evita inferência de tipo do pandas de propósito).
- Não toque em `.venv`, `.github/workflows/` nem em LICENSE.
- Não faça perguntas durante a execução: se algo estiver ambíguo, escolha a alternativa mais simples, implemente e registre a decisão no `docs/HANDOFF.md`.
- Não escreva números de aceite dentro do código de produção.

## Comandos exatos

Instalação das dependências novas (o `.venv` já existe):

```
cd /home/hermes/spreadsheet_automation
.venv/bin/pip install -e ".[dev,ui]"
```

Suíte (a única prova aceita):

```
cd /home/hermes/spreadsheet_automation
.venv/bin/python -m pytest tests -q
```

Estado de partida: 178 passed, 4 skipped (os 4 são da janela, sem display — devem continuar pulando). O total final tem de ser maior e todo verde, com no máximo esses 4 skips.

Demonstração obrigatória no relatório, com stdout real: monte uma pasta temporária com um `.xlsx`, um `.xls` e um `.csv` equivalentes, rode a CLI e cole a saída das 4 linhas.

## Relatório final

Liste: arquivos criados/alterados, comandos executados com resultado real, decisões tomadas onde o brief deixou margem, benchmark (tempo e memória), e o que ficou de fora.
