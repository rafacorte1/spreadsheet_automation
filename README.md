# Excel Consolidator

Consolida verticalmente arquivos `.xlsx` de uma pasta, preservando todas as linhas de dados lidas e adicionando `arquivo_origem` com apenas o nome de cada arquivo. Os arquivos são processados em ordem alfabética; as colunas seguem a ordem do primeiro arquivo. As entradas não são modificadas.

Requer Python >= 3.11. Dependências: pandas e openpyxl; pytest para testes.

Instalação a partir da raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Estrutura de pastas:

```text
src/excel_consolidator/  # reader, consolidator, writer e CLI
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
```

Em caso de erro de consolidação, a CLI escreve `erro: <mensagem>` em stderr e termina com código 1, sem traceback. Argumentos inválidos terminam com código 2. Sucesso retorna 0.

Para executar os testes:

```bash
.venv/bin/python -m pytest tests -q
```

A leitura usa openpyxl para detectar cabeçalhos duplicados ou em branco antes que sejam transformados por inferência de nomes. A comparação dos cabeçalhos é literal, sem normalização; os arquivos precisam ter os mesmos nomes de colunas, ainda que em ordens diferentes. A coluna `arquivo_origem` é reservada. Entradas vazias, sem registros, corrompidas ou incompatíveis são rejeitadas. Arquivos `~$*` e subpastas são ignorados.

A consolidação preserva os valores retornados pelo reader, sem conversão de tipos, arredondamento ou deduplicação. O resultado contém uma única aba `consolidado`, com cabeçalho na linha 1 e sem índice do pandas. A escrita cria um temporário no diretório do destino, fecha o arquivo completo e usa `os.replace` para substituição atômica. Falhas de leitura ou escrita preservam o resultado anterior; temporários de uma escrita que falhou são removidos.

Limitações do Sprint 1:

- Apenas `.xlsx` e a primeira aba de cada arquivo; sem `.xls` ou `.csv`.
- Fórmulas sem valor em cache são lidas como vazias (`data_only=True`); fórmulas e formatação não são preservadas na saída.
- Sem normalização, deduplicação ou validação de valores.
- Sem agendamento.
