-- =====================================================================
-- 001 - Schemas e tabelas de controle do pipeline
-- =====================================================================
-- raw       : copia fiel do Excel, sem conversao de valor
-- staging   : dados tipados/normalizados, ainda sem modelagem dimensional
-- analytics : modelo dimensional (dim_/fact_/bridge_/mv_)
-- app       : estado da aplicacao (visoes salvas, preferencias)
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS app;

COMMENT ON SCHEMA raw       IS 'Camada bruta: 1 tabela por aba importada. Nunca alterar valores.';
COMMENT ON SCHEMA staging   IS 'Camada intermediaria: tipagem, normalizacao e explosao de listas.';
COMMENT ON SCHEMA analytics IS 'Modelo dimensional consumido pela aplicacao.';
COMMENT ON SCHEMA app       IS 'Estado da aplicacao (visoes salvas, configuracoes de usuario).';

-- ---------------------------------------------------------------------
-- Controle de migrations (executadas pelo runner src/db/migrate.py)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.schema_migrations (
    version      TEXT PRIMARY KEY,
    filename     TEXT        NOT NULL,
    checksum     TEXT        NOT NULL,
    applied_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms  INTEGER
);

COMMENT ON TABLE app.schema_migrations IS 'Migrations SQL ja aplicadas (idempotencia por checksum).';

-- ---------------------------------------------------------------------
-- Lotes de carga (idempotencia por hash de arquivo)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.ingestion_batch (
    batch_id          BIGSERIAL PRIMARY KEY,
    source_id         TEXT        NOT NULL,
    source_file       TEXT        NOT NULL,
    source_sheet      TEXT,
    source_file_hash  TEXT        NOT NULL,
    file_size_bytes   BIGINT,
    file_modified_at  TIMESTAMPTZ,
    rows_read         INTEGER,
    rows_loaded       INTEGER,
    status            TEXT        NOT NULL DEFAULT 'RUNNING',
    error_message     TEXT,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    duration_ms       INTEGER,
    CONSTRAINT ck_batch_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED'))
);

CREATE INDEX IF NOT EXISTS ix_batch_source     ON app.ingestion_batch (source_id, started_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_batch_hash_sheet
    ON app.ingestion_batch (source_id, source_file_hash, COALESCE(source_sheet, ''))
    WHERE status = 'SUCCESS';

COMMENT ON TABLE app.ingestion_batch IS
    'Um registro por (fonte, aba, hash de arquivo). Hash ja carregado com SUCCESS = skip.';

-- ---------------------------------------------------------------------
-- Resultado dos testes de qualidade de dados
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.data_quality_check (
    check_id      BIGSERIAL PRIMARY KEY,
    batch_id      BIGINT REFERENCES app.ingestion_batch (batch_id) ON DELETE CASCADE,
    run_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    check_name    TEXT        NOT NULL,
    category      TEXT        NOT NULL,
    target_object TEXT        NOT NULL,
    severity      TEXT        NOT NULL DEFAULT 'WARNING',
    status        TEXT        NOT NULL,
    observed      NUMERIC,
    expected      NUMERIC,
    tolerance     NUMERIC,
    message       TEXT,
    evidence_sql  TEXT,
    CONSTRAINT ck_dq_status   CHECK (status IN ('PASS', 'WARN', 'FAIL', 'SKIPPED')),
    CONSTRAINT ck_dq_severity CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL'))
);

CREATE INDEX IF NOT EXISTS ix_dq_run ON app.data_quality_check (run_at DESC, status);

COMMENT ON COLUMN app.data_quality_check.evidence_sql IS
    'SQL que reproduz as linhas problematicas ("Ver evidencia" na UI).';

-- ---------------------------------------------------------------------
-- Reconciliacao: modelo calculado vs fonte gerencial
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.reconciliation_result (
    recon_id        BIGSERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    scope           TEXT        NOT NULL,
    period          TEXT,
    dimension       TEXT,
    metric_id       TEXT        NOT NULL,
    value_source    NUMERIC,
    value_model     NUMERIC,
    diff_abs        NUMERIC GENERATED ALWAYS AS (value_model - value_source) STORED,
    diff_pct        NUMERIC,
    tolerance_pct   NUMERIC,
    status          TEXT        NOT NULL,
    explanation     TEXT,
    CONSTRAINT ck_recon_status CHECK (status IN ('OK', 'DIVERGENTE', 'EXPLICADO', 'SEM_FONTE'))
);

CREATE INDEX IF NOT EXISTS ix_recon_run ON app.reconciliation_result (run_at DESC, scope);

COMMENT ON TABLE app.reconciliation_result IS
    'Comparacao entre o modelo analitico e as fontes gerenciais (161, OUTROS, CTE). '
    'Nunca ajustar dados para "bater": divergencia deve ser explicada.';

-- ---------------------------------------------------------------------
-- Visoes salvas do Explorador
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.saved_views (
    view_id     BIGSERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    description TEXT,
    owner       TEXT        NOT NULL DEFAULT 'consultor',
    config      JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_saved_view_name UNIQUE (owner, name)
);

-- ---------------------------------------------------------------------
-- Catalogo de fontes de dados (inventario Sankhya) - SEM credenciais
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.data_source_catalog (
    catalog_id   BIGSERIAL PRIMARY KEY,
    origem       TEXT,
    relatorio    TEXT,
    descricao    TEXT,
    periodicidade TEXT,
    responsavel  TEXT,
    status       TEXT,
    observacoes  TEXT,
    _source_file TEXT,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE app.data_source_catalog IS
    'Backlog/inventario de fontes. Credenciais NUNCA sao importadas (ver src/ingestion/catalog.py).';
