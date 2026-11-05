# HANDOFF — Excel Consolidator

Documento de retomada. Última atualização: 2026-11-05 10:40 (sessão no container Linux do Hermes).

## O que é

CLI Python que consolida verticalmente planilhas `.xlsx` de uma pasta, preservando a origem de cada linha, com padronização opcional, relatório de qualidade e log rotacionado.

- Repo: `git@github.com:rafacorte1/spreadsheet_automation.git` (público, branch `main`)
- Fluxo de trabalho: Product Owner (Rafael) → Hermes como Tech Lead/Scrum Master → Codex CLI como implementador
- Governança: `SPEC.md` (escopo e roadmap), `AGENTS.md` (papéis e regras), `HERMES_MASTER_PROMPT.md` (fluxo por sprint com gate de aprovação)

## Estado

| Sprint | Escopo | Status | Commit |
|---|---|---|---|
| 1 | leitura, validação estrutural, exportação atômica | aprovado | `e0e5d36` |
| 2 | qualidade de dados: nulos, duplicados, padronização, relatório | aprovado | `aed12bd` |
| 3 | configuração TOML + log rotacionado (sem agendamento) | aprovado | `d15a02e` |
| — | interface gráfica customtkinter | **não iniciado** | — |

Suíte: 153 testes pytest verdes. Árvore limpa, head local == `git ls-remote origin main`.

Dados de teste do usuário no repo: `data/input/filial_01.xlsx`, `filial_02.xlsx`, `filial_03.xlsx` (7 linhas no total, `filial_02` com ordem de colunas trocada). Saída gerada: `data/output/consolidado.xlsx` + `data/output/consolidacao.log` (ambos ignorados pelo git).

## Arquitetura

```
src/excel_consolidator/
  errors.py       ConsolidationError (mensagem exibível, sem traceback na CLI)
  reader.py       descoberta ordenada, primeira aba, cabeçalhos literais, linhas crus
  quality.py      trim / números pt-BR / datas ISO, contadores por coluna e regra, duplicados
  report.py       aba `relatorio` em formato longo (secao, arquivo, coluna, metrica, valor)
  consolidator.py concatenação, validação de chave, dedup opcional, resultado + relatório
  writer.py       gravação de 2 abas com temporário no destino + os.replace
  config.py       config.toml opcional, validação de chave/tipo, precedência CLI > arquivo > default
  runlog.py       RotatingFileHandler (~1 MB, 1 backup), sem handler de console
  cli.py          argparse, merge config, logs, 4 linhas de stdout, exit codes
  __main__.py     python -m excel_consolidator
```

Contrato de execução: stdout sempre

```
arquivos: <n>
linhas: <linhas da saída final>
saida: <caminho absoluto>
qualidade: nulos=<X> duplicados=<Y> removidos=<Z> alterados=<W>
```

Erro de consolidação/configuração: `erro: <mensagem>` em stderr, exit 1, sem traceback, saída anterior byte a byte intacta. Argumento inválido: exit 2 (argparse).

## Decisões e porquês

- **Leitura por openpyxl, não `pandas.read_excel`**: o pandas renomeia cabeçalhos duplicados (`id`, `id.1`) e transforma célula vazia em `Unnamed: N`, o que mascararia duas rejeições exigidas pelo SPEC.
- **Comparação de cabeçalhos literal**: sem strip, casefold ou remoção de acento. `"A"` ≠ `" A"` ≠ `"a"`.
- **`dtype=object` na concatenação**: evita `None` → `NaN` e string numérica → número.
- **Nenhuma transformação silenciosa**: valor que a regra não converte fica intocado e é contado como falha. Falha só é contada quando nenhuma conversão converteu a célula (um texto só aparado pelo trim continua contando falha).
- **Duplicados comparam as colunas de dados**: `arquivo_origem` é excluída, então linha idêntica em arquivos diferentes é duplicata. Remoção mantém a primeira ocorrência (ordem de arquivo + linha).
- **Relatório em formato longo** (`secao, arquivo, coluna, metrica, valor`): parseável, estável, sem blocos visuais no meio da planilha. Calculado **antes** da remoção de duplicados.
- **Saída atômica**: temporário no mesmo diretório + `os.replace`; falha preserva o resultado anterior e remove o temporário.
- **Caminhos do TOML relativos ao próprio arquivo**: rodar de outro diretório não muda o alvo. Defaults e flags de CLI continuam relativos ao CWD.
- **Sem agendamento** (decisão do PO): a execução recorrente será feita por interface gráfica.
- **`run_config(RuntimeConfig)`**: entrada do núcleo para a futura UI — importável, silenciosa (sem print, sem log, sem sys.exit).
- **Testes isolados por CWD** (fixture autouse em `tests/conftest.py`): sem isso a suíte grava no `data/output/consolidacao.log` de produção.

## Ambiente onde foi construído

- Container Linux, home `/home/hermes` (não é o MacBook; `/Users/rafaelcorte` não existe aqui)
- Python 3.14.9; pandas 3.1.1; openpyxl 3.1.5; pytest 9.2.0 em `.venv`
- Codex CLI 0.166.0 autenticado via ChatGPT. `--sandbox workspace-write` falha neste container (sem user namespaces); usar `--sandbox danger-full-access` com o git como rede de segurança
- Sem display: `DISPLAY` vazio e sem Xvfb (`sudo` pede senha interativa) — GUI não pode ser executada nem vista aqui
- tkinter 9.0 disponível; `customtkinter 6.0.0` instalável

## Como rodar

```bash
git clone git@github.com:rafacorte1/spreadsheet_automation.git
cd spreadsheet_automation
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest tests -q
.venv/bin/python -m excel_consolidator --config config.example.toml
```

## Próximo passo: interface customtkinter

Plano proposto ao PO, ainda **sem confirmação**:

- `src/excel_consolidator/ui/controller.py` — sem importar tkinter: valida campos, monta `RuntimeConfig`, chama `run_config`, formata resumo/erro, lê o rabo do log. Testável sem tela.
- `src/excel_consolidator/ui/app.py` — só widgets customtkinter; execução em thread para não congelar a janela.
- `src/excel_consolidator/ui/__main__.py` — `python -m excel_consolidator.ui`.
- Layout: frame de entradas (pasta + arquivo de saída com "Procurar"), frame de qualidade (4 switches + campo chave), botões Consolidar / Carregar config.toml / Abrir pasta, e abas Resumo / Relatório (Treeview) / Log.

Três decisões pendentes do PO:

1. Abas Resumo + Relatório + Log, ou só Resumo e Log?
2. Carregar `config.toml` ao abrir a janela (com botão para recarregar), ou UI independente do arquivo?
3. A UI grava log como a CLI (caminho do config) ou log desligado na interface?

## Armadilhas conhecidas

- `data_only=True`: célula com fórmula sem valor em cache é lida como vazia.
- `--normalizar-numeros` converte `"007"` em `7` (perde zero à esquerda) — não usar em colunas de código.
- Notações não suportadas (viram falha, valor intocado): `R$`, `(10)`, `1e5`, `1.23.456`, `05/11/26`.
- `--chave` é literal e diferencia maiúsculas: `nome` não casa com coluna `Nome`.
- Linha final totalmente vazia é descartada pelo reader (regra do Sprint 1); linha vazia no meio é preservada.
- `write_atomic(frame, output)` sem relatório gera uma aba; com relatório, duas (`consolidado`, `relatorio`).
- Rotação de log mantém apenas `consolidacao.log.1`.

## Artefatos desta sessão

- `docs/briefs/` — briefs enviados ao Codex, na ordem (sprint1-a … sprint3-fix)
- `docs/verificacao/` — scripts de verificação independente (caminhos absolutos do container; ajustar antes de rodar em outra máquina)
- Transcrição completa da sessão e log resumido na base `life`: `Ligeirinho/Logs/2026-11-05-1036.md` e `2026-11-05-1036-transcricao.md`
