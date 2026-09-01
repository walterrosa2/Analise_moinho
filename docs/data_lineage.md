# Linhagem dos Dados

De onde vem cada número que a plataforma exibe, e por quais transformações ele passou.

---

## Visão geral

```text
  8 planilhas Excel (originais, NUNCA modificadas)
  E:\Backup_HD_Walter\Moinho\Dados\...
        │  cópia (não movimento)
        ▼
  data/input/*.xlsx
        │  SHA-256 do arquivo → app.ingestion_batch
        │  hash já carregado com SUCCESS ⇒ skip
        ▼
  raw.*                      tudo TEXT + 6 metadados de linhagem
        │
        ├──────────────────► data/parquet/*.parquet   (o Excel não é relido)
        │
        │  staging: TRIM · decimal pt-BR · 'NULL'→NULL · domínios normalizados
        ▼
  analytics.dim_* / fact_* / bridge_*
        │
        ├─ as-of join de custos (LATERAL, cascata de 3 níveis)
        ├─ rateio de frete CT-e→NF-e (TON_WEIGHT)
        ├─ 23 verificações de qualidade  → app.data_quality_check
        └─ reconciliação com o 161       → app.reconciliation_result
        │
        ▼
  analytics.mv_*             recortes mensais pré-agregados
        │
        ▼
  src/repositories/          única camada que escreve SQL
        ▼
  app/pages/                 interface (nenhuma SQL aqui)
```

---

## Origem de cada tabela

| Tabela analítica | Fonte | Aba | Transformações principais |
|---|---|---|---|
| `fact_venda_item` | `VENDAS-DEV-RCA-CUSTOS…xlsx` | `Dados Vend_Dev 012023-072026` | tipagem, `CIF_FOB` normalizado, sinal de devolução preservado, as-of de custo, frete rateado |
| `fact_venda_documento` | idem | idem | agregação por `NUNOTA`; recebe `VLRNOTA` e o frete da carga |
| `fact_custo_pa` | idem | `Custos PA 012023 - 072026` | tipagem de datas, verificação de grão, outliers sinalizados |
| `dim_vendedor` | idem | `Vendedor_Supervisor` | papel de `config/seller_roles.yaml`; códigos com movimento e sem cadastro entram como `NAO_IDENTIFICADO` |
| `dim_produto` | idem (Custos PA) | — | classificação de `config/product_classification.yaml`, com origem registrada |
| `dim_cliente` | idem (Dados Vend_Dev) | — | CNPJ/CPF → SHA-256; cidade e ramo separados de seus códigos; primeira/última compra observadas no fato |
| `fact_cte` + `bridge_cte_nfe` | `CTE Venda…xlsx` | `CTE Venda 012023 - 072026` | explosão de `CHAVES_NFE_VENDA` por `;`, resolução contra a venda, rateio por tonelagem |
| `fact_positivado` | `POSITIVADOS V1.xlsx` | `parceiros positivados` | explosão de `PARC_POSITIVADOS` por `,`; conferência contra `QTD_POSITIVADOS` |
| `fact_gestao_diaria` | `161 - Gestão Diária Comercial V1.xlsx` | `Planilha1` | tipagem; usado só para reconciliação e tendência |
| `fact_despesa_mensal` | `161 … (OUTROS) V1.xlsx` | `Planilha1` | tipagem; `ORC/ANT` carregado sem interpretação (Q-03) |
| `fact_trigo_compra_mensal` | `Relatorio Compra de Trigo - Max.xlsx` | `Compra` | parser posicional (cabeçalho de 2 linhas, células mescladas) |
| `fact_trigo_estoque_mensal` | idem | `Estoque` | idem |
| `dim_regiao` | Dados Vend_Dev | — | `CODREG`/`NOMEREG` do movimento |
| `app.data_source_catalog` | `Inventário de Dados…xlsx` | `Sankhya`, `Outras fontes` | **coluna de credenciais bloqueada na leitura** (ADR-005) |

Fonte adicional carregada e não prevista na especificação:
`REGIÃO COMERCIAL POR REPRESENTANTE -SANATHIELLE.xlsx` (abas `GERAL` e `REPRESENTANTE`) —
mapa cidade → região comercial → representante, com 35 regiões nomeadas.

---

## Metadados de linhagem

Toda linha de `raw.*` carrega:

| Campo | Conteúdo |
|---|---|
| `_source_file` | nome do arquivo de origem |
| `_source_sheet` | aba de origem |
| `_source_row` | número da linha dentro da aba |
| `_ingestion_batch_id` | lote de carga (`app.ingestion_batch`) |
| `_ingested_at` | momento da carga |
| `_source_file_hash` | SHA-256 do arquivo, base da idempotência |

Com isso, qualquer número da tela pode ser rastreado até a linha exata da planilha:

```text
KPI na tela
  → repositório (SQL)
  → analytics.fact_venda_item (nunota + sequencia)
  → raw.vendas_dev (_source_row)
  → linha da planilha original
```

---

## Transformações que alteram valores

Estas são as únicas conversões que mudam a representação do dado. Todas acontecem no staging,
nunca na RAW:

| Transformação | Onde | Regra |
|---|---|---|
| Decimal pt-BR → float | `PERCCOM`, `VLRCOM`, `VLRUNIT`, `ACORDO`, `VLRNOTA` (CT-e), 161, positivados | vírgula é decimal; ponto é milhar |
| `'NULL'` textual → NULL | ~15 colunas | nunca preenchido com zero |
| `TRIM` | todo campo de texto | espaços à direita da origem |
| `CIF_FOB` normalizado | vendas | primeira letra é o código; valor bruto fica na RAW |
| Código separado da descrição | `NOMECIDPARC`, `RAMOATIVPARC`, `PERFILEMPPARC` | `'5357-UBERLANDIA'` → `'UBERLANDIA'` |
| CNPJ/CPF → SHA-256 | `dim_cliente` | apenas dígitos, antes do hash |
| Data como texto → DATE | `DTFATUR`, datas do CT-e | ISO com hora, ou `dd/mm/aaaa` |

**Nada mais é alterado.** Devolução continua negativa; anomalias históricas continuam lá;
outliers de custo são sinalizados, não corrigidos.

---

## Reprodutibilidade

```bash
py scripts/profile_sources.py      # perfil real das fontes
py scripts/deep_checks.py          # verificações cruzadas
py scripts/gen_source_contracts.py # contratos a partir do perfil
py scripts/run_pipeline.py         # pipeline completo (~80s)
py scripts/gen_docs.py             # dicionário e reconciliação, do banco
pytest                             # 59 testes
```

A carga é idempotente: rodar `run_pipeline.py` duas vezes seguidas não duplica nada — a segunda
execução pula todas as fontes cujo hash já foi carregado com sucesso.
