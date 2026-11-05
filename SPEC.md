# Excel Consolidator — Especificação v0.1

## Objetivo
Construir uma ferramenta CLI Python para consolidar verticalmente arquivos `.xlsx` de uma pasta, preservando a origem de cada linha.

## Arquitetura
Python >=3.11; pandas, openpyxl; pytest. Pacote `src/excel_consolidator` com `cli.py`, `reader.py`, `consolidator.py`, `writer.py`. Pastas `data/input` e `data/output`. Sem APIs, banco de dados ou UI.

## Roadmap (gates obrigatórios)
- Sprint 1: MVP de leitura, validação estrutural e exportação.
- Sprint 2: qualidade de dados (nulos, duplicados, padronização e relatório de inconsistências), somente após aprovação explícita.
- Sprint 3: configuração, logs e execução recorrente, somente após aprovação explícita.

## Sprint 1 — requisitos
1. Descobrir arquivos `.xlsx` diretamente em `data/input`, em ordem alfabética; ignorar `~$*`.
2. Ler apenas a primeira aba de cada arquivo.
3. Exigir cabeçalhos não vazios, únicos e idênticos entre arquivos, independentemente da ordem; comparação literal de nomes, sem normalização.
4. Reordenar colunas para a ordem do primeiro arquivo; concatenar verticalmente, sem deduplicar, com coluna adicional `arquivo_origem` contendo o nome do arquivo.
5. Rejeitar entrada que já possua coluna `arquivo_origem` para evitar colisão.
6. Exportar `data/output/consolidado.xlsx` com uma aba, somente após todos os arquivos serem validados; escrita em arquivo temporário no diretório de saída e substituição atômica ao final, para não sobrescrever resultado anterior em caso de erro.
7. Informar no terminal total de arquivos e linhas e caminho da saída.
8. Se não houver arquivos, se um arquivo estiver corrompido, sem cabeçalho, sem linhas de dados ou com colunas incompatíveis, terminar com código diferente de zero e mensagem útil.
9. Não alterar os arquivos de entrada.

## Testes e aceite do Sprint 1
- Dois arquivos com mesmas colunas e ordens diferentes geram todas as linhas e `arquivo_origem` correto.
- Arquivos temporários ignorados.
- Diretório vazio, arquivo corrompido, cabeçalhos incompatíveis, duplicados, colisão de `arquivo_origem` e arquivo sem registros produzem erro controlado.
- Resultado anterior permanece intacto após falha.
- Testes automatizados via pytest passam; comando CLI demonstrado com dados sintéticos.
- README contém instalação, execução, limitações e exemplos.

## Limites
Sem normalização de cabeçalhos, deduplicação, validação de valores, processamento de `.xls` ou `.csv`, agendamento, interface gráfica ou envio de e-mail no Sprint 1.

## Definição de pronto
Código funcional, testes executados, documentação, demonstração com dados sintéticos e relatório final do Hermes com evidências. A aprovação do usuário é necessária para iniciar Sprint 2.
