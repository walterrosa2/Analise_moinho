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

---

## Camada geográfica de mercado (Minas Gerais)

Única parte da plataforma que consome dados de fora do Moinho. Roda separada do
pipeline principal (`scripts/build_mercado_mg.py`) e nunca é chamada em tempo de tela.

```text
  API do IBGE  (as URLs vivem em config/mercado_mg.yaml, não no código)
    ├─ Localidades .............. 853 municípios de MG + hierarquia regional oficial
    ├─ Censo 2022 (agr. 4714) ... população residente por município
    ├─ CEMPRE 2024 (agr. 9528) .. unidades locais e pessoal ocupado
    │                             por município × classe CNAE 2.0
    └─ Malha municipal .......... GeoJSON para o mapa (data/geo/, fora do banco)
        │  retry com backoff · sem rede, o pipeline segue com o cache
        ▼
  data/parquet/mercado_mg_*.parquet
        │  src/staging/geografia.py
        ▼
  analytics.dim_municipio_mg          o denominador: 853 municípios
  analytics.map_cidade_ibge           pareamento auditável grafia → código IBGE
  analytics.fact_mercado_cnae         estabelecimentos por município e segmento
  analytics.dim_territorio_rca        território declarado (2 abas preservadas)
  analytics.fact_potencial_municipio  potencial estimado em t/mês
        │
        ▼
  analytics.mv_vendas_municipio_mg    venda por município × mês × classificação
  analytics.mv_mercado_municipio_mg   as três camadas sobrepostas, 1 linha/município
        │
        ▼
  src/repositories/geo.py  →  app/pages/p13_potencial_mg.py
```

### O ponto de integração: código IBGE do município

Três fontes escrevem o nome da cidade de três jeitos — `5357-UBERLANDIA` no ERP,
`Uberlândia, Minas Gerais` numa aba do arquivo de território e `UBERLANDIA` na outra.
O pareamento é um **dado inspecionável** em `analytics.map_cidade_ibge`, não um `LIKE`
escondido dentro de uma consulta. Cada grafia carrega o método que a ligou:

| Método | Significado | Resultado atual |
|---|---|---|
| `EXATO` | idênticas após normalização | 435 grafias |
| `SEM_CONECTIVOS` | idênticas após expandir abreviação e remover *de/do/da* | 9 grafias |
| `APROXIMADO` | similaridade alta, primeiro token igual, sem empate | 1 grafia |
| `AMBIGUO` | dois municípios disputam a grafia — não se decide sozinho | 0 |
| `NAO_ENCONTRADO` | sem correspondência segura | 76 grafias |

As 150 cidades com venda em MG parearam **sem uso de aproximação**. As 76 sem
correspondência são cidades de GO, SP, MT e DF que constam do arquivo de território —
ficarem de fora é o comportamento correto para uma análise restrita a Minas.

### O que é fato e o que é estimativa

| Camada | Natureza | Origem |
|---|---|---|
| Venda por município | **fato** | item de nota fiscal |
| Território do RCA | **fato** (declaração) | arquivo de região comercial |
| Estabelecimentos | **fato** | CEMPRE/IBGE |
| Consumo por estabelecimento | **medido** nos clientes do Moinho | mediana observada |
| Probabilidade de captura | **julgamento** | `config/mercado_mg.yaml`, não homologado |
| Potencial em t/mês | **estimativa** | produto dos quatro acima |
