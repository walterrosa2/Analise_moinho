-- =====================================================================
-- 003 - Status SUPERSEDED para recarga forcada
-- =====================================================================
-- Sem este status, uma recarga com --forcar do MESMO arquivo violaria o
-- indice unico (source_id, hash, sheet) WHERE status='SUCCESS'.
-- A carga anterior passa a SUPERSEDED, preservando o historico do batch.
-- =====================================================================

ALTER TABLE app.ingestion_batch DROP CONSTRAINT IF EXISTS ck_batch_status;

ALTER TABLE app.ingestion_batch
    ADD CONSTRAINT ck_batch_status
    CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED', 'SUPERSEDED'));

COMMENT ON COLUMN app.ingestion_batch.status IS
    'RUNNING | SUCCESS | FAILED | SKIPPED (hash ja carregado) | SUPERSEDED (substituido por recarga forcada)';
