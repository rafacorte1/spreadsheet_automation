# Codex spec — Sprint 3, Etapa F (logs, integração com a CLI e README)

Repo: /home/hermes/spreadsheet_automation, branch main. Etapa E aprovada (`config.py` com `load_config`, `apply_overrides`, `RuntimeConfig`; 144 testes).

OBJETIVO: adicionar log em arquivo rotacionado, ligar `config.toml` à CLI e documentar. **Sem agendamento** — decisão do Product Owner: a execução recorrente será feita por uma interface gráfica futura, então o núcleo precisa continuar importável e silencioso.

## NÃO FAÇA

- não altere `reader.py`, `quality.py`, `report.py`, `writer.py`, `consolidator.py`, `config.py`, `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`
- não crie cron, systemd, launchd, script de agendamento ou workflow de CI
- não adicione dependência nova (use `logging` + `logging.handlers` do stdlib)
- não altere as 4 linhas de stdout já documentadas (arquivos, linhas, saida, qualidade)
- sem `git add/commit/push`

## 1) `src/excel_consolidator/runlog.py`

```python
LOGGER_NAME: str = "excel_consolidator"
LOG_FORMAT: str = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES: int = 1_000_000
DEFAULT_BACKUP_COUNT: int = 1

def setup_logging(
    log_file: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger
def close_logging(logger: logging.Logger) -> None
```

- Logger nomeado `excel_consolidator`, nível `INFO`, `propagate = False`, **sem** handler de console (stdout/stderr são da CLI).
- `RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")`; crie o diretório pai (`parents=True, exist_ok=True`). Falha ao criar o diretório/arquivo -> `ConsolidationError` citando o caminho.
- `setup_logging` deve ser **idempotente**: chamado duas vezes, não duplica handlers (remova e feche os handlers anteriores do mesmo logger).
- `close_logging` fecha e remove os handlers do logger.

## 2) `src/excel_consolidator/cli.py`

Assinaturas:

```python
def run(input_dir: Path, output_path: Path, options: QualityOptions | None = None) -> ConsolidationResult
def run_config(config: RuntimeConfig) -> ConsolidationResult
def main(argv: Sequence[str] | None = None) -> int
```

- `run` mantém o comportamento atual (usado pelos testes e por uma futura UI). `run_config` faz `consolidate(input_dir, options)` + `write_atomic(frame, output, report)`.
- Novos argumentos: `--config PATH` (default `None` = procurar `config.toml` no CWD), `--log-file PATH` (default `None`).
- `--input`, `--output`, `--trim-texto`, `--normalizar-numeros`, `--datas-iso`, `--remover-duplicados` passam a ter `default=None` para permitir distinguir "não informado" de "false". `--chave` continua `default=None`; string vazia ou só vírgulas -> `ConsolidationError`.
- Precedência: CLI explícita > `config.toml` > defaults, resolvida com `load_config` + `apply_overrides`. `--config` apontando para arquivo inexistente -> exit 1.
- `main` deve: carregar config, abrir o log, registrar as linhas de log abaixo, executar, imprimir **exatamente** as 4 linhas de stdout já existentes e retornar 0; em `ConsolidationError`, registrar `erro=<mensagem>` no log, imprimir `erro: <mensagem>` em stderr e retornar 1 (sem traceback, saída anterior intacta). Sempre fechar o log ao final (inclusive no caminho de erro).
- Linhas de log (uma por chamada, em nível INFO, exceto a última):
  ```
  inicio input=<input resolvido> output=<output resolvido> flags=<trim_texto,normalizar_numeros,datas_iso,remover_duplicados ativos, vírgula, ou nenhum> chave=<a,b ou ->
  leitura arquivos=<n> linhas_lidas=<soma dos linhas_lidas>
  gravado linhas=<linhas finais> nulos=<n> duplicados=<n> removidos=<n> alterados=<n> saida=<caminho absoluto>
  ```
  em erro: `ERROR erro=<mensagem>`.

## 3) `.gitignore`

Acrescente `data/output/*.log` e `data/output/*.log.1`.

## 4) Testes

`tests/test_runlog.py`:
- cria diretório e arquivo; conteúdo contém as três linhas de log de uma execução real (via `main`), com prefixo de data no formato `%Y-%m-%d %H:%M:%S`
- segunda execução **acrescenta** (arquivo cresce, conteúdo anterior preservado) e não duplica handler (contagem de linhas por execução é exata)
- rotação: com `max_bytes` pequeno via monkeypatch do default, após duas execuções existe `<log>.1` e o log atual é menor
- `setup_logging` em diretório impossível (arquivo comum ocupando o nome do diretório) -> `ConsolidationError`
- `close_logging` remove handlers (segunda chamada não quebra)

`tests/test_cli.py` (adicione, sem quebrar os existentes):
- `--config` com arquivo completo define input/output/flags, e stdout continua as 4 linhas
- `--input` explícito vence o `config.toml`
- `--log-file` explícito vence o config; log criado no caminho indicado
- `--config` inexistente -> exit 1, stderr com o caminho, sem criar saída
- config com chave desconhecida -> exit 1, stderr menciona a chave
- sem `config.toml` no CWD, a CLI continua funcionando com defaults e cria o log default
- caso de erro com log ligado: `erro=` aparece no arquivo de log e stdout fica vazio

`tests/test_end_to_end.py` (adicione um teste, preserve os existentes):
- rodar via `subprocess` com `--config` e `--log-file` em `tmp_path`, conferir stdout de 4 linhas, abas, conteúdo e o log com as três linhas; conferir que os arquivos de entrada não mudaram.

## 5) `README.md`

Acrescente: seção de configuração (com o bloco TOML do `config.example.toml`, a precedência CLI > arquivo > default e a regra de caminho relativo ao arquivo), seção de log (caminho default, rotação em ~1 MB mantendo 1 backup, formato das linhas, exemplo real de 3 linhas) e uma nota dizendo que **não há agendamento**: a automação é disparada por comando e o núcleo (`run_config`) é importável para uma interface gráfica futura.

## REGRAS

- `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- **Se um teste não passar, corrija o código; nunca relaxe o teste.** Não enfraqueça as asserções de stdout existentes.
- Ao final cole a saída real do pytest e uma execução real mostrando as 4 linhas de stdout + o conteúdo do arquivo de log.
