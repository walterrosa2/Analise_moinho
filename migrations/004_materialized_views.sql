-- =====================================================================
-- 004 - Materialized views (recortes mensais pre-agregados)
-- =====================================================================
-- Objetivo (especificacao secao 37): nao varrer o fato detalhado a cada
-- renderizacao de tela. Atualizadas ao fim de cada carga.
--
-- Convencao de metricas nas MVs:
--   receita_liquida = SUM(vlrtot)                  (devolucao ja vem negativa)
--   vendas_brutas   = SUM(vlrtot) sem devolucao
--   devolucoes      = SUM(vlrtot) so devolucao     (negativo)
--   ton_liquida     = SUM(tonliq)
--   *_pmv           = receita / tonelada EXCLUINDO operacoes sem receita
--                     (bonificacao/amostra: tonelada sem valor rebaixaria o preco)
-- =====================================================================

-- Operacoes sem receita (RN-04). Materializada para nao repetir a lista.
CREATE OR REPLACE VIEW analytics.v_operacao_sem_receita AS
SELECT UNNEST(ARRAY[3107, 3102]) AS codtipoper;

COMMENT ON VIEW analytics.v_operacao_sem_receita IS
    'SAIDA BONIFICACAO e AMOSTRA/DOACAO: tonelagem com VLRTOT=0. '
    'Espelha config/settings.yaml -> operacoes.sem_receita.';

-- Item enriquecido: base de quase todas as MVs
CREATE OR REPLACE VIEW analytics.v_venda_item AS
SELECT
    i.*,
    d.codtipoper,
    d.descroper,
    d.chavenfe,
    d.numnota,
    d.uforigem,
    d.ufdestino,
    d.cidorigem,
    d.ciddestino,
    d.ordemcarga,
    d.codparctransp,
    d.vlrnota                                   AS documento_vlrnota,
    (d.codtipoper IN (3107, 3102))              AS is_sem_receita,
    p.descrprod,
    p.classificacao,
    p.grupo_produto,
    c.parceiro,
    c.uf                                        AS uf_cliente,
    c.cidade                                    AS cidade_cliente,
    c.ramo_atividade,
    c.perfil_empresa,
    v.apelido                                   AS vendedor,
    v.papel_analitico,
    v.tipo_vend,
    r.nomereg                                   AS regiao_comercial
FROM analytics.fact_venda_item i
LEFT JOIN analytics.fact_venda_documento d ON d.nunota  = i.nunota
LEFT JOIN analytics.dim_produto          p ON p.codprod = i.codprod
LEFT JOIN analytics.dim_cliente          c ON c.codparc = i.codparc
LEFT JOIN analytics.dim_vendedor         v ON v.codvend = i.codvend
LEFT JOIN analytics.dim_regiao           r ON r.codreg  = i.codreg;

COMMENT ON VIEW analytics.v_venda_item IS
    'Item + dimensoes. documento_vlrnota vem junto apenas para drill-down ate a nota: '
    'NUNCA soma-lo neste grao (RN-02).';

-- ---------------------------------------------------------------------
-- mv_sales_month
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_month AS
SELECT
    ano, mes, ano_mes,
    COUNT(*)                                                     AS linhas,
    COUNT(DISTINCT nunota)                                       AS documentos,
    COUNT(DISTINCT codparc)                                      AS clientes,
    SUM(vlrtot)                                                  AS receita_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_devolucao)                  AS vendas_brutas,
    SUM(vlrtot) FILTER (WHERE is_devolucao)                      AS devolucoes,
    SUM(tonliq)                                                  AS ton_liquida,
    SUM(tonliq) FILTER (WHERE NOT is_devolucao)                  AS ton_bruta,
    SUM(tonliq) FILTER (WHERE is_devolucao)                      AS ton_devolvida,
    SUM(vlrdesc)                                                 AS desconto,
    SUM(vlrcom)                                                  AS comissao,
    SUM(vlricms)                                                 AS icms,
    SUM(vlrsubst)                                                AS substituicao,
    SUM(vlrfrete_alocado)                                        AS frete_alocado,
    SUM(vlrtot)     FILTER (WHERE NOT is_sem_receita)            AS receita_para_pmv,
    SUM(tonliq)     FILTER (WHERE NOT is_sem_receita)            AS ton_para_pmv,
    SUM(tonliq * cusmed)                                         AS custo_cusmed,
    SUM(tonliq * cusmedicm)                                      AS custo_cusmedicm,
    SUM(tonliq * cussemicm)                                      AS custo_cussemicm,
    SUM(tonliq * cusrep)                                         AS custo_cusrep,
    SUM(tonliq * cusger)                                         AS custo_cusger,
    SUM(tonliq * cusvariavel)                                    AS custo_cusvariavel
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes;

CREATE UNIQUE INDEX ON analytics.mv_sales_month (ano, mes);

-- ---------------------------------------------------------------------
-- mv_sales_product_month
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_product_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_product_month AS
SELECT
    ano, mes, ano_mes, codprod, descrprod, classificacao, grupo_produto,
    COUNT(DISTINCT codparc)                          AS clientes,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrdesc)                                     AS desconto,
    SUM(tonliq * cusmed)                             AS custo_cusmed,
    SUM(tonliq * cusmedicm)                          AS custo_cusmedicm,
    SUM(tonliq * cussemicm)                          AS custo_cussemicm,
    SUM(tonliq * cusrep)                             AS custo_cusrep,
    SUM(tonliq * cusger)                             AS custo_cusger,
    SUM(tonliq * cusvariavel)                        AS custo_cusvariavel
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codprod, descrprod, classificacao, grupo_produto;

CREATE UNIQUE INDEX ON analytics.mv_sales_product_month (ano, mes, codprod);

-- ---------------------------------------------------------------------
-- mv_sales_region_month  (regiao COMERCIAL e geografia REAL, separadas)
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_region_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_region_month AS
SELECT
    ano, mes, ano_mes,
    codreg, regiao_comercial,
    uf_cliente, cidade_cliente,
    COUNT(DISTINCT codparc)                          AS clientes,
    COUNT(DISTINCT codvend)                          AS vendedores,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrfrete_alocado)                            AS frete_alocado,
    SUM(tonliq * cusger)                             AS custo_cusger
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codreg, regiao_comercial, uf_cliente, cidade_cliente;

CREATE INDEX ON analytics.mv_sales_region_month (ano, mes);
CREATE INDEX ON analytics.mv_sales_region_month (uf_cliente);

-- ---------------------------------------------------------------------
-- mv_sales_seller_month
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_seller_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_seller_month AS
SELECT
    ano, mes, ano_mes,
    codvend, vendedor, papel_analitico, tipo_vend,
    COUNT(DISTINCT codparc)                          AS clientes,
    COUNT(DISTINCT nunota)                           AS documentos,
    COUNT(DISTINCT codprod)                          AS produtos,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(vlrtot) FILTER (WHERE is_devolucao)          AS devolucoes,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrdesc)                                     AS desconto,
    SUM(vlrcom)                                      AS comissao,
    SUM(vlrfrete_alocado)                            AS frete_alocado,
    SUM(tonliq * cusger)                             AS custo_cusger
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codvend, vendedor, papel_analitico, tipo_vend;

CREATE UNIQUE INDEX ON analytics.mv_sales_seller_month (ano, mes, codvend);

-- ---------------------------------------------------------------------
-- mv_sales_customer_month
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_customer_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_customer_month AS
SELECT
    ano, mes, ano_mes,
    codparc, parceiro, uf_cliente, cidade_cliente, ramo_atividade,
    codvend, vendedor, codreg, regiao_comercial,
    COUNT(DISTINCT nunota)                           AS documentos,
    COUNT(DISTINCT codprod)                          AS produtos,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrfrete_alocado)                            AS frete_alocado,
    SUM(tonliq * cusger)                             AS custo_cusger
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codparc, parceiro, uf_cliente, cidade_cliente,
         ramo_atividade, codvend, vendedor, codreg, regiao_comercial;

CREATE INDEX ON analytics.mv_sales_customer_month (ano, mes);
CREATE INDEX ON analytics.mv_sales_customer_month (codparc);

-- ---------------------------------------------------------------------
-- mv_freight_route_month / mv_freight_carrier_month
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_freight_route_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_freight_route_month AS
SELECT
    d.ano, d.mes, d.ano_mes,
    d.uforigem, d.ufdestino, d.cidorigem, d.ciddestino, d.cif_fob,
    COUNT(DISTINCT b.frete_id)                       AS ctes,
    COUNT(DISTINCT d.nunota)                         AS notas,
    SUM(b.vlrfrete_alocado)                          AS frete,
    SUM(ABS(t.ton))                                  AS ton,
    CASE WHEN SUM(ABS(t.ton)) > 0
         THEN SUM(b.vlrfrete_alocado) / SUM(ABS(t.ton)) END AS frete_por_ton
FROM analytics.bridge_cte_nfe b
JOIN analytics.fact_venda_documento d ON d.nunota = b.nunota_venda
LEFT JOIN (
    SELECT nunota, SUM(tonliq) AS ton FROM analytics.fact_venda_item GROUP BY nunota
) t ON t.nunota = d.nunota
WHERE b.match_status <> 'SEM_VINCULO'
GROUP BY d.ano, d.mes, d.ano_mes, d.uforigem, d.ufdestino,
         d.cidorigem, d.ciddestino, d.cif_fob;

CREATE INDEX ON analytics.mv_freight_route_month (ano, mes);

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_freight_carrier_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_freight_carrier_month AS
SELECT
    c.ano, c.mes, c.ano_mes,
    c.codparc                                        AS codparc_transp,
    c.nomeparc                                       AS transportador,
    COUNT(*)                                         AS ctes,
    SUM(c.vlrnota)                                   AS frete_total,
    SUM(c.qtd_nfe_vinculadas)                        AS nfe_vinculadas,
    COUNT(*) FILTER (WHERE c.qtd_nfe_vinculadas = 0) AS ctes_sem_nfe
FROM analytics.fact_cte c
GROUP BY c.ano, c.mes, c.ano_mes, c.codparc, c.nomeparc;

CREATE INDEX ON analytics.mv_freight_carrier_month (ano, mes);

-- ---------------------------------------------------------------------
-- mv_cost_product_month
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_cost_product_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_cost_product_month AS
SELECT
    ano, mes, ano_mes, codprod, produto, grupo_produto,
    COUNT(*)          AS registros,
    AVG(cusmed)       AS cusmed,
    AVG(cusmedicm)    AS cusmedicm,
    AVG(cussemicm)    AS cussemicm,
    AVG(cusrep)       AS cusrep,
    AVG(cusger)       AS cusger,
    AVG(cusvariavel)  AS cusvariavel,
    MIN(dtatual)      AS primeira_data,
    MAX(dtatual)      AS ultima_data
FROM analytics.fact_custo_pa
GROUP BY ano, mes, ano_mes, codprod, produto, grupo_produto;

CREATE UNIQUE INDEX ON analytics.mv_cost_product_month (ano, mes, codprod);

-- ---------------------------------------------------------------------
-- mv_positivados_cohort
-- ---------------------------------------------------------------------
-- "Positivado" = mes da PRIMEIRA compra do cliente (RN-15, verificado:
-- 2.871 vinculos para 2.871 clientes distintos). A MV liga a coorte de
-- entrada ao comportamento posterior de compra.
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_positivados_cohort CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_positivados_cohort AS
WITH entrada AS (
    SELECT codparc, ano_mes AS coorte, ano, mes, periodo_implantacao_erp,
           make_date(ano, mes, 1) AS data_coorte
    FROM analytics.fact_positivado
),
compras AS (
    SELECT codparc, ano_mes, MIN(data_referencia) AS primeira_no_mes,
           SUM(vlrtot) AS receita, SUM(tonliq) AS ton
    FROM analytics.fact_venda_item
    WHERE NOT is_devolucao
    GROUP BY codparc, ano_mes
)
SELECT
    e.coorte,
    e.data_coorte,
    e.periodo_implantacao_erp,
    e.codparc,
    c.ano_mes                                              AS mes_compra,
    (EXTRACT(YEAR  FROM to_date(c.ano_mes, 'YYYY-MM')) * 12
   + EXTRACT(MONTH FROM to_date(c.ano_mes, 'YYYY-MM')))
  - (e.ano * 12 + e.mes)                                   AS meses_desde_entrada,
    c.receita,
    c.ton
FROM entrada e
LEFT JOIN compras c ON c.codparc = e.codparc;

CREATE INDEX ON analytics.mv_positivados_cohort (coorte);
CREATE INDEX ON analytics.mv_positivados_cohort (codparc);

-- ---------------------------------------------------------------------
-- mv_trigo_cost_month  (serie para correlacao exploratoria)
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_trigo_cost_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_trigo_cost_month AS
SELECT
    COALESCE(t.ano_mes, e.ano_mes, s.ano_mes)  AS ano_mes,
    t.preco_medio                              AS trigo_preco_medio,
    t.ton_total                                AS trigo_ton_comprada,
    e.ton_estoque                              AS trigo_ton_estoque,
    e.preco_medio                              AS trigo_estoque_preco_medio,
    s.receita_para_pmv / NULLIF(s.ton_para_pmv, 0) AS pmv,
    s.custo_cusmed      / NULLIF(s.ton_liquida, 0) AS cusmed_por_ton,
    s.custo_cusger      / NULLIF(s.ton_liquida, 0) AS cusger_por_ton,
    s.custo_cusvariavel / NULLIF(s.ton_liquida, 0) AS cusvariavel_por_ton,
    s.ton_liquida,
    s.receita_liquida
FROM analytics.fact_trigo_compra_mensal t
FULL OUTER JOIN analytics.fact_trigo_estoque_mensal e ON e.ano_mes = t.ano_mes
FULL OUTER JOIN analytics.mv_sales_month s            ON s.ano_mes = COALESCE(t.ano_mes, e.ano_mes);

CREATE UNIQUE INDEX ON analytics.mv_trigo_cost_month (ano_mes);

COMMENT ON MATERIALIZED VIEW analytics.mv_trigo_cost_month IS
    'Serie mensal para correlacao EXPLORATORIA trigo x custo x PMV. '
    'Nao ha granularidade de fornecedor, rendimento ou qualidade: '
    'correlacao aqui NUNCA e prova de causalidade.';
