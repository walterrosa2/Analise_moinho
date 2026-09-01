# Dicionário de Dados

> Gerado por `scripts/gen_docs.py` a partir do schema real do banco.
> Não editar à mão: rode o script novamente após alterar uma migration.

## Camadas

| Schema | Papel |
|---|---|
| `raw` | Cópia fiel do Excel, tudo TEXT, com metadados de linhagem. Nunca alterada. |
| `staging` | Transformações intermediárias (em memória, no ETL). |
| `analytics` | Modelo dimensional consumido pela aplicação. |
| `app` | Estado da plataforma: lotes, qualidade, reconciliação, visões salvas. |

---

## Schema `analytics`

### `analytics.bridge_cte_nfe`

> Um CT-e atende N notas. Frete rateado por tonelagem (TON_WEIGHT). O rateio NUNCA e escondido: % nao alocado aparece na UI.

- Linhas: **45.240** · Colunas: 12

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `bridge_id` | bigint | não | — |
| `frete_id` | bigint | não | — |
| `chavecte` | text | sim | — |
| `chave_nfe` | text | sim | — |
| `numero_nota_venda` | text | sim | — |
| `nunota_venda` | bigint | sim | — |
| `match_status` | text | não | — |
| `ton_nfe` | numeric | sim | — |
| `allocation_weight` | numeric | sim | — |
| `allocation_method` | text | não | — |
| `vlrfrete_alocado` | numeric | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.dim_cliente`

- Linhas: **2.233** · Colunas: 15

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `codparc` | bigint | não | — |
| `parceiro` | text | sim | — |
| `razao_social` | text | sim | — |
| `cgccpf_hash` | text | sim | SHA-256 do CNPJ/CPF. O documento em claro nao entra no DW (LGPD). |
| `tipo_pessoa` | text | sim | — |
| `cidade` | text | sim | — |
| `uf` | text | sim | — |
| `ramo_atividade` | text | sim | — |
| `perfil_empresa` | text | sim | — |
| `codreg` | bigint | sim | REGIAO COMERCIAL (atribuicao interna). A geografia real do cliente esta em uf/cidade. |
| `nomereg` | text | sim | — |
| `primeira_compra` | date | sim | — |
| `ultima_compra` | date | sim | — |
| `qtd_meses_ativos` | integer | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.dim_data`

- Linhas: **2.922** · Colunas: 12

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `data_id` | date | não | — |
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `dia` | smallint | não | — |
| `ano_mes` | text | não | — |
| `trimestre` | smallint | não | — |
| `semestre` | smallint | não | — |
| `dia_semana` | smallint | não | — |
| `nome_mes` | text | não | — |
| `inicio_mes` | date | não | — |
| `fim_mes` | date | não | — |
| `is_fim_semana` | boolean | não | — |

### `analytics.dim_produto`

- Linhas: **101** · Colunas: 9

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `codprod` | bigint | não | — |
| `descrprod` | text | sim | — |
| `codgrupoprod` | bigint | sim | — |
| `grupo_produto` | text | sim | — |
| `unidade` | text | sim | — |
| `classificacao` | text | sim | — |
| `classificacao_origem` | text | sim | Rastreabilidade: como o produto recebeu a classificacao. Nunca inferir em silencio. |
| `classificacao_versao` | text | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.dim_regiao`

- Linhas: **98** · Colunas: 3

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `codreg` | bigint | não | — |
| `nomereg` | text | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.dim_transportador`

- Linhas: **491** · Colunas: 3

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `codparc_transp` | bigint | não | — |
| `nome_transp` | text | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.dim_vendedor`

- Linhas: **459** · Colunas: 17

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `codvend` | bigint | não | — |
| `apelido` | text | sim | — |
| `tipo_vend` | text | sim | — |
| `vendedor_ativo` | text | sim | — |
| `ativo` | boolean | sim | — |
| `codparc` | bigint | sim | — |
| `nomeparc` | text | sim | — |
| `cidade` | text | sim | — |
| `estado` | text | sim | — |
| `codregiao` | bigint | sim | — |
| `regiao` | text | sim | — |
| `papel_analitico` | text | não | Vem de config/seller_roles.yaml. Default NAO_CLASSIFICADO ate validacao do negocio. |
| `grupo_analitico` | text | sim | — |
| `papel_origem` | text | não | — |
| `primeira_venda` | date | sim | — |
| `ultima_venda` | date | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_cte`

- Linhas: **32.789** · Colunas: 22

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `frete_id` | bigint | não | — |
| `codemp` | integer | sim | — |
| `nunota` | bigint | sim | — |
| `numnota` | bigint | sim | — |
| `serienota` | text | sim | — |
| `chavecte` | text | sim | — |
| `dtneg` | date | sim | — |
| `dtentsai` | date | sim | — |
| `dtfatur` | date | sim | — |
| `data_referencia` | date | sim | — |
| `ano` | smallint | sim | — |
| `mes` | smallint | sim | — |
| `ano_mes` | text | sim | — |
| `codtipoper` | integer | sim | — |
| `descroper` | text | sim | — |
| `ordemcarga` | bigint | sim | — |
| `codparc` | bigint | sim | — |
| `nomeparc` | text | sim | — |
| `vlrnota` | numeric | sim | — |
| `qtd_nfe_vinculadas` | integer | não | — |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_custo_pa`

> Seis conceitos de custo coexistem. NENHUM e "o custo oficial" ate homologacao da Controladoria.

- Linhas: **29.135** · Colunas: 20

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `custo_id` | bigint | não | — |
| `codprod` | bigint | não | — |
| `codemp` | integer | sim | — |
| `codlocal` | integer | sim | — |
| `dtatual` | date | não | — |
| `ano` | smallint | sim | — |
| `mes` | smallint | sim | — |
| `ano_mes` | text | sim | — |
| `produto` | text | sim | — |
| `codgrupoprod` | bigint | sim | — |
| `grupo_produto` | text | sim | — |
| `unidade` | text | sim | — |
| `cusmed` | numeric | sim | — |
| `cusmedicm` | numeric | sim | — |
| `cussemicm` | numeric | sim | — |
| `cusrep` | numeric | sim | — |
| `cusger` | numeric | sim | — |
| `cusvariavel` | numeric | sim | — |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_despesa_mensal`

- Linhas: **396** · Colunas: 10

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `despesa_id` | bigint | não | — |
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `ano_mes` | text | não | — |
| `descricao` | text | não | — |
| `orc_ant` | numeric | sim | pending_business_validation: nao assumir se e Orcado ou Ano Anterior. |
| `atual` | numeric | sim | — |
| `perc_var` | numeric | sim | — |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_gestao_diaria`

- Linhas: **1.545** · Colunas: 15

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `gestao_id` | bigint | não | — |
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `ano_mes` | text | não | — |
| `tipo` | text | não | — |
| `cod_cla` | text | sim | — |
| `desc_cla` | text | sim | — |
| `valor` | numeric | sim | — |
| `perc_ating_vlr` | numeric | sim | — |
| `tonelada` | numeric | sim | — |
| `perc_ating_ton` | numeric | sim | — |
| `markup` | numeric | sim | — |
| `pc_medio` | numeric | sim | — |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_positivado`

- Linhas: **2.871** · Colunas: 9

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `positivado_id` | bigint | não | — |
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `ano_mes` | text | não | — |
| `codparc` | bigint | não | — |
| `cliente_existe_dim` | boolean | não | — |
| `periodo_implantacao_erp` | boolean | não | TRUE para os primeiros meses do Sankhya (dados fora do padrao). Dados NUNCA sao excluidos. |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_positivado_mes`

- Linhas: **67** · Colunas: 10

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `ano_mes` | text | não | — |
| `qtd_positivados_fonte` | integer | sim | — |
| `qtd_positivados_explodido` | integer | sim | — |
| `vlrtot_positivados` | numeric | sim | — |
| `vlrtot_geral` | numeric | sim | — |
| `perc_positivados_geral` | numeric | sim | — |
| `periodo_implantacao_erp` | boolean | não | — |
| `_batch_id` | bigint | sim | — |

### `analytics.fact_trigo_compra_mensal`

- Linhas: **31** · Colunas: 11

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `ano_mes` | text | não | — |
| `ton_trigo` | numeric | sim | — |
| `ton_triticale` | numeric | sim | — |
| `ton_total` | numeric | sim | — |
| `vlr_trigo` | numeric | sim | — |
| `vlr_triticale` | numeric | sim | — |
| `vlr_total` | numeric | sim | — |
| `preco_medio` | numeric | sim | — |
| `_batch_id` | bigint | sim | — |

### `analytics.fact_trigo_estoque_mensal`

- Linhas: **19** · Colunas: 6

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `ano` | smallint | não | — |
| `mes` | smallint | não | — |
| `ano_mes` | text | não | — |
| `ton_estoque` | numeric | sim | — |
| `preco_medio` | numeric | sim | — |
| `_batch_id` | bigint | sim | — |

### `analytics.fact_venda_documento`

- Linhas: **87.274** · Colunas: 35

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `nunota` | bigint | não | — |
| `codemp` | integer | sim | — |
| `numnota` | bigint | sim | — |
| `chavenfe` | text | sim | — |
| `dtneg` | date | sim | — |
| `dtfatur` | date | sim | — |
| `dtentsai` | date | sim | — |
| `data_referencia` | date | sim | — |
| `ano` | smallint | sim | — |
| `mes` | smallint | sim | — |
| `ano_mes` | text | sim | — |
| `codtipoper` | integer | sim | — |
| `descroper` | text | sim | — |
| `tipmov` | text | sim | — |
| `is_devolucao` | boolean | não | — |
| `cif_fob` | text | sim | — |
| `cidorigem` | text | sim | — |
| `ciddestino` | text | sim | — |
| `uforigem` | text | sim | — |
| `ufdestino` | text | sim | — |
| `vlrfrete_rateado_nota` | numeric | sim | — |
| `ordemcarga` | bigint | sim | — |
| `cif_fob_ordemcarga` | text | sim | — |
| `codparctransp` | bigint | sim | — |
| `vlrfrete_ordemcarga` | numeric | sim | — |
| `codparc` | bigint | sim | — |
| `codvend` | bigint | sim | — |
| `codsupervisor` | bigint | sim | — |
| `codreg` | bigint | sim | — |
| `nomereg` | text | sim | — |
| `vlrnota` | numeric | sim | Valor do DOCUMENTO. Proibido somar no grao de item (repete-se nas linhas). |
| `acordo` | text | sim | — |
| `observacaonota` | text | sim | — |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `analytics.fact_venda_item`

> Grao NUNOTA+SEQUENCIA. Devolucoes preservam o sinal negativo da origem.

- Linhas: **204.037** · Colunas: 47

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `item_id` | bigint | não | — |
| `nunota` | bigint | não | — |
| `sequencia` | integer | não | — |
| `codemp` | integer | sim | — |
| `data_referencia` | date | sim | — |
| `ano` | smallint | sim | — |
| `mes` | smallint | sim | — |
| `ano_mes` | text | sim | — |
| `codprod` | bigint | sim | — |
| `codparc` | bigint | sim | — |
| `codvend` | bigint | sim | — |
| `codsupervisor` | bigint | sim | — |
| `codreg` | bigint | sim | — |
| `codlocalorig` | integer | sim | — |
| `codtrib` | text | sim | — |
| `controle` | text | sim | — |
| `codcfo` | bigint | sim | — |
| `tipmov` | text | sim | — |
| `is_devolucao` | boolean | não | — |
| `cif_fob` | text | sim | — |
| `codvol` | text | sim | — |
| `qtd` | numeric | sim | — |
| `pesoliq` | numeric | sim | — |
| `tonliq` | numeric | sim | — |
| `pesobruto` | numeric | sim | — |
| `tonbruto` | numeric | sim | — |
| `vlrunit` | numeric | sim | — |
| `vlrtot` | numeric | sim | — |
| `vlrdesc` | numeric | sim | — |
| `vlrrepred` | numeric | sim | — |
| `perccom` | numeric | sim | — |
| `vlrcom` | numeric | sim | — |
| `vlricms` | numeric | sim | — |
| `vlrsubst` | numeric | sim | — |
| `vlrfrete_alocado` | numeric | sim | — |
| `frete_alocado_metodo` | text | sim | — |
| `cusmed` | numeric | sim | — |
| `cusmedicm` | numeric | sim | — |
| `cussemicm` | numeric | sim | — |
| `cusrep` | numeric | sim | — |
| `cusger` | numeric | sim | — |
| `cusvariavel` | numeric | sim | — |
| `cost_match_date` | date | sim | — |
| `cost_age_days` | integer | sim | — |
| `cost_match_status` | text | sim | EXATO=custo na mesma data; ANTERIOR=custo vigente mais recente <= data; SEM_CUSTO=nao encontrado. |
| `_batch_id` | bigint | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

---

## Schema `app`

### `app.data_quality_check`

- Linhas: **23** · Colunas: 13

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `check_id` | bigint | não | — |
| `batch_id` | bigint | sim | — |
| `run_at` | timestamp with time zone | não | — |
| `check_name` | text | não | — |
| `category` | text | não | — |
| `target_object` | text | não | — |
| `severity` | text | não | — |
| `status` | text | não | — |
| `observed` | numeric | sim | — |
| `expected` | numeric | sim | — |
| `tolerance` | numeric | sim | — |
| `message` | text | sim | — |
| `evidence_sql` | text | sim | SQL que reproduz as linhas problematicas ("Ver evidencia" na UI). |

### `app.data_source_catalog`

> Backlog/inventario de fontes. Credenciais NUNCA sao importadas (ver src/ingestion/catalog.py).

- Linhas: **42** · Colunas: 10

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `catalog_id` | bigint | não | — |
| `origem` | text | sim | — |
| `relatorio` | text | sim | — |
| `descricao` | text | sim | — |
| `periodicidade` | text | sim | — |
| `responsavel` | text | sim | — |
| `status` | text | sim | — |
| `observacoes` | text | sim | — |
| `_source_file` | text | sim | — |
| `_ingested_at` | timestamp with time zone | não | — |

### `app.ingestion_batch`

> Um registro por (fonte, aba, hash de arquivo). Hash ja carregado com SUCCESS = skip.

- Linhas: **39** · Colunas: 14

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `batch_id` | bigint | não | — |
| `source_id` | text | não | — |
| `source_file` | text | não | — |
| `source_sheet` | text | sim | — |
| `source_file_hash` | text | não | — |
| `file_size_bytes` | bigint | sim | — |
| `file_modified_at` | timestamp with time zone | sim | — |
| `rows_read` | integer | sim | — |
| `rows_loaded` | integer | sim | — |
| `status` | text | não | RUNNING \| SUCCESS \| FAILED \| SKIPPED (hash ja carregado) \| SUPERSEDED (substituido por recarga forcada) |
| `error_message` | text | sim | — |
| `started_at` | timestamp with time zone | não | — |
| `finished_at` | timestamp with time zone | sim | — |
| `duration_ms` | integer | sim | — |

### `app.reconciliation_result`

> Comparacao entre o modelo analitico e as fontes gerenciais (161, OUTROS, CTE). Nunca ajustar dados para "bater": divergencia deve ser explicada.

- Linhas: **1.064** · Colunas: 13

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `recon_id` | bigint | não | — |
| `run_at` | timestamp with time zone | não | — |
| `scope` | text | não | — |
| `period` | text | sim | — |
| `dimension` | text | sim | — |
| `metric_id` | text | não | — |
| `value_source` | numeric | sim | — |
| `value_model` | numeric | sim | — |
| `diff_abs` | numeric | sim | — |
| `diff_pct` | numeric | sim | — |
| `tolerance_pct` | numeric | sim | — |
| `status` | text | não | — |
| `explanation` | text | sim | — |

### `app.saved_views`

- Linhas: **0** · Colunas: 7

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `view_id` | bigint | não | — |
| `name` | text | não | — |
| `description` | text | sim | — |
| `owner` | text | não | — |
| `config` | jsonb | não | — |
| `created_at` | timestamp with time zone | não | — |
| `updated_at` | timestamp with time zone | não | — |

### `app.schema_migrations`

> Migrations SQL ja aplicadas (idempotencia por checksum).

- Linhas: **6** · Colunas: 5

| Coluna | Tipo | Nulo? | Observação |
|---|---|---|---|
| `version` | text | não | — |
| `filename` | text | não | — |
| `checksum` | text | não | — |
| `applied_at` | timestamp with time zone | não | — |
| `duration_ms` | integer | sim | — |

---

## Schema `raw`

### `raw.catalogo_fontes`

- Linhas: **36** · Colunas: 9

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.catalogo_fontes_externas`

- Linhas: **6** · Colunas: 9

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.cte`

- Linhas: **32.789** · Colunas: 22

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.custos_pa`

- Linhas: **29.135** · Colunas: 20

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.gestao_diaria_161`

- Linhas: **1.545** · Colunas: 17

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.gestao_diaria_outros`

- Linhas: **396** · Colunas: 12

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.positivados_mensal`

- Linhas: **67** · Colunas: 13

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.regiao_comercial_geral`

- Linhas: **218** · Colunas: 11

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.regiao_representante`

- Linhas: **394** · Colunas: 12

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.trigo_compra`

- Linhas: **35** · Colunas: 15

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.trigo_estoque`

- Linhas: **22** · Colunas: 9

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.vendas_dev`

- Linhas: **204.037** · Colunas: 61

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

### `raw.vendedores`

- Linhas: **458** · Colunas: 23

Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados `_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.

---

## Views do schema `analytics`

| Objeto | Tipo | Linhas |
|---|---|---|
| `analytics.mv_cost_product_month` | materialized view | 3.270 |
| `analytics.mv_custo_mediana_produto` | materialized view | 101 |
| `analytics.mv_freight_carrier_month` | materialized view | 430 |
| `analytics.mv_freight_route_month` | materialized view | 4.389 |
| `analytics.mv_positivados_cohort` | materialized view | 38.343 |
| `analytics.mv_sales_customer_month` | materialized view | 44.754 |
| `analytics.mv_sales_month` | materialized view | 44 |
| `analytics.mv_sales_product_month` | materialized view | 3.344 |
| `analytics.mv_sales_region_month` | materialized view | 9.325 |
| `analytics.mv_sales_seller_month` | materialized view | 1.225 |
| `analytics.mv_trigo_cost_month` | materialized view | 44 |
| `analytics.v_operacao_sem_receita` | view | 2 |
| `analytics.v_venda_item` | view | 204.037 |

---

## Registro de métricas

Fonte: `src/metrics/registry.py`. Nenhuma fórmula vive dentro de uma página.

| ID | Métrica | Unidade | Grão | Fórmula | Status |
|---|---|---|---|---|---|
| `clientes_ativos` | Clientes ativos | un | agregado | `COUNT(DISTINCT codparc)` | PROVISIONAL |
| `clientes_novos` | Clientes novos (positivados) | un | mês | `COUNT(*) FROM fact_positivado` | RECONCILIADA |
| `ton_por_cliente` | Toneladas por cliente | t | agregado | `SUM(tonliq) / COUNT(DISTINCT codparc)` | PROVISIONAL |
| `comissao` | Comissão | R$ | item | `SUM(vlrcom)` | PROVISIONAL |
| `desconto` | Desconto concedido | R$ | item | `SUM(vlrdesc)` | PROVISIONAL |
| `devolucoes` | Devoluções | R$ | item | `SUM(vlrtot) WHERE is_devolucao` | RECONCILIADA |
| `pmv` | PMV — preço médio de venda | R$/t | agregado | `SUM(vlrtot) / SUM(tonliq), ambos filtrando CODTIPOPER NOT IN (3107, 3102)` | PROVISIONAL |
| `receita_liquida` | Receita líquida | R$ | item (NUNOTA+SEQUENCIA) | `SUM(vlrtot)` | RECONCILIADA |
| `taxa_devolucao` | Taxa de devolução | % | agregado | `-SUM(devolucoes) / NULLIF(SUM(vendas_brutas), 0) * 100` | PROVISIONAL |
| `ticket_medio` | Ticket médio por documento | R$ | agregado | `SUM(vlrtot) / COUNT(DISTINCT nunota)` | PROVISIONAL |
| `vendas_brutas` | Vendas brutas | R$ | item | `SUM(vlrtot) WHERE NOT is_devolucao` | RECONCILIADA |
| `volume_liquido_t` | Volume líquido | t | item | `SUM(tonliq)` | RECONCILIADA |
| `custo_total_cusger` | Custo total — CUSGER | R$ | item | `SUM(qtd * cusger) FILTER (WHERE NOT custo_outlier)` | PROVISIONAL |
| `custo_total_cusmed` | Custo total — CUSMED | R$ | item | `SUM(qtd * cusmed) FILTER (WHERE NOT custo_outlier)` | PROVISIONAL |
| `custo_total_cusmedicm` | Custo total — CUSMEDICM | R$ | item | `SUM(qtd * cusmedicm) FILTER (WHERE NOT custo_outlier)` | PROVISIONAL |
| `custo_total_cusrep` | Custo total — CUSREP | R$ | item | `SUM(qtd * cusrep) FILTER (WHERE NOT custo_outlier)` | PROVISIONAL |
| `custo_total_cussemicm` | Custo total — CUSSEMICM | R$ | item | `SUM(qtd * cussemicm) FILTER (WHERE NOT custo_outlier)` | PROVISIONAL |
| `custo_total_cusvariavel` | Custo total — CUSVARIAVEL | R$ | item | `SUM(qtd * cusvariavel) FILTER (WHERE NOT custo_outlier)` | PROVISIONAL |
| `margem_proxy_pct_cusger` | Margem Proxy % — Base CUSGER | % | agregado | `(SUM(vlrtot) - SUM(qtd * cusger)) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier` | PROVISIONAL |
| `margem_proxy_pct_cusmed` | Margem Proxy % — Base CUSMED | % | agregado | `(SUM(vlrtot) - SUM(qtd * cusmed)) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier` | PROVISIONAL |
| `margem_proxy_pct_cusmedicm` | Margem Proxy % — Base CUSMEDICM | % | agregado | `(SUM(vlrtot) - SUM(qtd * cusmedicm)) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier` | PROVISIONAL |
| `margem_proxy_pct_cusrep` | Margem Proxy % — Base CUSREP | % | agregado | `(SUM(vlrtot) - SUM(qtd * cusrep)) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier` | PROVISIONAL |
| `margem_proxy_pct_cussemicm` | Margem Proxy % — Base CUSSEMICM | % | agregado | `(SUM(vlrtot) - SUM(qtd * cussemicm)) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier` | PROVISIONAL |
| `margem_proxy_pct_cusvariavel` | Margem Proxy % — Base CUSVARIAVEL | % | agregado | `(SUM(vlrtot) - SUM(qtd * cusvariavel)) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier` | PROVISIONAL |
| `margem_proxy_cusger` | Margem Proxy — Base CUSGER | R$ | agregado | `SUM(vlrtot) - SUM(qtd * cusger), ambos excluindo linhas com outlier de custo` | PROVISIONAL |
| `margem_proxy_cusmed` | Margem Proxy — Base CUSMED | R$ | agregado | `SUM(vlrtot) - SUM(qtd * cusmed), ambos excluindo linhas com outlier de custo` | PROVISIONAL |
| `margem_proxy_cusmedicm` | Margem Proxy — Base CUSMEDICM | R$ | agregado | `SUM(vlrtot) - SUM(qtd * cusmedicm), ambos excluindo linhas com outlier de custo` | PROVISIONAL |
| `margem_proxy_cusrep` | Margem Proxy — Base CUSREP | R$ | agregado | `SUM(vlrtot) - SUM(qtd * cusrep), ambos excluindo linhas com outlier de custo` | PROVISIONAL |
| `margem_proxy_cussemicm` | Margem Proxy — Base CUSSEMICM | R$ | agregado | `SUM(vlrtot) - SUM(qtd * cussemicm), ambos excluindo linhas com outlier de custo` | PROVISIONAL |
| `margem_proxy_cusvariavel` | Margem Proxy — Base CUSVARIAVEL | R$ | agregado | `SUM(vlrtot) - SUM(qtd * cusvariavel), ambos excluindo linhas com outlier de custo` | PROVISIONAL |
| `pct_frete_nao_alocado` | % de frete não alocado | % | agregado | `(frete_total_cte - frete_alocado) / frete_total_cte * 100` | RECONCILIADA |
| `frete_alocado` | Frete alocado | R$ | vínculo CT-e × NF-e | `SUM(vlrfrete_alocado) WHERE match_status <> 'SEM_VINCULO'` | PROVISIONAL |
| `frete_por_ton` | Frete por tonelada | R$/t | agregado | `SUM(vlrfrete_alocado) / SUM(ABS(tonliq))` | PROVISIONAL |
| `frete_sobre_receita` | Frete sobre receita | % | agregado | `SUM(vlrfrete_alocado) / NULLIF(SUM(vlrtot), 0) * 100` | PROVISIONAL |
| `icms` | ICMS destacado | R$ | item | `SUM(vlricms)` | PROVISIONAL |
| `substituicao` | ICMS substituição tributária | R$ | item | `SUM(vlrsubst)` | PROVISIONAL |
