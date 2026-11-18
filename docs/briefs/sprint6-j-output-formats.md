# Brief — Sprint 6: saída CSV e resumo `--json`

Incremento aprovado pelo PO em 2026-11-18. Escopo fechado: escrever o resultado consolidado em CSV além do `.xlsx`, e imprimir um resumo legível por máquina. O contexto é uso real por SSH numa VPS headless, então nada aqui depende de tela.

Leia antes de começar: `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `docs/HANDOFF.md`, o código em `src/excel_consolidator/` e os testes em `tests/`.

## Estado de partida

Sprints 1–5 aprovados. 230 testes passando, 4 pulados sem display. O produto lê `.xlsx`, `.xls` e `.csv` e sempre grava um workbook com as abas `consolidated` e `report`, imprimindo 4 linhas de stdout.

## Decisões já tomadas (não reabra)

1. **Flag `--output-format`** com valores `xlsx` (default), `csv` e `both`. Mesma chave no TOML como `output_format`, validada (valor fora da lista = erro de configuração, exit 1 na CLI por `ConsolidationError`, como as outras chaves).
2. **Caminhos, regra exata**:
   - `xlsx`: `--output` recebe o workbook com as abas `consolidated` e `report`. Comportamento atual, inalterado.
   - `csv`: `--output` recebe os dados em CSV; o relatório vai para `<stem do output>_report.csv` no mesmo diretório. Nenhuma extensão é reescrita.
   - `both`: `--output` precisa terminar em `.xlsx` (senão `ConsolidationError` explicando a regra). O workbook vai nele, os dados vão para `<stem>.csv` e o relatório para `<stem>_report.csv`.
3. **Formato do CSV de saída**: `utf-8-sig` (BOM para o Excel do Windows abrir acento certo), delimitador `,`, `csv.QUOTE_MINIMAL`, quebra de linha `\n`, cabeçalho com as colunas do frame incluindo `source_file`. Valores convertidos para texto com a mesma representação que o xlsx produz: `None` → campo vazio, `int`/`float`/`bool`/`datetime`/`date` → `str(value)`. Não inventar formatação regional.
4. **CSV do relatório**: mesmas colunas do formato longo já usado na aba `report` (`section, file, column, metric, value`), mesma ordem de linhas que a aba.
5. **Escrita atômica em CSV também**: temporário no diretório de destino + `os.replace`, e falha no meio não pode destruir CSV anterior válido nem deixar temporário. Nenhum arquivo do conjunto pode ficar parcialmente atualizado: escreva todos os temporários primeiro e só então publique, para que um erro de escrita não deixe xlsx novo com csv velho.
6. **`--json`**: imprime um objeto JSON em stdout, uma linha, e desliga as 4 linhas de texto. Sem `--json`, stdout continua exatamente como hoje. Schema:
   ```json
   {"files": 3, "rows": 7, "output": "/abs/principal", "outputs": {"xlsx": "/abs/x.xlsx", "csv": "/abs/x.csv", "report": "/abs/x_report.csv"}, "quality": {"nulls": 0, "duplicates": 0, "removed": 0, "changed": 0}, "warnings": ["..."]}
   ```
   `outputs` contém só as chaves realmente gravadas; `output` é o caminho de `--output`. Exit codes não mudam (0 sucesso, 1 erro de consolidação/configuração, 2 argumento inválido). Erro com `--json` continua indo para stderr como `error: <mensagem>`, sem JSON.
7. **Log**: as linhas de log continuam existindo e passam a registrar os caminhos gravados. `--json` não muda o log.
8. **GUI**: continua funcionando e ganha o campo de formato de saída no mesmo padrão dos campos atuais; `--json` é só de CLI. Se um campo da GUI ficar ambíguo, use o mais simples e documente.
9. **Nada de dependência nova.** Biblioteca padrão (`csv`, `json`, `os`, `tempfile`) resolve.

## Entregáveis

1. `writer.py` (ou módulo novo, se ficar mais claro) com a escrita CSV e a publicação atômica de um conjunto de arquivos. `write_atomic` atual continua existindo com o mesmo contrato, ou é substituída mantendo os testes existentes verdes.
2. `cli.py`: `--output-format`, `--json`, montagem do JSON e impressão do resumo. As 4 linhas atuais preservadas quando `--json` estiver ausente.
3. `config.py`: chave `output_format`, validação de tipo/valor, precedência CLI > arquivo > default.
4. `ui/controller.py` e `ui/app.py`: formato de saída exposto, sem tkinter no controller.
5. `config.example.toml` com `output_format` comentado e o exemplo de uso.
6. Testes novos, sintéticos, nos arquivos que você julgar adequados. Cobertura mínima:
   - `csv`: arquivo criado, BOM presente (`\xef\xbb\xbf`), cabeçalho exato, `None` vira campo vazio, número inteiro/fracionário e data com a mesma representação do xlsx, 7 linhas de dados no caso misto do fixture.
   - `both`: os três arquivos aparecem, workbook continua com 2 abas, valores idênticos entre csv e xlsx célula a célula (paridade), um único `source_file` por linha.
   - `--output` sem `.xlsx` com `both` → erro claro, nada escrito.
   - `--json`: JSON válido, campos exatos, `outputs` só com o que foi gravado, stdout com uma linha e sem as 4 linhas de texto, exit 0. Em erro, stderr com `error:` e stdout vazio.
   - `output_format` inválido no TOML → exit 1; valor inválido em `--output-format` → exit 2 pelo argparse.
   - Atomicidade: falha de escrita no meio deixa os arquivos anteriores byte a byte intactos e nenhum `tmp*` para trás; vale para csv e para `both`.
   - Entradas intactas (sha256) em todos os formatos de saída.
7. `README.md` e `docs/HANDOFF.md`: flags novas, exemplos por SSH, o que fica no CSV e o que só existe no xlsx, e o estado do sprint 6 (implementado, aguardando aprovação do PO).

## Não faça

- Não rode `git add`, `git commit` nem `git push`.
- Não altere `data/input/*` nem `data/output/*`.
- Não mude as 4 linhas de stdout existentes quando `--json` não for passado, nem o texto `error:`.
- Não relaxe nem apague asserção existente. Se um teste antigo falhar por assinatura que este brief exige, ajuste só a chamada e registre no relatório.
- Não adicione dependência, não toque em `.venv`, `.github/workflows/`, `LICENSE`, `SPEC.md` nem `AGENTS.md`.
- Não faça perguntas durante a execução: escolha a alternativa mais simples, implemente e registre a decisão no `docs/HANDOFF.md`.
- Não escreva números de aceite no código de produção.

## Comandos exatos

```
cd /home/hermes/spreadsheet_automation
.venv/bin/python -m pytest tests -q
```

Estado de partida: 230 passed, 4 skipped. O total final tem de ser maior e todo verde, com no máximo esses 4 skips.

## Relatório final

Liste arquivos criados/alterados, comandos executados com resultado real, decisões onde o brief deixou margem, e demonstração com stdout real de duas execuções: `--output-format both` e `--output-format both --json`.
