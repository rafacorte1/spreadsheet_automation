# Excel Consolidator

Consolida verticalmente arquivos `.xlsx` de uma pasta, preservando por padrão todas as linhas de dados lidas e adicionando `arquivo_origem` com apenas o nome de cada arquivo. Os arquivos são processados em ordem alfabética; as colunas seguem a ordem do primeiro arquivo. As entradas não são modificadas.

Requer Python >= 3.11. Dependências: pandas e openpyxl; pytest para testes.

Instalação a partir da raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ui]"
```

Estrutura de pastas:

```text
src/excel_consolidator/  # reader, consolidator, writer e CLI
src/excel_consolidator/ui/  # interface gráfica (controller sem tkinter + app customtkinter)
tests/                  # testes com dados sintéticos
data/input/             # arquivos de entrada
data/output/            # consolidado.xlsx
```

Uso, com o ambiente virtual ativado:

```bash
python -m excel_consolidator
python -m excel_consolidator --input DIR --output PATH
```

Os argumentos são opcionais. Os padrões são `data/input` e `data/output/consolidado.xlsx`, relativos ao diretório atual. Exemplo de saída para dois arquivos com três linhas ao todo:

```text
arquivos: 2
linhas: 3
saida: /caminho/do/projeto/data/output/consolidado.xlsx
qualidade: nulos=0 duplicados=0 removidos=0 alterados=0
```

Em caso de erro de consolidação, a CLI escreve `erro: <mensagem>` em stderr e termina com código 1, sem traceback. Argumentos inválidos terminam com código 2. Sucesso retorna 0.

Para executar os testes:

```bash
.venv/bin/python -m pytest tests -q
```

A leitura usa openpyxl para detectar cabeçalhos duplicados ou em branco antes que sejam transformados por inferência de nomes. A comparação dos cabeçalhos é literal, sem normalização; os arquivos precisam ter os mesmos nomes de colunas, ainda que em ordens diferentes. A coluna `arquivo_origem` é reservada. Entradas vazias, sem registros, corrompidas ou incompatíveis são rejeitadas. Arquivos `~$*` e subpastas são ignorados.

Sem flags de qualidade, a consolidação preserva os valores retornados pelo reader, sem conversão de tipos, arredondamento ou deduplicação. A CLI gera as abas `consolidado` e `relatorio`, nessa ordem, com cabeçalhos na linha 1 e sem índice do pandas. A função `write_atomic(frame, output)` continua gerando apenas `consolidado` quando não recebe relatório. A escrita cria um temporário no diretório do destino, fecha o arquivo completo e usa `os.replace` para substituição atômica. Falhas de leitura ou escrita preservam o resultado anterior; temporários de uma escrita que falhou são removidos.

Limitações:

- Apenas `.xlsx` e a primeira aba de cada arquivo; sem `.xls` ou `.csv`.
- Fórmulas sem valor em cache são lidas como vazias (`data_only=True`); fórmulas e formatação não são preservadas na saída.
- Sem casefold ou remoção de acentos; cabeçalhos continuam com comparação literal.
- Sem deduplicação por semelhança; somente igualdade de valores ou da chave.
- `"007"` vira `7` com `--normalizar-numeros`, perdendo zeros à esquerda.
- Sem agendamento.

Qualidade de dados (todas as flags são opcionais e desligadas por padrão):

- `--trim-texto`: remove espaços das extremidades de textos.
- `--normalizar-numeros`: converte textos numéricos brasileiros, por exemplo `" 1.234,56 "` em `1234.56`.
- `--datas-iso`: converte datas reconhecidas em valor de data ou de data e hora (formatos `DD/MM/AAAA`, `AAAA-MM-DD`, com hora opcional `HH:MM:SS`).
- `--chave COL1,COL2`: compara duplicados pelas colunas informadas; espaços e entradas vazias são removidos. Uma chave vazia é sempre rejeitada. Coluna desconhecida é erro quando a chave vai ser usada para remover (`--remover-duplicados`); sem remoção, a chave é ignorada com `WARNING` no log e o relatório conta duplicados no modo `linhas_identicas`.
- `--remover-duplicados`: remove ocorrências posteriores à primeira, na ordem de arquivo e linha. Sem chave, compara todas as colunas de dados, excluindo `arquivo_origem`.

```bash
python -m excel_consolidator --input data/input --output data/output/consolidado.xlsx \
  --trim-texto --normalizar-numeros --remover-duplicados --chave nome,valor
```

As regras são aplicadas na ordem trim, números e datas. Um valor que não pode ser convertido fica intocado pela conversão; a falha de uma regra só é contada quando nenhuma conversão (`--normalizar-numeros` ou `--datas-iso`) converteu aquela célula — um texto que apenas perdeu espaços com `--trim-texto` continua contando falha. `alterados` soma operações de alteração por regra; uma célula pode contribuir mais de uma vez.

A aba `relatorio` tem exatamente as colunas `secao, arquivo, coluna, metrica, valor`. As seções aparecem nesta ordem, com arquivos em ordem alfabética e colunas na ordem de cada planilha:

- `resumo`: `linhas_lidas` por arquivo, antes de remover duplicados.
- `nulos`: `nulos` por coluna de dados (inclusive zero), considerando `None`, texto vazio ou só espaços, após padronização e antes de remover duplicados. Nunca inclui `arquivo_origem`.
- `padronizacao`: `alterados_<regra>` e `falhas_<regra>` por coluna, inclusive zero, somente para regras ativas (`trim_texto`, `normalizar_numeros`, `datas_iso`).
- `duplicados`: `modo` (`linhas_identicas` ou `chave:a,b`), `linhas_duplicadas` e `linhas_removidas`. Campos de arquivo e coluna ficam vazios.

`linhas` no stdout conta as linhas da saída final, após eventual remoção; `linhas_lidas` conta a entrada. A linha `qualidade:` soma nulos, duplicados posteriores à primeira, removidos e alterações por regra. A detecção de duplicados e o relatório funcionam mesmo sem flags; por isso dados com nulos ou duplicados podem apresentar contadores diferentes de zero sem solicitar mudanças.

## Configuração

A CLI procura `config.toml` no diretório atual; use `--config PATH` para indicar outro arquivo (obrigatório quando explícito). Exemplo de `config.example.toml`:

```toml
# Caminhos relativos ao diretório deste arquivo.
input = "data/input"
output = "data/output/consolidado.xlsx"
log_file = "data/output/consolidacao.log"

[qualidade]
# Padronizações opcionais.
trim_texto = false
normalizar_numeros = false
datas_iso = false
# Remoção opcional e colunas usadas como chave.
remover_duplicados = false
chave = ["produto"]
```

A chave só precisa existir quando é usada para remover. Com `remover_duplicados = false`, uma coluna inexistente na chave não interrompe a execução: o log registra `WARNING ... ignorada` e o relatório conta duplicados no modo `linhas_identicas`. Com a remoção ligada, a mesma chave é rejeitada.

A precedência é CLI explícita > arquivo > defaults. Caminhos definidos no TOML são relativos ao diretório do arquivo; caminhos da CLI e defaults são relativos ao diretório atual. Sem arquivo, as flags ficam desligadas e a chave vazia. Ajuste a chave do exemplo às colunas das entradas.

```bash
python -m excel_consolidator --config config.toml --log-file data/output/execucao.log
```

## Log

O caminho default é `data/output/consolidacao.log`. O log UTF-8 acrescenta registros a cada execução e rotaciona em aproximadamente 1 MB, mantendo um backup `.log.1`. `--log-file PATH` substitui o caminho configurado. O formato é `AAAA-MM-DD HH:MM:SS NIVEL mensagem`, sem handler de console. Cada sucesso registra `inicio` (caminhos resolvidos, flags ativas e chave), `leitura` (arquivos e linhas antes de remover duplicados) e `gravado` (linhas finais, contadores e saída absoluta). Erros após abrir o log usam `ERROR erro=<mensagem>`; falhas de configuração ou abertura são informadas em stderr, pois o log ainda não está disponível.

Exemplo real com entrada sintética:

```text
2026-11-05 10:29:59 INFO inicio input=/home/hermes/.hermes/cache/scratch/etapa-f-demo-2xuqum_e/input output=/home/hermes/.hermes/cache/scratch/etapa-f-demo-2xuqum_e/out.xlsx flags=trim_texto chave=-
2026-11-05 10:29:59 INFO leitura arquivos=1 linhas_lidas=1
2026-11-05 10:29:59 INFO gravado linhas=1 nulos=0 duplicados=0 removidos=0 alterados=1 saida=/home/hermes/.hermes/cache/scratch/etapa-f-demo-2xuqum_e/out.xlsx
```

Não há agendamento: a automação é disparada por comando. O núcleo `run_config`, em `excel_consolidator.cli`, recebe um `RuntimeConfig` e permanece importável e silencioso para uma interface gráfica futura. Ele não configura logs; essa responsabilidade pertence à CLI.

## Interface gráfica

`customtkinter` é opcional (`pip install -e ".[ui]"`). A janela usa o mesmo núcleo da CLI:

```bash
python -m excel_consolidator.ui
python -m excel_consolidator.ui --config caminho/config.toml
```

- Campos: pasta de entrada, arquivo de saída e arquivo de log (os três com "Procurar"), os quatro interruptores de qualidade e a chave.
- Abas: `Resumo` (as quatro linhas do contrato da CLI), `Relatório` (a tabela `secao, arquivo, coluna, metrica, valor`) e `Log` (rabo do arquivo, com botão para atualizar).
- `config.toml` do diretório atual é carregado ao abrir; "Recarregar config" relê o arquivo. Arquivo inválido mostra o erro na aba Resumo e mantém os defaults.
- A execução roda em thread; o resumo, o relatório e o log chegam à janela sem congelá-la. Erro de consolidação aparece como `erro: <mensagem>`, sem traceback, e não substitui a saída anterior.
- A interface grava log em arquivo, no caminho configurado, exatamente como a CLI.
- A lógica testável vive em `ui/controller.py`, que não importa tkinter; `ui/app.py` só monta widgets. Sem display, os testes da janela são pulados, e os do controller continuam rodando.

## Retomar o projeto

`docs/HANDOFF.md` tem o estado dos sprints, as decisões com o porquê, as armadilhas conhecidas e o próximo passo. `docs/briefs/` guarda os briefs por sprint e `docs/verificacao/` os scripts de verificação independente.
