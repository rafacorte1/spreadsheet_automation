# Brief — Sprint 7: intake com arquivamento

Escopo proposto em 2026-11-18, **não aprovado ainda**. Nada de implementação antes do aceite do PO.

Leia antes de começar: `SPEC.md`, `AGENTS.md`, `HERMES_MASTER_PROMPT.md`, `docs/HANDOFF.md`, `docs/briefs/sprint6-j-output-formats.md` e o código em `src/excel_consolidator/`.

## Problema

O uso real é CLI na VPS por SSH. O único passo manual que resta é o arquivo entrar e o "já rodei esse arquivo?" ser respondido de cabeça. Hoje o Rafael copia o extrato por `scp` para uma pasta, roda a consolidação e precisa lembrar depois o que já entrou. Se rodar de novo com os mesmos arquivos, o resultado duplica linhas.

## Objetivo do incremento

Um subcomando `intake` que, depois de consolidar com sucesso, arquiva os arquivos processados fora da pasta de entrada, com registro auditável do que entrou. Falha nunca move arquivo.

## Decisões propostas (o PO aprova ou corrige)

1. **Comando**: `excel-consolidator intake` como subcomando novo, sem mexer no comando atual. `excel-consolidator --input ...` continua funcionando exatamente como hoje, sem arquivar nada. `intake` aceita as mesmas flags (`--input`, `--output`, `--output-format`, `--json`, qualidade, CSV, formatos, `--config`, `--log-file`) mais `--archive`.
2. **Archive padrão**: `--archive` ou config `archive`, default `data/archive`. Layout `<archive>/AAAA-MM-DD/<nome original>`, data do run.
3. **Colisão de nome no archive**: nunca sobrescreve. Segunda ocorrência vira `<stem>-2.<ext>`, depois `-3`, e assim por diante.
4. **Ordem e atomicidade**: consolida, publica as saídas (já é transacional desde o sprint 6) e **só depois** move as entradas. Erro em qualquer etapa anterior ao move = nenhum arquivo sai da pasta de entrada. Se um move falhar no meio, os já movidos ficam no archive, os demais continuam na entrada, a saída é mantida e o erro diz exatamente quais arquivos não foram arquivados.
5. **Manifesto**: `<archive>/index.csv` em modo append, cabeçalho `date,file,source_name,sha256,rows,output`. Uma linha por arquivo arquivado, com o sha256 do conteúdo e as linhas que aquele arquivo contribuiu. Se o manifesto não puder ser escrito, o intake falha antes de mover qualquer coisa (o registro nunca fica atrás do estado real).
6. **Pasta de entrada vazia** depois de um intake bem-sucedido é estado normal; rodar `intake` de novo cai no erro atual de "nenhum arquivo", com a lista de extensões ativas.
7. **Relatório**: as 4 linhas de stdout atuais continuam iguais; com `--json` some um campo novo `archived` (lista de caminhos de destino) e `archive` (o diretório). `--json` mantém o schema anterior e só acrescenta chaves.
8. **GUI**: fora deste incremento. O controller não muda; se `intake` for chamado pela GUI no futuro, é incremento próprio.
9. **Sem dependência nova**: `shutil`, `hashlib`, `csv`, `datetime`.

## Entregáveis

1. `intake.py` (ou módulo equivalente) com a lógica de arquivamento, colisão, manifesto e erros nomeados. Função pura para o cálculo de nome livre, testável sem tocar disco.
2. `cli.py`: subcomando `intake`, mantendo o comando atual intacto. Config: chave `archive` validada.
3. Testes novos, sintéticos. Cobertura mínima:
   - sucesso: 3 arquivos mistos, todos movidos, entrada vazia no fim, saída escrita, `archived` no JSON com os três caminhos;
   - falha de consolidação: nenhum arquivo movido, saída anterior intacta;
   - colisão: dois intakes no mesmo dia com o mesmo nome → `<stem>-2.<ext>`, conteúdo antigo preservado byte a byte;
   - manifesto: uma linha por arquivo, sha256 correto conferido por fora, `rows` somando o total, append em run seguinte sem perder linha anterior;
   - manifesto bloqueado (diretório no lugar do arquivo) → intake falha e nada é movido;
   - move que falha no meio (monkeypatch em `shutil.move`) → erro nomeia o(s) arquivo(s) restantes, saída mantida, arquivos já movidos permanecem no archive;
   - `--archive` igual à pasta de entrada ou à de saída → erro claro;
   - comando antigo sem `intake` não arquiva nada nem cria `data/archive`.
4. `README.md` e `docs/HANDOFF.md`: subcomando, layout do archive, manifesto, exemplo por SSH (`scp` para `data/inbox` e `intake`), estado do sprint 7.

## Não faça

- Não rode `git add`, `git commit` nem `git push`.
- Não altere `data/input/*`, `data/output/*` nem os fixtures do repo.
- Não mude o comportamento do comando atual, nem as 4 linhas de stdout, nem o texto `error:`.
- Não relaxe nem apague asserção existente.
- Não adicione dependência; não toque em `.venv`, `.github/workflows/`, `LICENSE`, `SPEC.md`, `AGENTS.md`.
- Não implemente deduplicação por hash entre dias, agendamento, watcher de pasta nem GUI. Ficam para incremento próprio.
- Não faça perguntas durante a execução: escolha a alternativa mais simples, implemente e registre no `docs/HANDOFF.md`.
- Não escreva números de aceite no código de produção.

## Comandos exatos

```
cd /home/hermes/spreadsheet_automation
.venv/bin/python -m pytest tests -q
```

Estado de partida: 257 passed, 4 skipped. Total final maior e todo verde, no máximo esses 4 skips.

## Relatório final

Arquivos criados/alterados, comandos com resultado real, decisões tomadas onde o brief deixou margem, e demonstração com stdout real de um intake completo mostrando entrada vazia no fim, conteúdo do `index.csv` e as duas execuções do segundo run (que deve falhar por falta de arquivo).
