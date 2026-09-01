# Checklist de Implementação

Legenda: `[x]` concluído · `[ ]` pendente · `[~]` em andamento

---

## Fase 0 — Discovery técnico  ✅ GATE CUMPRIDO

- [x] T0.1 Copiar as 8 fontes para `data/input/` (originais intocados)
- [x] T0.2 Ambiente Python 3.13 + venv + dependências fixadas
- [x] T0.3 `scripts/profile_sources.py` — perfil real de abas/colunas/tipos/nulos/grãos
- [x] T0.4 `scripts/deep_checks.py` — verificações cruzadas que decidem modelagem
- [x] T0.5 `docs/source_profile.md` gerado a partir da leitura real
- [x] T0.6 `docs/data_dictionary.md`
- [x] T0.7 `docs/business_rules.md`
- [x] T0.8 `docs/open_questions.md`
- [x] T0.9 `docs/decisions.md` (ADRs)
- [x] T0.10 `docs/data_lineage.md`

## Fase 1 — Banco e ingestão

- [x] T1.1 `docker-compose.yml` com PostgreSQL 16 na porta 5434
- [x] T1.2 Migrations SQL 001 (schemas/controle) e 002 (modelo analítico)
- [ ] T1.3 Runner de migrations com checksum (`src/db/migrate.py`)
- [ ] T1.4 Contratos de dados `config/sources/*.yaml` (8 fontes)
- [ ] T1.5 Leitores de Excel + parser pt-BR + normalizadores (`src/ingestion/`)
- [ ] T1.6 Carga RAW idempotente por hash + cópia Parquet
- [ ] T1.7 Staging: dimensões (`dim_cliente`, `dim_produto`, `dim_vendedor`, `dim_regiao`, `dim_data`, `dim_transportador`)
- [ ] T1.8 Staging: `fact_venda_documento` + `fact_venda_item`
- [ ] T1.9 Staging: `fact_custo_pa` + as-of join dos 6 custos
- [ ] T1.10 Staging: `fact_cte` + `bridge_cte_nfe` + rateio TON_WEIGHT
- [ ] T1.11 Staging: explosão de positivados + flag de implantação do ERP
- [ ] T1.12 Staging: 161, OUTROS, trigo (parser posicional), catálogo de fontes
- [ ] T1.13 Materialized views (`migrations/003`)
- [ ] T1.14 Orquestrador `scripts/run_pipeline.py`

## Fase 2 — Qualidade e reconciliação

- [ ] T2.1 Motor de testes de qualidade (`src/reconciliation/quality.py`)
- [ ] T2.2 Reconciliação contra o 161 (receita, tonelada, PMV, devolução)
- [ ] T2.3 Reconciliação contra OUTROS (frete, comissão, ICMS, ST, acordos)
- [ ] T2.4 Registro de métricas com status (`src/metrics/registry.py`)

## Fase 3 — Aplicação analítica base

- [ ] T3.1 Esqueleto Streamlit + tema + filtros globais + estado
- [ ] T3.2 Página Qualidade e Reconciliação
- [ ] T3.3 Página Visão Geral
- [ ] T3.4 Página Gestão Diária / Mix
- [ ] T3.5 Página Vendas e Devoluções (drill-down até o item)
- [ ] T3.6 Página Regional e Territorial
- [ ] T3.7 Página RCAs / Vendedores
- [ ] T3.8 Página Custos
- [ ] T3.9 Página Logística / CT-e

## Fase 4 — Análises avançadas

- [ ] T4.1 Página Clientes (RFM, matriz crescimento × contribuição)
- [ ] T4.2 Página Positivados / Coortes
- [ ] T4.3 Página Trigo × Custo × PMV (defasagem 0–6 meses)
- [ ] T4.4 Motor de insights quantitativos com evidência

## Fase 5 — Explorador e visões salvas

- [ ] T5.1 Construtor de visões (dimensões × métricas × gráfico)
- [ ] T5.2 Persistência em `app.saved_views`
- [ ] T5.3 Exportação CSV/XLSX/PNG com nome carimbado

## Fase 6 — Hardening

- [ ] T6.1 Suíte de testes (`pytest`)
- [ ] T6.2 Scripts `_start.ps1` / `_start.bat`
- [ ] T6.3 Dockerfile multi-stage
- [ ] T6.4 README, Walkthrough, PRD, CHANGELOG
