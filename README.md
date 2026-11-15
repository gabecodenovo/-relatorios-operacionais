# SmartOps CLI

Ferramenta de linha de comando para **triagem, registro e geracao de relatorios operacionais** de pequenas empresas. Feita apenas com a biblioteca padrao do Python (sem dependencias externas).

O cenario: uma empresa recebe demandas de clientes/areas por e-mail, planilha e WhatsApp, e perde prazo porque nao tem um funil unico. O SmartOps registra cada demanda em SQLite, classifica a prioridade automaticamente, calcula SLA e gera relatorio e exportacao prontos para envio.

## Funcionalidades

- **`seed`** — popula o banco com 14 registros ficticios realistas (demonstracao imediata em entrevista ou teste com cliente).
- **`add`** — adiciona um registro e calcula a prioridade (`ALTA`, `MEDIA`, `BAIXA`) por valor, prazo e categoria.
- **`list`** — lista registros com filtros de status, prioridade e categoria.
- **`update`** — atualiza status e/ou observacao de um registro pelo ID.
- **`report`** — resumo executivo no terminal: totais, valores, taxa de conclusao, distribuicoes, itens criticos e atrasados.
- **`export`** — gera CSV e/ou JSON na pasta `exports/`, com data e hora no nome do arquivo.

## Arquitetura

| Arquivo | Responsabilidade |
| --- | --- |
| `main.py` | Interface de linha de comando (`argparse`), validacoes e formatacao da saida. |
| `database.py` | Conexao SQLite (`smartops.db`), criacao da tabela `records`, CRUD e consultas filtradas. |
| `processor.py` | Regras de negocio: prioridade automatica, SLA, deteccao de atraso e resumo executivo. |
| `exporter.py` | Exportacao dos relatorios enriquecidos para CSV e JSON. |

O banco e criado automaticamente na primeira execucao (`smartops.db`), com indices em `status` e `prioridade`.

## Instalacao

Requisito: **Python 3.8+** (nenhum `pip install` necessario).

```bash
cd Projeto-2-SmartOps
python main.py
```

Sem argumentos, a CLI mostra a ajuda com todos os comandos.

## Exemplos de uso

```bash
# 1) Popular o banco com dados de demonstracao
python main.py seed

# 2) Ver o resumo executivo
python main.py report

# 3) Cadastrar uma demanda (a prioridade e calculada sozinha)
python main.py add --cliente "Padaria Pao Dourado" --titulo "Automacao do estoque" \
  --categoria Automacao --valor 3500 --prazo 5 --obs "Planilha com 3 abas duplicadas"

# 4) Listar somente demandas abertas de prioridade alta
python main.py list --status ABERTO --prioridade ALTA

# 5) Concluir um registro
python main.py update 3 --status CONCLUIDO --obs "Entrega validada pelo cliente"

# 6) Exportar tudo em CSV + JSON
python main.py export --formato ambos

# 7) Exportar apenas os atrasados de uma categoria
python main.py export --categoria Suporte --formato csv
```

## Regras de prioridade

| Criterio | Pontos |
| --- | --- |
| Valor >= R$ 5.000 | +2 |
| Valor >= R$ 2.000 | +1 |
| Prazo <= 2 dias | +3 |
| Prazo <= 5 dias | +2 |
| Prazo <= 10 dias | +1 |
| Categoria critica (Suporte, Urgencia, Manutencao, Sistema) | +2 |

- **ALTA**: 5 pontos ou mais (SLA de 3 dias)
- **MEDIA**: 3 ou 4 pontos (SLA de 7 dias)
- **BAIXA**: ate 2 pontos (SLA de 15 dias)

Um registro e considerado **atrasado** quando a data limite (`criado_em` + `prazo_dias`) ja passou e o status nao e `CONCLUIDO`.

## Estrutura da tabela `records`

| Coluna | Tipo | Descricao |
| --- | --- | --- |
| `id` | INTEGER | Chave primaria. |
| `cliente` | TEXT | Cliente ou area responsavel. |
| `titulo` | TEXT | Titulo curto da demanda. |
| `categoria` | TEXT | Automacao, Integracao, Suporte, Dados, Relatorios... |
| `valor` | REAL | Valor estimado em reais. |
| `prazo_dias` | INTEGER | Prazo em dias corridos. |
| `prioridade` | TEXT | `ALTA`, `MEDIA` ou `BAIXA`. |
| `status` | TEXT | `ABERTO`, `EM_ANDAMENTO` ou `CONCLUIDO`. |
| `observacao` | TEXT | Notas livres. |
| `criado_em` | TEXT | Data/hora de criacao (ISO). |
| `atualizado_em` | TEXT | Data/hora da ultima alteracao (ISO). |

O comando `export` acrescenta as colunas calculadas `data_limite`, `dias_restantes` e `atrasado`.

## Por que este projeto e bom para portfolio

- Modelagem de dados real, com persistencia e indices.
- Regra de negocio explicita e testavel (prioridade/SLA/atraso).
- CLI com tratamento de erro amigavel (ID inexistente, banco vazio, entrada invalida, filtro sem resultado).
- Saida pronta para o cliente final: resumo no terminal, CSV para planilha e JSON para integracao.
- Codigo modular, docstrings e comentarios em portugues.
