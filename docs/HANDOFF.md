# HANDOFF — Excel Consolidator

Documento de retomada. Última atualização: 2026-11-05 (MacBook, `~/Documents/spreadsheet_automation`).

## O que é

CLI Python que consolida verticalmente planilhas `.xlsx` de uma pasta, preservando a origem de cada linha, com padronização opcional, relatório de qualidade, log rotacionado e interface gráfica.

- Repo: `git@github.com:rafacorte1/spreadsheet_automation.git` (público, branch `main`)
- Fluxo de trabalho: Product Owner (Rafael) → Hermes como Tech Lead/Scrum Master → Codex CLI como implementador
- Governança: `SPEC.md` (escopo e roadmap), `AGENTS.md` (papéis e regras), `HERMES_MASTER_PROMPT.md` (fluxo por sprint com gate de aprovação)

## Estado

| Sprint | Escopo | Status | Commit |
|---|---|---|---|
| 1 | leitura, validação estrutural, exportação atômica | aprovado | `e0e5d36` |
| 2 | qualidade de dados: nulos, duplicados, padronização, relatório | aprovado | `aed12bd` |
| 3 | configuração TOML + log rotacionado (sem agendamento) | aprovado | `d15a02e` |
| 4 | interface customtkinter (Resumo/Relatório/Log) | aprovado | `343f06c` |
| — | validação de chave só quando usada | aprovado | ver `git log` |
| — | empacotamento (`.app`, atalho de duplo clique) | adiado pelo PO | — |

Suíte: 182 testes pytest (153 anteriores + 26 da UI + 3 do comportamento de chave).

Dados de teste do usuário no repo: `data/input/filial_01.xlsx`, `filial_02.xlsx`, `filial_03.xlsx` (7 linhas, `filial_02` com ordem de colunas trocada). Saída: `data/output/consolidado.xlsx` + `data/output/consolidacao.log` (ambos ignorados pelo git).

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
  cli.py          argparse, merge config, logs, 4 linhas de stdout, exit codes, run_config
  __main__.py     python -m excel_consolidator
  ui/controller.py  campos → RuntimeConfig → run_config → RunOutcome (sem tkinter)
  ui/app.py         widgets customtkinter, thread + fila, 3 abas
  ui/__main__.py    python -m excel_consolidator.ui
```

Contrato de execução da CLI: stdout sempre

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
- **Nenhuma transformação silenciosa**: valor que a regra não converte fica intocado e é contado como falha. Falha só é contada quando nenhuma conversão converteu a célula.
- **Duplicados comparam as colunas de dados**: `arquivo_origem` é excluída, então linha idêntica em arquivos diferentes é duplicata. Remoção mantém a primeira ocorrência.
- **Relatório em formato longo** (`secao, arquivo, coluna, metrica, valor`): parseável, estável. Calculado **antes** da remoção de duplicados.
- **Saída atômica**: temporário no mesmo diretório + `os.replace`; falha preserva o resultado anterior e remove o temporário.
- **Caminhos do TOML relativos ao próprio arquivo**: rodar de outro diretório não muda o alvo. Defaults e flags de CLI continuam relativos ao CWD.
- **Sem agendamento** (decisão do PO): execução recorrente é feita pela interface gráfica.
- **`run_config(RuntimeConfig)`**: entrada do núcleo para a UI — importável, silenciosa (sem print, sem log, sem sys.exit).
- **Testes isolados por CWD** (fixture autouse em `tests/conftest.py`): sem isso a suíte grava no `data/output/consolidacao.log` de produção.
- **UI: três abas, Resumo + Relatório + Log** (decisão do PO). O relatório é o diferencial do produto; escondê-lo atrás de "abrir planilha" perderia valor.
- **UI carrega `config.toml` ao abrir, com botão Recarregar** (decisão do PO). Arquivo inválido mostra o erro e mantém os defaults, em vez de abrir vazia.
- **UI grava log em arquivo, no caminho do config** (decisão do PO): mesma trilha de auditoria da CLI, não um log só em memória.
- **Controller separado do tkinter**: `ui/controller.py` valida, executa e formata; dá para testar tudo sem abrir janela, e `ui/app.py` fica com widgets.
- **Thread + `queue.Queue` + `after`**: o trabalho roda fora da thread do Tk e o resultado volta por polling; nunca se chama widget de outra thread.
- **`customtkinter` como extra `[ui]`**: o pacote continua instalável e testável sem GUI.
- **Exceção inesperada na thread vira `RunOutcome` de erro**: a janela não morre silenciosamente.
- **Chave validada só quando é usada** (decisão do PO): sem `remover_duplicados`, coluna desconhecida na chave não interrompe a execução — vira `WARNING` no log, a chave é descartada (`options.key = ()`) e o relatório volta ao modo `linhas_identicas`. Com remoção ligada, continua sendo erro. Motivo: uma chave velha no `config.toml` matava um run que não deduplicava nada.

## Ambiente onde foi construído

Sessão atual: macOS 26.6.2 no MacBook de Rafael; Python 3.14.6 (`/usr/local/bin/python3`), tkinter 9.0, pandas 3.1.1, openpyxl 3.1.5, pytest 9.2.0, customtkinter 6.0.0 em `.venv`. Codex CLI 0.166.0 autenticado (ChatGPT) e disponível, mas nesta sessão o Hermes implementou direto e usou a suíte como rede de segurança — se o PO quiser o fluxo Codex de volta, é só pedir.

Sessão anterior (sprints 1–3): container Linux, home `/home/hermes`, Python 3.14.9; Codex 0.166.0 com `--sandbox danger-full-access` (sem user namespaces o sandbox padrão falha).

## Como rodar

```bash
git clone git@github.com:rafacorte1/spreadsheet_automation.git
cd spreadsheet_automation
python3 -m venv .venv
.venv/bin/pip install -e ".[dev,ui]"
.venv/bin/python -m pytest tests -q
.venv/bin/python -m excel_consolidator --config config.example.toml
.venv/bin/python -m excel_consolidator.ui
```

## Próximos passos (candidatos, sem aprovação)

1. `write_atomic` gera saída com permissão 600 (herança do `mkstemp`); 644 seria mais previsível para arquivo compartilhado. Decisão do PO pendente.
2. Teste de carga com planilhas reais grandes (a suíte usa só dados sintéticos pequenos).
3. `docs/verificacao/*.py` ainda têm caminhos absolutos do container antigo.
4. Empacotamento (`.app`/duplo clique) está adiado por decisão do PO.

## Armadilhas conhecidas

- **Python 3.14 ignora `.pth` com flag `UF_HIDDEN`** (macOS). O `.pth` do editable install do setuptools ganhou essa flag sozinho nesta máquina e o import passou a falhar com `No module named excel_consolidator`, inclusive nos testes. Workaround aplicado: symlink `site-packages/excel_consolidator -> src/excel_consolidator` no `.venv`, e o `.pth` foi removido. Se um `pip install -e .` recriar o `.pth`, conferir com `ls -lO` e remover de novo (ou `chflags nohidden`).
- `data_only=True`: célula com fórmula sem valor em cache é lida como vazia.
- `--normalizar-numeros` converte `"007"` em `7` (perde zero à esquerda) — não usar em colunas de código.
- Notações não suportadas (viram falha, valor intocado): `R$`, `(10)`, `1e5`, `1.23.456`, `05/11/26`.
- `--chave` é literal e diferencia maiúsculas: `nome` não casa com coluna `Nome`. Coluna desconhecida só é erro com remoção ativa; sem ela a chave é ignorada com `WARNING` no log.
- Linha final totalmente vazia é descartada pelo reader (regra do Sprint 1); linha vazia no meio é preservada.
- `write_atomic(frame, output)` sem relatório gera uma aba; com relatório, duas (`consolidado`, `relatorio`).
- Rotação de log mantém apenas `consolidacao.log.1`.
- Captura de tela nesta máquina falha (`screencapture: could not create image from display`), então a janela é verificada por teste automatizado (`tests/test_ui_app.py` monta a App, executa e lê os widgets), não por screenshot.
- Testes da janela pulam sem display (`pytest.importorskip` + `TclError`): em CI sem X/VNC eles não rodam, os do controller rodam.

## Artefatos

- `docs/briefs/` — briefs por sprint (sprint1-a … sprint4-g-ui)
- `docs/verificacao/` — scripts de verificação independente (caminhos absolutos do container antigo)
- Transcrição da sessão anterior na base `life`: `Ligeirinho/Logs/2026-11-05-1036.md` e `2026-11-05-1036-transcricao.md`
