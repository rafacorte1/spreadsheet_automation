# Codex spec — Sprint 3, Etapa E (configuração em TOML)

Repo: /home/hermes/spreadsheet_automation, branch main (`aed12bd`). Sprints 1 e 2 aprovados, 115 testes passando.

OBJETIVO: adicionar `config.py` com carregamento validado de `config.toml`, precedência CLI > arquivo > default, e testes. **Nenhuma** mudança de logging, CLI ou README nesta etapa.

## NÃO FAÇA

- não altere `reader.py`, `quality.py`, `report.py`, `writer.py`, `consolidator.py`, `cli.py`, `__main__.py`, `README.md`
- não implemente logging, agendamento, interface gráfica ou variáveis de ambiente
- sem dependência nova: use `tomllib` (stdlib, Python >= 3.11)
- sem `git add/commit/push`
- não crie `config.toml` real no repositório (apenas `config.example.toml`)

## ENTREGÁVEIS

1) `src/excel_consolidator/config.py`

```python
CONFIG_FILENAME: str = "config.toml"
DEFAULT_INPUT: Path = Path("data/input")
DEFAULT_OUTPUT: Path = Path("data/output/consolidado.xlsx")
DEFAULT_LOG_FILE: Path = Path("data/output/consolidacao.log")

@dataclass(frozen=True)
class RuntimeConfig:
    input_dir: Path
    output_path: Path
    log_file: Path
    options: QualityOptions

def load_config(path: Path | None = None) -> RuntimeConfig
def apply_overrides(config: RuntimeConfig, **overrides: object) -> RuntimeConfig
```

Formato do arquivo (todas as chaves opcionais):

```toml
input = "data/input"
output = "data/output/consolidado.xlsx"
log_file = "data/output/consolidacao.log"

[qualidade]
trim_texto = false
normalizar_numeros = false
datas_iso = false
remover_duplicados = false
chave = ["produto", "data"]
```

Regras obrigatórias:

- `load_config(None)`: se `Path(CONFIG_FILENAME)` existir no diretório atual, carrega; se não existir, devolve os defaults. Nunca falha por arquivo ausente nesse modo.
- `load_config(path)` com `path` informado: arquivo inexistente -> `ConsolidationError` citando o caminho. Arquivo ilegível ou TOML inválido -> `ConsolidationError` citando o caminho e a causa.
- Chaves válidas na raiz: `input`, `output`, `log_file`, `qualidade`. Qualquer outra chave (inclusive dentro de `[qualidade]`) -> `ConsolidationError` listando as chaves desconhecidas. Erro de digitação não pode ser ignorado.
- Tipos: `input`/`output`/`log_file` precisam ser `str` não vazia; os booleanos precisam ser `bool`; `chave` precisa ser lista de `str` não vazias (aceite também lista vazia). Tipo errado -> `ConsolidationError` dizendo a chave, o tipo esperado e o tipo recebido.
- `[qualidade]` ausente = todos os defaults (`False`, `chave=()`). `[qualidade]` presente mas não tabela -> erro.
- Caminhos relativos no arquivo são resolvidos **em relação ao diretório do arquivo de configuração**, não ao CWD. Caminhos absolutos passam intactos. Defaults (sem arquivo) continuam relativos ao CWD.
- `apply_overrides(config, **overrides)`: `overrides` só aceita os nomes `input_dir`, `output_path`, `log_file`, `trim_text`, `normalize_numbers`, `dates_iso`, `key`, `remove_duplicates`; valor `None` significa "não sobrescrever". Nome desconhecido -> `TypeError`. Retorna novo `RuntimeConfig` (frozen, sem mutação).

2) `config.example.toml` na raiz, com todas as chaves e comentários curtos. **Não** crie `config.toml` (ele é opcional; o exemplo é a documentação).

3) `.gitignore`: acrescente `config.toml` (configuração local do usuário não deve ser versionada).

4) `tests/test_config.py` — cobrir:

- sem arquivo no diretório atual -> defaults exatos (`data/input`, `data/output/consolidado.xlsx`, `data/output/consolidacao.log`, `QualityOptions()`)
- arquivo completo -> todos os campos lidos
- arquivo só com `input` -> demais campos nos defaults
- `[qualidade]` parcial (`chave = ["a"]`, `trim_texto = true`) -> demais flags em `False`
- `load_config(path)` inexistente -> `ConsolidationError` com o caminho na mensagem
- TOML inválido -> `ConsolidationError` com o caminho
- chave desconhecida na raiz e dentro de `[qualidade]` -> erro listando a chave
- tipo errado (`input = 5`, `trim_texto = "sim"`, `chave = "produto"`, `chave = [1]`, `input = ""`) -> erro com chave/tipo
- caminho relativo resolvido a partir do diretório do config (crie o config em `tmp_path/sub`, use `input = "dados"`, espere `tmp_path/sub/dados`)
- caminho absoluto preservado
- `apply_overrides`: sobrescreve só o que veio diferente de `None`; `None` mantém; nome inválido -> `TypeError`; não muta o original
- `load_config` acha `config.toml` no CWD (use `monkeypatch.chdir(tmp_path)`)

## REGRAS

- `cd /home/hermes/spreadsheet_automation && .venv/bin/python -m pytest tests -q`
- Tipado, `from __future__ import annotations`, docstrings curtas.
- **Se um teste não passar, corrija o código; nunca relaxe o teste.** Não altere os 115 testes existentes.
- Cole a saída real do pytest e relate arquivos criados.
