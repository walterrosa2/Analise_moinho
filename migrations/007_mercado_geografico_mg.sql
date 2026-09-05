-- =====================================================================
-- 007 - Camada geografica de mercado: Minas Gerais
-- =====================================================================
-- Objetivo: responder "onde o Moinho DEVERIA vender", e nao apenas
-- "onde o Moinho vende". Tres camadas que se sobrepoem por municipio:
--
--   1. VENDA      o que o Moinho fatura hoje, por cidade de MG
--   2. TERRITORIO qual RCA / regiao comercial responde por aquela cidade
--   3. MERCADO    quantos estabelecimentos consumidores de farinha existem
--                 ali (CEMPRE/IBGE) e quanto isso vale em toneladas
--
-- Chave de integracao: CODIGO IBGE DO MUNICIPIO (7 digitos). O cadastro do
-- Sankhya traz cidade como texto livre ("5357-UBERLANDIA") e o arquivo de
-- territorio traz outra grafia ("Uberlandia, Minas Gerais"). O pareamento
-- e explicito, auditavel e fica registrado em analytics.map_cidade_ibge -
-- nenhuma juncao por texto acontece dentro das consultas da aplicacao.
--
-- Regra estrutural preservada de 002: REGIAO COMERCIAL (atribuicao interna,
-- CODREG) e GEOGRAFIA REAL (municipio IBGE) continuam sendo dimensoes
-- distintas. Esta migration acrescenta a terceira: TERRITORIO DECLARADO do
-- RCA, que e o que o arquivo de regiao comercial descreve.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Municipios de Minas Gerais (universo fechado: 853)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_municipio_mg (
    cod_ibge              BIGINT PRIMARY KEY,
    municipio             TEXT   NOT NULL,
    municipio_norm        TEXT   NOT NULL,   -- maiusculo, sem acento, sem sufixo de UF
    uf                    TEXT   NOT NULL DEFAULT 'MG',
    microrregiao          TEXT,
    mesorregiao           TEXT,
    regiao_imediata       TEXT,
    regiao_intermediaria  TEXT,
    populacao             INTEGER,
    _ingested_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_municipio_mg_norm  ON analytics.dim_municipio_mg (municipio_norm);
CREATE INDEX IF NOT EXISTS ix_municipio_mg_inter ON analytics.dim_municipio_mg (regiao_intermediaria);

COMMENT ON TABLE analytics.dim_municipio_mg IS
    'Os 853 municipios de MG (IBGE Localidades) com populacao do Censo 2022. '
    'Universo fechado: e o denominador de toda medida de cobertura.';
COMMENT ON COLUMN analytics.dim_municipio_mg.regiao_intermediaria IS
    'Divisao regional oficial do IBGE (2017). Substitui mesorregiao nas leituras '
    'territoriais recentes e e a usada como agrupamento padrao das telas.';

-- ---------------------------------------------------------------------
-- 2. De-para: cidade como o Moinho escreve  ->  codigo IBGE
-- ---------------------------------------------------------------------
-- Existe para que o pareamento seja um DADO inspecionavel, e nao um
-- LIKE escondido dentro de uma consulta. O que nao parear fica com
-- cod_ibge NULL e aparece na pagina de qualidade.
CREATE TABLE IF NOT EXISTS analytics.map_cidade_ibge (
    origem          TEXT   NOT NULL,     -- CLIENTE | TERRITORIO_REGIAO | TERRITORIO_REPRESENTANTE
    cidade_texto    TEXT   NOT NULL,     -- exatamente como consta na fonte
    cidade_norm     TEXT   NOT NULL,
    cod_ibge        BIGINT REFERENCES analytics.dim_municipio_mg (cod_ibge),
    -- EXATO | SEM_CONECTIVOS | APROXIMADO | AMBIGUO | NAO_ENCONTRADO
    metodo          TEXT   NOT NULL,
    similaridade    NUMERIC(5, 4),
    _ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (origem, cidade_texto)
);

CREATE INDEX IF NOT EXISTS ix_map_cidade_ibge ON analytics.map_cidade_ibge (cod_ibge);

COMMENT ON TABLE analytics.map_cidade_ibge IS
    'Pareamento auditavel entre a grafia de cidade de cada fonte e o codigo IBGE. '
    'EXATO e SEM_CONECTIVOS sao seguros; APROXIMADO exige revisao humana; AMBIGUO e '
    'NAO_ENCONTRADO ficam sem municipio de proposito - uma lacuna visivel vale mais '
    'que um municipio errado no mapa. O arquivo de territorio contem cidades de GO, '
    'SP, MT e DF: elas caem aqui como NAO_ENCONTRADO, o que e o comportamento correto '
    'para uma analise restrita a MG.';

-- ---------------------------------------------------------------------
-- 3. Mercado: estabelecimentos por municipio e segmento (CEMPRE/IBGE)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.fact_mercado_cnae (
    cod_ibge          BIGINT NOT NULL REFERENCES analytics.dim_municipio_mg (cod_ibge),
    segmento          TEXT   NOT NULL,
    cnae              TEXT   NOT NULL,
    unidades_locais   INTEGER,
    pessoal_ocupado   INTEGER,          -- NULL = sigilo estatistico do IBGE
    pessoal_estimado  NUMERIC(12, 2),   -- preenchido no staging quando ha sigilo
    porte_medio       NUMERIC(10, 3),   -- pessoal / unidade
    periodo_ref       TEXT,
    _ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cod_ibge, segmento)
);

CREATE INDEX IF NOT EXISTS ix_mercado_cnae_seg ON analytics.fact_mercado_cnae (segmento);

COMMENT ON TABLE analytics.fact_mercado_cnae IS
    'CEMPRE (IBGE): unidades locais e pessoal ocupado por municipio e classe CNAE 2.0. '
    'Universo de empresas formais atuantes - NAO e o mesmo universo da base aberta do '
    'CNPJ nem o da ABIP, que incluem MEI e outras definicoes. Comparar totais entre '
    'fontes diferentes produz numeros incompativeis; aqui a fonte e unica e declarada.';
COMMENT ON COLUMN analytics.fact_mercado_cnae.pessoal_ocupado IS
    'NULL significa SIGILO ESTATISTICO (o IBGE publica X quando poucos informantes '
    'permitiriam identificacao), nao ausencia de empresas. Ver pessoal_estimado.';

-- ---------------------------------------------------------------------
-- 4. Territorio declarado dos RCAs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.dim_territorio_rca (
    cod_ibge          BIGINT NOT NULL REFERENCES analytics.dim_municipio_mg (cod_ibge),
    fonte             TEXT   NOT NULL,   -- REGIAO_COMERCIAL | REGIAO_REPRESENTANTE
    regiao_comercial  TEXT,
    representante     TEXT,
    codvend           BIGINT,            -- so quando a fonte traz o codigo
    _ingested_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cod_ibge, fonte, representante)
);

CREATE INDEX IF NOT EXISTS ix_territorio_rca_rep ON analytics.dim_territorio_rca (representante);
CREATE INDEX IF NOT EXISTS ix_territorio_rca_reg ON analytics.dim_territorio_rca (regiao_comercial);

COMMENT ON TABLE analytics.dim_territorio_rca IS
    'Territorio DECLARADO no arquivo "REGIAO COMERCIAL POR REPRESENTANTE". E uma '
    'intencao de cobertura, nao um fato de venda: uma cidade pode constar aqui e nao '
    'ter faturamento, e pode haver faturamento em cidade que nao consta. As duas '
    'abas do arquivo divergem entre si - por isso a coluna fonte, que preserva ambas '
    'em vez de escolher uma silenciosamente.';

-- ---------------------------------------------------------------------
-- 5. Potencial calculado por municipio e segmento
-- ---------------------------------------------------------------------
-- Preenchida por src/staging/geografia.py, que le config/mercado_mg.yaml.
-- O calculo mora em Python porque cada fator e um PARAMETRO DE NEGOCIO
-- versionado (intensidade, probabilidade de captura, ajuste de porte) e
-- precisa ser trocavel sem migration.
CREATE TABLE IF NOT EXISTS analytics.fact_potencial_municipio (
    cod_ibge                  BIGINT NOT NULL REFERENCES analytics.dim_municipio_mg (cod_ibge),
    segmento                  TEXT   NOT NULL,
    unidades_locais           INTEGER,
    consumo_medio_t_mes       NUMERIC(12, 4),  -- por estabelecimento
    origem_consumo            TEXT,            -- OBSERVADO | FALLBACK
    clientes_amostra          INTEGER,         -- n de clientes reais que calibraram
    fator_porte               NUMERIC(8, 4),
    prob_captura              NUMERIC(6, 4),
    potencial_t_mes           NUMERIC(14, 4),  -- consumo total do segmento na cidade
    potencial_capturavel_t_mes NUMERIC(14, 4), -- fracao realista para o Moinho
    _ingested_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cod_ibge, segmento)
);

COMMENT ON TABLE analytics.fact_potencial_municipio IS
    'Potencial ESTIMADO, nao medido. potencial_t_mes = unidades x consumo mediano '
    'observado nos clientes reais do Moinho do mesmo segmento x fator de porte. '
    'potencial_capturavel aplica a probabilidade de captura de config/mercado_mg.yaml. '
    'Numero de planejamento para priorizar territorio - nunca meta de venda.';

-- ---------------------------------------------------------------------
-- 6. MV: vendas do Moinho por municipio de MG e mes
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_vendas_municipio_mg CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_vendas_municipio_mg AS
SELECT
    m.cod_ibge,
    i.ano_mes,
    i.classificacao,
    SUM(i.vlrtot)                                             AS receita_liquida,
    SUM(i.vlrtot) FILTER (WHERE NOT i.is_devolucao)           AS vendas_brutas,
    SUM(i.vlrtot) FILTER (WHERE i.is_devolucao)               AS devolucoes,
    SUM(i.tonliq)                                             AS ton_liquida,
    SUM(i.vlrtot) FILTER (WHERE NOT i.is_sem_receita)         AS receita_para_pmv,
    SUM(i.tonliq) FILTER (WHERE NOT i.is_sem_receita)         AS ton_para_pmv,
    SUM(i.vlrfrete_alocado)                                   AS frete,
    COUNT(DISTINCT i.codparc)                                 AS clientes,
    COUNT(DISTINCT i.codvend)                                 AS vendedores,
    COUNT(DISTINCT i.nunota)                                  AS documentos
FROM analytics.v_venda_item i
JOIN analytics.map_cidade_ibge m
  ON m.origem = 'CLIENTE' AND m.cidade_texto = i.cidade_cliente
WHERE i.uf_cliente = 'MG' AND m.cod_ibge IS NOT NULL
GROUP BY m.cod_ibge, i.ano_mes, i.classificacao;

CREATE INDEX IF NOT EXISTS ix_mv_vendas_mun_mg ON analytics.mv_vendas_municipio_mg (cod_ibge, ano_mes);

COMMENT ON MATERIALIZED VIEW analytics.mv_vendas_municipio_mg IS
    'Venda do Moinho por municipio de MG, mes e classificacao de produto. '
    'Devolucao mantem o sinal de origem (RN-03). PMV usa receita/ton excluindo '
    'operacao sem receita (RN-04) - por isso as duas colunas *_para_pmv separadas.';

-- ---------------------------------------------------------------------
-- 7. MV: a sobreposicao das tres camadas
-- ---------------------------------------------------------------------
-- Uma linha por municipio de MG. Traz numeros objetivos; a classificacao
-- de White Space (que depende de percentis configuraveis) e aplicada em
-- src/repositories/geo.py, onde o usuario pode mover o corte na tela.
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_mercado_municipio_mg CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_mercado_municipio_mg AS
WITH vendas AS (
    SELECT
        cod_ibge,
        SUM(receita_liquida)                                        AS receita_total,
        SUM(ton_liquida)                                            AS ton_total,
        SUM(frete)                                                  AS frete_total,
        MAX(ano_mes)                                                AS ultimo_mes,
        MIN(ano_mes)                                                AS primeiro_mes
    FROM analytics.mv_vendas_municipio_mg
    GROUP BY cod_ibge
),
janela AS (
    -- Ultimos 12 meses da serie (a janela de negocio fica no YAML; aqui
    -- fixamos 12 para a MV e o repositorio recorta o que precisar)
    SELECT
        v.cod_ibge,
        SUM(v.receita_liquida)                                      AS receita_12m,
        SUM(v.ton_liquida)                                          AS ton_12m,
        SUM(v.receita_liquida) FILTER (WHERE v.classificacao IN ('FARINHAS','MISTURAS','BOLO'))
                                                                    AS receita_farinha_12m,
        SUM(v.ton_liquida)     FILTER (WHERE v.classificacao IN ('FARINHAS','MISTURAS','BOLO'))
                                                                    AS ton_farinha_12m,
        SUM(v.ton_liquida)     FILTER (WHERE v.classificacao = 'FARELO')
                                                                    AS ton_farelo_12m,
        SUM(v.frete)                                                AS frete_12m,
        MAX(v.clientes)                                             AS clientes_pico_mes
    FROM analytics.mv_vendas_municipio_mg v
    CROSS JOIN (SELECT MAX(ano_mes) AS fim FROM analytics.mv_vendas_municipio_mg) lim
    WHERE v.ano_mes > to_char(to_date(lim.fim, 'YYYY-MM') - INTERVAL '12 months', 'YYYY-MM')
    GROUP BY v.cod_ibge
),
clientes AS (
    SELECT
        m.cod_ibge,
        COUNT(DISTINCT c.codparc)                                   AS clientes_cadastrados,
        COUNT(DISTINCT c.codparc) FILTER (
            WHERE c.ultima_compra >= (SELECT MAX(ultima_compra) FROM analytics.dim_cliente)
                                     - INTERVAL '12 months')        AS clientes_ativos
    FROM analytics.dim_cliente c
    JOIN analytics.map_cidade_ibge m
      ON m.origem = 'CLIENTE' AND m.cidade_texto = c.cidade
    WHERE c.uf = 'MG' AND m.cod_ibge IS NOT NULL
    GROUP BY m.cod_ibge
),
mercado AS (
    SELECT
        cod_ibge,
        SUM(unidades_locais)                                        AS estabelecimentos,
        SUM(unidades_locais) FILTER (
            WHERE segmento IN ('panificacao','biscoitos','massas','pratos_prontos'))
                                                                    AS estab_industria_alimentos,
        SUM(unidades_locais) FILTER (WHERE segmento = 'panificacao') AS estab_panificacao,
        SUM(unidades_locais) FILTER (WHERE segmento = 'food_service') AS estab_food_service,
        SUM(unidades_locais) FILTER (
            WHERE segmento IN ('atacado_farinhas','atacado_alimentos'))
                                                                    AS estab_distribuidores,
        SUM(COALESCE(pessoal_estimado, pessoal_ocupado))            AS pessoal_ocupado_total
    FROM analytics.fact_mercado_cnae
    GROUP BY cod_ibge
),
potencial AS (
    SELECT
        cod_ibge,
        SUM(potencial_t_mes)                                        AS potencial_t_mes,
        SUM(potencial_capturavel_t_mes)                             AS potencial_capturavel_t_mes,
        SUM(potencial_capturavel_t_mes) FILTER (
            WHERE segmento IN ('panificacao','biscoitos','massas','pratos_prontos'))
                                                                    AS potencial_industria_t_mes,
        SUM(potencial_capturavel_t_mes) FILTER (
            WHERE segmento IN ('atacado_farinhas','atacado_alimentos'))
                                                                    AS potencial_distribuidor_t_mes
    FROM analytics.fact_potencial_municipio
    GROUP BY cod_ibge
),
territorio AS (
    SELECT
        cod_ibge,
        STRING_AGG(DISTINCT representante, ' | ' ORDER BY representante)    AS representantes,
        STRING_AGG(DISTINCT regiao_comercial, ' | ' ORDER BY regiao_comercial) AS regioes_comerciais,
        COUNT(DISTINCT representante)                               AS qtd_representantes,
        BOOL_OR(fonte = 'REGIAO_COMERCIAL')                         AS na_aba_regiao,
        BOOL_OR(fonte = 'REGIAO_REPRESENTANTE')                     AS na_aba_representante
    FROM analytics.dim_territorio_rca
    GROUP BY cod_ibge
)
SELECT
    d.cod_ibge,
    d.municipio,
    d.regiao_intermediaria,
    d.regiao_imediata,
    d.mesorregiao,
    d.populacao,

    -- Camada 1 - venda do Moinho
    COALESCE(v.receita_total, 0)                                    AS receita_total,
    COALESCE(v.ton_total, 0)                                        AS ton_total,
    COALESCE(j.receita_12m, 0)                                      AS receita_12m,
    COALESCE(j.ton_12m, 0)                                          AS ton_12m,
    COALESCE(j.ton_farinha_12m, 0)                                  AS ton_farinha_12m,
    COALESCE(j.ton_farelo_12m, 0)                                   AS ton_farelo_12m,
    COALESCE(j.receita_farinha_12m, 0)                              AS receita_farinha_12m,
    CASE WHEN COALESCE(j.ton_12m, 0) > 0
         THEN j.frete_12m / NULLIF(ABS(j.ton_12m), 0) END           AS frete_por_ton,
    v.ultimo_mes,
    v.primeiro_mes,
    COALESCE(c.clientes_cadastrados, 0)                             AS clientes_cadastrados,
    COALESCE(c.clientes_ativos, 0)                                  AS clientes_ativos,

    -- Camada 2 - territorio declarado
    t.representantes,
    t.regioes_comerciais,
    COALESCE(t.qtd_representantes, 0)                               AS qtd_representantes,
    COALESCE(t.na_aba_regiao, FALSE)                                AS na_aba_regiao,
    COALESCE(t.na_aba_representante, FALSE)                         AS na_aba_representante,

    -- Camada 3 - mercado e potencial
    COALESCE(mk.estabelecimentos, 0)                                AS estabelecimentos,
    COALESCE(mk.estab_panificacao, 0)                               AS estab_panificacao,
    COALESCE(mk.estab_industria_alimentos, 0)                       AS estab_industria_alimentos,
    COALESCE(mk.estab_food_service, 0)                              AS estab_food_service,
    COALESCE(mk.estab_distribuidores, 0)                            AS estab_distribuidores,
    COALESCE(mk.pessoal_ocupado_total, 0)                           AS pessoal_ocupado_total,
    COALESCE(p.potencial_t_mes, 0)                                  AS potencial_t_mes,
    COALESCE(p.potencial_capturavel_t_mes, 0)                       AS potencial_capturavel_t_mes,
    COALESCE(p.potencial_industria_t_mes, 0)                        AS potencial_industria_t_mes,
    COALESCE(p.potencial_distribuidor_t_mes, 0)                     AS potencial_distribuidor_t_mes,

    -- Sobreposicao
    CASE WHEN COALESCE(mk.estabelecimentos, 0) > 0
         THEN 100.0 * COALESCE(c.clientes_ativos, 0) / mk.estabelecimentos END
                                                                    AS penetracao_pct,
    CASE WHEN COALESCE(p.potencial_capturavel_t_mes, 0) > 0
         THEN 100.0 * (COALESCE(j.ton_farinha_12m, 0) / 12.0) / p.potencial_capturavel_t_mes END
                                                                    AS captura_pct,
    GREATEST(COALESCE(p.potencial_capturavel_t_mes, 0)
             - COALESCE(j.ton_farinha_12m, 0) / 12.0, 0)            AS espaco_t_mes,
    (COALESCE(j.ton_12m, 0) <> 0)                                   AS tem_venda,
    (COALESCE(t.qtd_representantes, 0) > 0)                         AS tem_territorio
FROM analytics.dim_municipio_mg d
LEFT JOIN vendas     v  ON v.cod_ibge  = d.cod_ibge
LEFT JOIN janela     j  ON j.cod_ibge  = d.cod_ibge
LEFT JOIN clientes   c  ON c.cod_ibge  = d.cod_ibge
LEFT JOIN mercado    mk ON mk.cod_ibge = d.cod_ibge
LEFT JOIN potencial  p  ON p.cod_ibge  = d.cod_ibge
LEFT JOIN territorio t  ON t.cod_ibge  = d.cod_ibge;

CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_mercado_mun_mg ON analytics.mv_mercado_municipio_mg (cod_ibge);
CREATE INDEX IF NOT EXISTS ix_mv_mercado_mun_inter
    ON analytics.mv_mercado_municipio_mg (regiao_intermediaria);

COMMENT ON MATERIALIZED VIEW analytics.mv_mercado_municipio_mg IS
    'Uma linha por municipio de MG com as tres camadas sobrepostas: venda, '
    'territorio declarado e mercado potencial. Municipio sem venda aparece com '
    'zero - e justamente essa linha que revela o White Space. A classificacao em '
    'quadrantes usa percentis configuraveis e e aplicada em src/repositories/geo.py.';
COMMENT ON COLUMN analytics.mv_mercado_municipio_mg.captura_pct IS
    'Toneladas/mes de farinha do Moinho sobre o potencial capturavel estimado. '
    'Acima de 100% significa que o modelo subestimou a cidade (tipicamente uma '
    'conta industrial ou um distribuidor que atende alem do proprio municipio).';
COMMENT ON COLUMN analytics.mv_mercado_municipio_mg.penetracao_pct IS
    'Clientes ativos do Moinho sobre estabelecimentos potenciais (CEMPRE). '
    'Denominador inclui multiplicadores (atacado/varejo), entao o indicador mede '
    'presenca relativa entre cidades - nao share de mercado.';
