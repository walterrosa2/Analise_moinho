-- =====================================================================
-- 002 - Modelo analitico (dimensoes, fatos, pontes)
-- =====================================================================
-- A camada `raw` NAO e criada aqui: suas tabelas sao geradas dinamicamente
-- pelo ingestor a partir das colunas reais de cada aba (todas TEXT),
-- garantindo fidelidade mesmo se o layout do Excel mudar.
-- Ver docs/decisions.md (ADR-002).
-- =====================================================================

-- ---------------------------------------------------------------------
-- DIM_DATA - calendario
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_data (
    data_id       DATE PRIMARY KEY,
    ano           SMALLINT NOT NULL,
    mes           SMALLINT NOT NULL,
    dia           SMALLINT NOT NULL,
    ano_mes       TEXT     NOT NULL,
    trimestre     SMALLINT NOT NULL,
    semestre      SMALLINT NOT NULL,
    dia_semana    SMALLINT NOT NULL,
    nome_mes      TEXT     NOT NULL,
    inicio_mes    DATE     NOT NULL,
    fim_mes       DATE     NOT NULL,
    is_fim_semana BOOLEAN  NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_dim_data_ano_mes ON analytics.dim_data (ano, mes);

-- ---------------------------------------------------------------------
-- DIM_CLIENTE
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_cliente (
    codparc            BIGINT PRIMARY KEY,
    parceiro           TEXT,
    razao_social       TEXT,
    cgccpf_hash        TEXT,          -- hash: documento nunca em claro no DW analitico
    tipo_pessoa        TEXT,          -- PJ | PF | DESCONHECIDO
    cidade             TEXT,
    uf                 TEXT,
    ramo_atividade     TEXT,
    perfil_empresa     TEXT,
    -- Regiao COMERCIAL (atribuicao interna) - nao confundir com geografia real
    codreg             BIGINT,
    nomereg            TEXT,
    -- Datas calculadas na carga
    primeira_compra    DATE,
    ultima_compra      DATE,
    qtd_meses_ativos   INTEGER,
    _ingested_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dim_cliente_uf     ON analytics.dim_cliente (uf);
CREATE INDEX IF NOT EXISTS ix_dim_cliente_cidade ON analytics.dim_cliente (cidade);
CREATE INDEX IF NOT EXISTS ix_dim_cliente_reg    ON analytics.dim_cliente (codreg);

COMMENT ON COLUMN analytics.dim_cliente.cgccpf_hash IS
    'SHA-256 do CNPJ/CPF. O documento em claro nao entra no DW (LGPD).';
COMMENT ON COLUMN analytics.dim_cliente.codreg IS
    'REGIAO COMERCIAL (atribuicao interna). A geografia real do cliente esta em uf/cidade.';

-- ---------------------------------------------------------------------
-- DIM_PRODUTO
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_produto (
    codprod          BIGINT PRIMARY KEY,
    descrprod        TEXT,
    codgrupoprod     BIGINT,
    grupo_produto    TEXT,
    unidade          TEXT,
    -- Classificacao FARINHAS/FARELO/MISTURAS/BOLO (config/product_classification.yaml)
    classificacao    TEXT,
    classificacao_origem TEXT,        -- REGRA_YAML | GRUPO_ERP | NAO_CLASSIFICADO
    classificacao_versao TEXT,
    _ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_dim_produto_class ON analytics.dim_produto (classificacao);
CREATE INDEX IF NOT EXISTS ix_dim_produto_grupo ON analytics.dim_produto (codgrupoprod);

COMMENT ON COLUMN analytics.dim_produto.classificacao_origem IS
    'Rastreabilidade: como o produto recebeu a classificacao. Nunca inferir em silencio.';

-- ---------------------------------------------------------------------
-- DIM_VENDEDOR
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_vendedor (
    codvend           BIGINT PRIMARY KEY,
    apelido           TEXT,
    tipo_vend         TEXT,
    vendedor_ativo    TEXT,
    ativo             BOOLEAN,
    codparc           BIGINT,
    nomeparc          TEXT,
    cidade            TEXT,
    estado            TEXT,
    codregiao         BIGINT,
    regiao            TEXT,
    -- Papel analitico (config/seller_roles.yaml) - NUNCA inferido pelo nome
    papel_analitico   TEXT NOT NULL DEFAULT 'NAO_CLASSIFICADO',
    grupo_analitico   TEXT,
    papel_origem      TEXT NOT NULL DEFAULT 'NAO_CLASSIFICADO',
    -- Atividade observada nos fatos
    primeira_venda    DATE,
    ultima_venda      DATE,
    _ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_papel CHECK (papel_analitico IN
        ('RCA', 'VENDA_DIRETA_LIDERANCA', 'INTERNO', 'SUPERVISOR', 'OUTRO', 'NAO_CLASSIFICADO'))
);

CREATE INDEX IF NOT EXISTS ix_dim_vendedor_papel ON analytics.dim_vendedor (papel_analitico);

COMMENT ON COLUMN analytics.dim_vendedor.papel_analitico IS
    'Vem de config/seller_roles.yaml. Default NAO_CLASSIFICADO ate validacao do negocio.';

-- ---------------------------------------------------------------------
-- DIM_REGIAO (regiao COMERCIAL)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_regiao (
    codreg       BIGINT PRIMARY KEY,
    nomereg      TEXT,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- DIM_TRANSPORTADOR
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_transportador (
    codparc_transp BIGINT PRIMARY KEY,
    nome_transp    TEXT,
    _ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- FACT_VENDA_DOCUMENTO - grao: NUNOTA
-- ---------------------------------------------------------------------
-- Guarda as medidas de DOCUMENTO (VLRNOTA, frete da carga). Somar essas
-- medidas no grao de item e ERRO (regra de seguranca analitica #1 e #2).
CREATE TABLE IF NOT EXISTS analytics.fact_venda_documento (
    nunota                 BIGINT PRIMARY KEY,
    codemp                 INTEGER,
    numnota                BIGINT,
    chavenfe               TEXT,
    dtneg                  DATE,
    dtfatur                DATE,
    dtentsai               DATE,
    data_referencia        DATE,          -- data usada nas analises (configuravel)
    ano                    SMALLINT,
    mes                    SMALLINT,
    ano_mes                TEXT,
    codtipoper             INTEGER,
    descroper              TEXT,
    tipmov                 TEXT,
    is_devolucao           BOOLEAN NOT NULL DEFAULT FALSE,
    cif_fob                TEXT,
    cidorigem              TEXT,
    ciddestino             TEXT,
    uforigem               TEXT,
    ufdestino              TEXT,
    vlrfrete_rateado_nota  NUMERIC(18, 4),
    ordemcarga             BIGINT,
    cif_fob_ordemcarga     TEXT,
    codparctransp          BIGINT,
    vlrfrete_ordemcarga    NUMERIC(18, 4),
    codparc                BIGINT,
    codvend                BIGINT,
    codsupervisor          BIGINT,
    codreg                 BIGINT,
    nomereg                TEXT,
    -- Medida de documento: NUNCA somar no grao de item
    vlrnota                NUMERIC(18, 4),
    acordo                 TEXT,
    observacaonota         TEXT,
    _batch_id              BIGINT,
    _ingested_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_fvd_data     ON analytics.fact_venda_documento (data_referencia);
CREATE INDEX IF NOT EXISTS ix_fvd_ano_mes  ON analytics.fact_venda_documento (ano, mes);
CREATE INDEX IF NOT EXISTS ix_fvd_parc     ON analytics.fact_venda_documento (codparc);
CREATE INDEX IF NOT EXISTS ix_fvd_vend     ON analytics.fact_venda_documento (codvend);
CREATE INDEX IF NOT EXISTS ix_fvd_chavenfe ON analytics.fact_venda_documento (chavenfe);
CREATE INDEX IF NOT EXISTS ix_fvd_ordem    ON analytics.fact_venda_documento (ordemcarga);

COMMENT ON COLUMN analytics.fact_venda_documento.vlrnota IS
    'Valor do DOCUMENTO. Proibido somar no grao de item (repete-se nas linhas).';

-- ---------------------------------------------------------------------
-- FACT_VENDA_ITEM - grao: NUNOTA + SEQUENCIA
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_venda_item (
    item_id           BIGSERIAL PRIMARY KEY,
    nunota            BIGINT   NOT NULL,
    sequencia         INTEGER  NOT NULL,
    codemp            INTEGER,
    data_referencia   DATE,
    ano               SMALLINT,
    mes               SMALLINT,
    ano_mes           TEXT,
    -- Dimensoes desnormalizadas (performance de filtro)
    codprod           BIGINT,
    codparc           BIGINT,
    codvend           BIGINT,
    codsupervisor     BIGINT,
    codreg            BIGINT,
    codlocalorig      INTEGER,
    codtrib           TEXT,
    controle          TEXT,
    codcfo            BIGINT,
    tipmov            TEXT,
    is_devolucao      BOOLEAN  NOT NULL DEFAULT FALSE,
    cif_fob           TEXT,
    -- Quantidades (devolucao vem negativa na origem: sinal preservado)
    codvol            TEXT,
    qtd               NUMERIC(18, 4),
    pesoliq           NUMERIC(18, 4),
    tonliq            NUMERIC(18, 6),
    pesobruto         NUMERIC(18, 4),
    tonbruto          NUMERIC(18, 6),
    -- Valores do ITEM (estes sim podem ser somados)
    vlrunit           NUMERIC(18, 6),
    vlrtot            NUMERIC(18, 4),
    vlrdesc           NUMERIC(18, 4),
    vlrrepred         NUMERIC(18, 4),
    -- Comissao e tributos
    perccom           NUMERIC(12, 6),
    vlrcom            NUMERIC(18, 4),
    vlricms           NUMERIC(18, 4),
    vlrsubst          NUMERIC(18, 4),
    -- Frete rateado do CT-e (calculado; ver bridge_cte_nfe)
    vlrfrete_alocado  NUMERIC(18, 4),
    frete_alocado_metodo TEXT,
    -- Custo as-of (join temporal; ver src/staging/costs.py)
    cusmed            NUMERIC(18, 6),
    cusmedicm         NUMERIC(18, 6),
    cussemicm         NUMERIC(18, 6),
    cusrep            NUMERIC(18, 6),
    cusger            NUMERIC(18, 6),
    cusvariavel       NUMERIC(18, 6),
    cost_match_date   DATE,
    cost_age_days     INTEGER,
    cost_match_status TEXT,
    _batch_id         BIGINT,
    _ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_fvi_grao UNIQUE (nunota, sequencia),
    CONSTRAINT ck_cost_match CHECK (cost_match_status IN
        ('EXATO', 'ANTERIOR', 'SEM_CUSTO', 'PRODUTO_SEM_CADASTRO', 'SEM_DATA') OR cost_match_status IS NULL)
);

CREATE INDEX IF NOT EXISTS ix_fvi_data    ON analytics.fact_venda_item (data_referencia);
CREATE INDEX IF NOT EXISTS ix_fvi_ano_mes ON analytics.fact_venda_item (ano, mes);
CREATE INDEX IF NOT EXISTS ix_fvi_prod    ON analytics.fact_venda_item (codprod);
CREATE INDEX IF NOT EXISTS ix_fvi_parc    ON analytics.fact_venda_item (codparc);
CREATE INDEX IF NOT EXISTS ix_fvi_vend    ON analytics.fact_venda_item (codvend);
CREATE INDEX IF NOT EXISTS ix_fvi_reg     ON analytics.fact_venda_item (codreg);
CREATE INDEX IF NOT EXISTS ix_fvi_nunota  ON analytics.fact_venda_item (nunota);
CREATE INDEX IF NOT EXISTS ix_fvi_dev     ON analytics.fact_venda_item (is_devolucao);

COMMENT ON TABLE analytics.fact_venda_item IS
    'Grao NUNOTA+SEQUENCIA. Devolucoes preservam o sinal negativo da origem.';
COMMENT ON COLUMN analytics.fact_venda_item.cost_match_status IS
    'EXATO=custo na mesma data; ANTERIOR=custo vigente mais recente <= data; SEM_CUSTO=nao encontrado.';

-- ---------------------------------------------------------------------
-- FACT_CUSTO_PA - grao: produto x empresa x local x data
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_custo_pa (
    custo_id       BIGSERIAL PRIMARY KEY,
    codprod        BIGINT   NOT NULL,
    codemp         INTEGER,
    codlocal       INTEGER,
    dtatual        DATE     NOT NULL,
    ano            SMALLINT,
    mes            SMALLINT,
    ano_mes        TEXT,
    produto        TEXT,
    codgrupoprod   BIGINT,
    grupo_produto  TEXT,
    unidade        TEXT,
    cusmed         NUMERIC(18, 6),
    cusmedicm      NUMERIC(18, 6),
    cussemicm      NUMERIC(18, 6),
    cusrep         NUMERIC(18, 6),
    cusger         NUMERIC(18, 6),
    cusvariavel    NUMERIC(18, 6),
    _batch_id      BIGINT,
    _ingested_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_custo_asof ON analytics.fact_custo_pa (codprod, codemp, codlocal, dtatual DESC);
CREATE INDEX IF NOT EXISTS ix_custo_prod_dt ON analytics.fact_custo_pa (codprod, dtatual DESC);

COMMENT ON TABLE analytics.fact_custo_pa IS
    'Seis conceitos de custo coexistem. NENHUM e "o custo oficial" ate homologacao da Controladoria.';

-- ---------------------------------------------------------------------
-- FACT_CTE + BRIDGE_CTE_NFE
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_cte (
    frete_id      BIGSERIAL PRIMARY KEY,     -- surrogate: CHAVECTE nao e PK garantida
    codemp        INTEGER,
    nunota        BIGINT,
    numnota       BIGINT,
    serienota     TEXT,
    chavecte      TEXT,
    dtneg         DATE,
    dtentsai      DATE,
    dtfatur       DATE,
    data_referencia DATE,
    ano           SMALLINT,
    mes           SMALLINT,
    ano_mes       TEXT,
    codtipoper    INTEGER,
    descroper     TEXT,
    ordemcarga    BIGINT,
    codparc       BIGINT,                    -- transportador emissor do CT-e
    nomeparc      TEXT,
    vlrnota       NUMERIC(18, 4),            -- valor do frete (CT-e)
    qtd_nfe_vinculadas INTEGER NOT NULL DEFAULT 0,
    _batch_id     BIGINT,
    _ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_cte_chave ON analytics.fact_cte (chavecte);
CREATE INDEX IF NOT EXISTS ix_cte_data  ON analytics.fact_cte (data_referencia);
CREATE INDEX IF NOT EXISTS ix_cte_parc  ON analytics.fact_cte (codparc);
CREATE INDEX IF NOT EXISTS ix_cte_ordem ON analytics.fact_cte (ordemcarga);

CREATE TABLE IF NOT EXISTS analytics.bridge_cte_nfe (
    bridge_id         BIGSERIAL PRIMARY KEY,
    frete_id          BIGINT NOT NULL REFERENCES analytics.fact_cte (frete_id) ON DELETE CASCADE,
    chavecte          TEXT,
    chave_nfe         TEXT,
    numero_nota_venda TEXT,
    nunota_venda      BIGINT,             -- resolvido contra fact_venda_documento
    match_status      TEXT NOT NULL,      -- NFE_OK | NOTA_OK | ORDEMCARGA_OK | SEM_VINCULO
    ton_nfe           NUMERIC(18, 6),
    allocation_weight NUMERIC(18, 10),
    allocation_method TEXT NOT NULL DEFAULT 'TON_WEIGHT',
    vlrfrete_alocado  NUMERIC(18, 4),
    _ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_bridge_match CHECK (match_status IN
        ('NFE_OK', 'NOTA_OK', 'ORDEMCARGA_OK', 'SEM_VINCULO'))
);

CREATE INDEX IF NOT EXISTS ix_bridge_frete  ON analytics.bridge_cte_nfe (frete_id);
CREATE INDEX IF NOT EXISTS ix_bridge_nfe    ON analytics.bridge_cte_nfe (chave_nfe);
CREATE INDEX IF NOT EXISTS ix_bridge_nunota ON analytics.bridge_cte_nfe (nunota_venda);
CREATE INDEX IF NOT EXISTS ix_bridge_status ON analytics.bridge_cte_nfe (match_status);

COMMENT ON TABLE analytics.bridge_cte_nfe IS
    'Um CT-e atende N notas. Frete rateado por tonelagem (TON_WEIGHT). '
    'O rateio NUNCA e escondido: % nao alocado aparece na UI.';

-- ---------------------------------------------------------------------
-- FACT_POSITIVADO - grao: ANO + MES + CODPARC
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_positivado (
    positivado_id            BIGSERIAL PRIMARY KEY,
    ano                      SMALLINT NOT NULL,
    mes                      SMALLINT NOT NULL,
    ano_mes                  TEXT     NOT NULL,
    codparc                  BIGINT   NOT NULL,
    cliente_existe_dim       BOOLEAN  NOT NULL DEFAULT FALSE,
    periodo_implantacao_erp  BOOLEAN  NOT NULL DEFAULT FALSE,
    _batch_id                BIGINT,
    _ingested_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_positivado UNIQUE (ano, mes, codparc)
);

CREATE INDEX IF NOT EXISTS ix_positivado_parc ON analytics.fact_positivado (codparc);
CREATE INDEX IF NOT EXISTS ix_positivado_mes  ON analytics.fact_positivado (ano, mes);

CREATE TABLE IF NOT EXISTS analytics.fact_positivado_mes (
    ano                      SMALLINT NOT NULL,
    mes                      SMALLINT NOT NULL,
    ano_mes                  TEXT     NOT NULL,
    qtd_positivados_fonte    INTEGER,
    qtd_positivados_explodido INTEGER,
    vlrtot_positivados       NUMERIC(18, 4),
    vlrtot_geral             NUMERIC(18, 4),
    perc_positivados_geral   NUMERIC(12, 6),
    periodo_implantacao_erp  BOOLEAN NOT NULL DEFAULT FALSE,
    _batch_id                BIGINT,
    PRIMARY KEY (ano, mes)
);

COMMENT ON COLUMN analytics.fact_positivado.periodo_implantacao_erp IS
    'TRUE para os primeiros meses do Sankhya (dados fora do padrao). Dados NUNCA sao excluidos.';

-- ---------------------------------------------------------------------
-- FACT_GESTAO_DIARIA (161) - grao: ANO + MES + TIPO + COD_CLA
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_gestao_diaria (
    gestao_id       BIGSERIAL PRIMARY KEY,
    ano             SMALLINT NOT NULL,
    mes             SMALLINT NOT NULL,
    ano_mes         TEXT     NOT NULL,
    tipo            TEXT     NOT NULL,
    cod_cla         TEXT,
    desc_cla        TEXT,
    valor           NUMERIC(18, 4),
    perc_ating_vlr  NUMERIC(18, 6),
    tonelada        NUMERIC(18, 6),
    perc_ating_ton  NUMERIC(18, 6),
    markup          NUMERIC(18, 6),
    pc_medio        NUMERIC(18, 6),
    _batch_id       BIGINT,
    _ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_gestao_grao UNIQUE (ano, mes, tipo, cod_cla)
);

CREATE INDEX IF NOT EXISTS ix_gestao_mes ON analytics.fact_gestao_diaria (ano, mes, tipo);

-- ---------------------------------------------------------------------
-- FACT_DESPESA_MENSAL (161 OUTROS) - grao: ANO + MES + DESCRICAO
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_despesa_mensal (
    despesa_id   BIGSERIAL PRIMARY KEY,
    ano          SMALLINT NOT NULL,
    mes          SMALLINT NOT NULL,
    ano_mes      TEXT     NOT NULL,
    descricao    TEXT     NOT NULL,
    orc_ant      NUMERIC(18, 4),   -- semantica pendente de validacao do negocio
    atual        NUMERIC(18, 4),
    perc_var     NUMERIC(18, 6),
    _batch_id    BIGINT,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ux_despesa_grao UNIQUE (ano, mes, descricao)
);

COMMENT ON COLUMN analytics.fact_despesa_mensal.orc_ant IS
    'pending_business_validation: nao assumir se e Orcado ou Ano Anterior.';

-- ---------------------------------------------------------------------
-- FACT_TRIGO - compra e estoque mensais
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_trigo_compra_mensal (
    ano            SMALLINT NOT NULL,
    mes            SMALLINT NOT NULL,
    ano_mes        TEXT     NOT NULL,
    ton_trigo      NUMERIC(18, 6),
    ton_triticale  NUMERIC(18, 6),
    ton_total      NUMERIC(18, 6),
    vlr_trigo      NUMERIC(18, 4),
    vlr_triticale  NUMERIC(18, 4),
    vlr_total      NUMERIC(18, 4),
    preco_medio    NUMERIC(18, 6),
    _batch_id      BIGINT,
    PRIMARY KEY (ano, mes)
);

CREATE TABLE IF NOT EXISTS analytics.fact_trigo_estoque_mensal (
    ano          SMALLINT NOT NULL,
    mes          SMALLINT NOT NULL,
    ano_mes      TEXT     NOT NULL,
    ton_estoque  NUMERIC(18, 6),
    preco_medio  NUMERIC(18, 6),
    _batch_id    BIGINT,
    PRIMARY KEY (ano, mes)
);
