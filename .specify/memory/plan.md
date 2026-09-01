# Plano Técnico — Plataforma Analítica Moinho Sete Irmãos

Referência: `.specify/memory/specify.md` · Fonte normativa: `ESPECIFICACAO_TECNICA_PLATAFORMA_ANALITICA_MOINHO.md`

---

## 1. Arquitetura em camadas

```text
Streamlit UI (app/)
      ↓  só chama serviços; nenhuma linha de SQL nas páginas
Services / Analytics (src/analytics, src/insights)
      ↓
Metrics Registry (src/metrics)   ← fórmula, grão, unidade, status, regra de sinal
      ↓
Repositories (src/repositories)  ← única camada que escreve SQL
      ↓
PostgreSQL 16 (schemas raw / staging / analytics / app)
```

A separação permite trocar Streamlit por FastAPI + React sem tocar em regra analítica.

---

## 2. Fluxo de dados

```text
data/input/*.xlsx  (cópia; originais intocados)
   │  hash SHA-256 → app.ingestion_batch (skip se já carregado com SUCCESS)
   ▼
raw.*              DDL gerado do cabeçalho real; TODAS as colunas TEXT + 6 metadados
   │
   ├─→ data/parquet/*.parquet   (Excel nunca é relido em análise)
   ▼
staging.*          tipagem, TRIM, parser decimal pt-BR, 'NULL'→NULL, normalização de domínios
   │
   ▼
analytics.*        dim_ / fact_ / bridge_  (+ as-of join de custos, rateio de frete)
   │
   ├─→ testes de qualidade  → app.data_quality_check
   ├─→ reconciliação 161    → app.reconciliation_result
   ▼
mv_*               materialized views por recorte mensal
```

---

## 3. Decisões técnicas

| # | Decisão | Motivo |
|---|---|---|
| D-01 | PostgreSQL 16 em Docker, porta **5434** | 5432/5433 já ocupadas na máquina do desenvolvedor |
| D-02 | Migrations em **SQL numerado** com runner próprio, não autogeração Alembic | DW com schemas, MVs e comentários; SQL explícito é auditável pelo consultor (ADR-002) |
| D-03 | RAW com DDL **gerado do cabeçalho real**, tudo TEXT | Layout de Excel muda; carga nunca deve falhar silenciosamente por tipo |
| D-04 | **Polars** para ETL; pandas só onde necessário | 204k×55 lidos em segundos; API de expressão explícita |
| D-05 | **fastexcel/calamine** para ler Excel | 72 MB lidos sem estourar memória |
| D-06 | Carga em massa via **COPY** do psycopg | ordens de grandeza mais rápido que INSERT |
| D-07 | As-of join de custos executado no **PostgreSQL** com `LATERAL` | evita trazer 29k×204k para a memória |
| D-08 | Métricas em **registry declarativo** (`src/metrics/registry.py`) | fórmula única, status por métrica, nunca espalhada nas páginas |
| D-09 | Cache do Streamlit com TTL nas consultas de repositório | consultas repetidas em reunião |
| D-10 | CNPJ/CPF apenas como **SHA-256** no DW | LGPD; nenhum uso analítico exige o documento em claro |

---

## 4. Modelo dimensional

**Dimensões:** `dim_data`, `dim_cliente`, `dim_produto`, `dim_vendedor`, `dim_regiao`, `dim_transportador`

**Fatos:**

| Tabela | Grão | Verificado na Fase 0 |
|---|---|---|
| `fact_venda_documento` | `NUNOTA` | 87.274 documentos |
| `fact_venda_item` | `NUNOTA + SEQUENCIA` | 204.037 — **único, 0 duplicadas** |
| `fact_custo_pa` | `CODPROD + CODEMP + CODLOCAL + DTATUAL` | 29.135 — **único** |
| `fact_cte` | surrogate `frete_id` | `CHAVECTE` ausente em 3,46% → PK natural inviável |
| `bridge_cte_nfe` | `frete_id × chave_nfe` | 41.037 vínculos |
| `fact_positivado` | `ANO + MES + CODPARC` | 67 meses, explosão bate 100% |
| `fact_gestao_diaria` | `ANO + MES + TIPO + COD_CLA` | 1.545 — **único** |
| `fact_despesa_mensal` | `ANO + MES + DESCRICAO` | 396 — **único** |
| `fact_trigo_compra_mensal` / `_estoque_mensal` | `ANO + MES` | 31 / 19 meses reais |

---

## 5. Regras analíticas centrais

### 5.1 Sinal e devolução
`TIPMOV='D'` ⇒ todas as medidas já vêm negativas na origem (confirmado: 23.137/23.137).
Receita líquida = `SUM(VLRTOT)` sem `ABS`, sem `CASE`. Vendas brutas e devoluções são
métricas separadas, filtradas por `is_devolucao`.

### 5.2 PMV (preço médio de venda)
`SUM(VLRTOT) / SUM(TONLIQ)` — **excluindo** operações sem receita (bonificação, amostra, doação),
que têm tonelagem e valor zero e rebaixariam artificialmente o preço. O filtro é configurável e
exibido na UI.

### 5.3 As-of join de custos
Para cada item: maior `DTATUAL <= data_referencia` do mesmo `CODPROD`, com tentativa em cascata —
(1) `CODPROD+CODEMP+CODLOCAL`, (2) `CODPROD+CODEMP`, (3) `CODPROD` — registrando
`cost_match_status`, `cost_match_date` e `cost_age_days`. Data de referência padrão `DTFATUR`
(configurável em `.env`).

### 5.4 Rateio de frete
`frete_alocado_NF = VLRNOTA_CTE × TON_NF / TON_total_vinculada_ao_CTE`, `allocation_method='TON_WEIGHT'`.
Quando não há tonelagem, cai para rateio igualitário (`EQUAL_SPLIT`), sempre gravado.
CT-e sem vínculo permanece com `SEM_VINCULO` e entra no indicador de % não alocado.

### 5.5 Margem proxy
`margem_proxy_<custo> = SUM(VLRTOT) - SUM(TONLIQ × custo_unitário)`, rotulada
**"Margem Proxy — Base CUSGER"** etc. Nunca "margem".

---

## 6. Páginas (ordem da seção 45, Passo 8)

1. Qualidade e Reconciliação · 2. Visão Geral · 3. Gestão Diária/Mix · 4. Vendas e Devoluções ·
5. Regional e Territorial · 6. RCAs/Vendedores · 7. Clientes · 8. Positivados/Coortes ·
9. Custos · 10. Logística/CT-e · 11. Trigo × Custo × PMV · 12. Explorador · 13. Admin/Diagnóstico

---

## 7. Riscos

| Risco | Mitigação |
|---|---|
| Papel do vendedor não homologado (canais como "V DIRETA FARELO" tratados como RCA) | `config/seller_roles.yaml` com default por `TipoVend` + status `NAO_HOMOLOGADO` visível |
| Semântica de `ORC/ANT` desconhecida | Coluna carregada, rotulada `pending_business_validation` |
| 4,54% dos CT-e sem NF-e correspondente | Indicador de cobertura em tela; nunca embutido no total |
| Divergência com o 161 (fontes de períodos diferentes: 161 cobre 2020+, vendas 2023+) | Reconciliação restrita à janela comum; divergência explicada, jamais ajustada |
