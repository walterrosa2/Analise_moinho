-- =====================================================================
-- 005 - Correcao da unidade do custo nas materialized views
-- =====================================================================
-- ACHADO (Fase 3, confrontando custo com preco unitario por unidade de venda):
--
--   O custo de fact_custo_pa esta na MESMA unidade de VLRUNIT (a unidade de
--   venda: FD, SC, CX, KG, PT) — NAO por tonelada. Exemplos:
--
--     CODPROD 20059 FAR.LUNAR PREMIUM 25KG : VLRUNIT 91,52  CUSGER  62,42
--     CODPROD 20024 FAR.LUNAR PLUS 25KG    : VLRUNIT 80,67  CUSGER  50,05
--     CODPROD 20007 FAR.LUNAR PP 1KG       : VLRUNIT 32,62  CUSGER  22,36
--     CODPROD 20029 FARELO IDEAL 40KG      : VLRUNIT 72,84  CUSGER  58,83
--
--   A formula anterior (tonliq * custo) produzia margem proxy de 98,7%,
--   economicamente impossivel para um moinho.
--
--   Formula correta:  custo_total = QTD * custo_unitario
--   Devolucao tem QTD negativa, entao o sinal se preserva sozinho.
--
-- RESSALVA REGISTRADA (Q-15): uma minoria de produtos tem custo em escala
-- incompativel com o preco (ex.: 20128 FAR.TIA NENA 25KG, VLRUNIT 75,69 e
-- CUSGER 3.677,62). Esses casos NAO sao corrigidos aqui: sao sinalizados
-- pela verificacao de qualidade 'custo_fora_de_escala' e pela flag
-- custo_escala_suspeita, para decisao da Controladoria.
-- =====================================================================

-- CREATE OR REPLACE VIEW so aceita colunas novas no FIM da lista; como a flag
-- entra no meio, a view e recriada do zero. As MVs que dependem dela caem junto
-- e sao reconstruidas mais abaixo.
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_trigo_cost_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_product_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_region_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_seller_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_customer_month CASCADE;
DROP VIEW IF EXISTS analytics.v_venda_item CASCADE;

-- Item enriquecido ganha a flag de escala suspeita do custo
CREATE VIEW analytics.v_venda_item AS
WITH escala AS (
    -- Razao mediana entre custo unitario e preco unitario, por produto.
    -- Acima de 3x, o custo esta em outra escala (ou e um erro de cadastro).
    SELECT codprod,
           percentile_cont(0.5) WITHIN GROUP (
               ORDER BY cusger / NULLIF(vlrunit, 0)
           ) AS razao_custo_preco
    FROM analytics.fact_venda_item
    WHERE NOT is_devolucao AND vlrunit > 0 AND cusger > 0
    GROUP BY codprod
)
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
    p.unidade                                   AS unidade_produto,
    c.parceiro,
    c.uf                                        AS uf_cliente,
    c.cidade                                    AS cidade_cliente,
    c.ramo_atividade,
    c.perfil_empresa,
    v.apelido                                   AS vendedor,
    v.papel_analitico,
    v.tipo_vend,
    r.nomereg                                   AS regiao_comercial,
    e.razao_custo_preco,
    (e.razao_custo_preco > 3)                   AS custo_escala_suspeita
FROM analytics.fact_venda_item i
LEFT JOIN analytics.fact_venda_documento d ON d.nunota  = i.nunota
LEFT JOIN analytics.dim_produto          p ON p.codprod = i.codprod
LEFT JOIN analytics.dim_cliente          c ON c.codparc = i.codparc
LEFT JOIN analytics.dim_vendedor         v ON v.codvend = i.codvend
LEFT JOIN analytics.dim_regiao           r ON r.codreg  = i.codreg
LEFT JOIN escala                         e ON e.codprod = i.codprod;

COMMENT ON VIEW analytics.v_venda_item IS
    'Item + dimensoes + flag de escala de custo. documento_vlrnota vem junto apenas '
    'para drill-down ate a nota: NUNCA soma-lo neste grao (RN-02).';

-- ---------------------------------------------------------------------
-- Recriacao das MVs com custo = QTD * custo_unitario
-- ---------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_trigo_cost_month CASCADE;
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
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)                AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)                AS ton_para_pmv,
    -- Custo na unidade de venda; exclui produtos com escala suspeita (Q-15)
    SUM(qtd * cusmed)      FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusmed,
    SUM(qtd * cusmedicm)   FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusmedicm,
    SUM(qtd * cussemicm)   FILTER (WHERE NOT custo_escala_suspeita) AS custo_cussemicm,
    SUM(qtd * cusrep)      FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusrep,
    SUM(qtd * cusger)      FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusger,
    SUM(qtd * cusvariavel) FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusvariavel,
    -- Receita comparavel ao custo (mesma populacao de linhas)
    SUM(vlrtot) FILTER (WHERE NOT custo_escala_suspeita)         AS receita_com_custo,
    SUM(tonliq) FILTER (WHERE NOT custo_escala_suspeita)         AS ton_com_custo,
    COUNT(*)    FILTER (WHERE custo_escala_suspeita)             AS linhas_custo_suspeito
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes;

CREATE UNIQUE INDEX ON analytics.mv_sales_month (ano, mes);

COMMENT ON MATERIALIZED VIEW analytics.mv_sales_month IS
    'custo_* = SUM(QTD * custo_unitario), excluindo produtos com escala de custo '
    'suspeita (Q-15). Compare sempre com receita_com_custo, nunca com receita_liquida.';

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_product_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_product_month AS
SELECT
    ano, mes, ano_mes, codprod, descrprod, classificacao, grupo_produto,
    COUNT(DISTINCT codparc)                          AS clientes,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(qtd)                                         AS quantidade,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrdesc)                                     AS desconto,
    bool_or(custo_escala_suspeita)                   AS custo_escala_suspeita,
    SUM(qtd * cusmed)                                AS custo_cusmed,
    SUM(qtd * cusmedicm)                             AS custo_cusmedicm,
    SUM(qtd * cussemicm)                             AS custo_cussemicm,
    SUM(qtd * cusrep)                                AS custo_cusrep,
    SUM(qtd * cusger)                                AS custo_cusger,
    SUM(qtd * cusvariavel)                           AS custo_cusvariavel
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codprod, descrprod, classificacao, grupo_produto;

CREATE UNIQUE INDEX ON analytics.mv_sales_product_month (ano, mes, codprod);

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_region_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_region_month AS
SELECT
    ano, mes, ano_mes, codreg, regiao_comercial, uf_cliente, cidade_cliente,
    COUNT(DISTINCT codparc)                          AS clientes,
    COUNT(DISTINCT codvend)                          AS vendedores,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrfrete_alocado)                            AS frete_alocado,
    SUM(qtd * cusger) FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusger,
    SUM(vlrtot)       FILTER (WHERE NOT custo_escala_suspeita) AS receita_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codreg, regiao_comercial, uf_cliente, cidade_cliente;

CREATE INDEX ON analytics.mv_sales_region_month (ano, mes);
CREATE INDEX ON analytics.mv_sales_region_month (uf_cliente);

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_seller_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_seller_month AS
SELECT
    ano, mes, ano_mes, codvend, vendedor, papel_analitico, tipo_vend,
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
    SUM(qtd * cusger) FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusger,
    SUM(vlrtot)       FILTER (WHERE NOT custo_escala_suspeita) AS receita_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codvend, vendedor, papel_analitico, tipo_vend;

CREATE UNIQUE INDEX ON analytics.mv_sales_seller_month (ano, mes, codvend);

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_customer_month CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_sales_customer_month AS
SELECT
    ano, mes, ano_mes, codparc, parceiro, uf_cliente, cidade_cliente, ramo_atividade,
    codvend, vendedor, codreg, regiao_comercial,
    COUNT(DISTINCT nunota)                           AS documentos,
    COUNT(DISTINCT codprod)                          AS produtos,
    SUM(vlrtot)                                      AS receita_liquida,
    SUM(tonliq)                                      AS ton_liquida,
    SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)    AS receita_para_pmv,
    SUM(tonliq) FILTER (WHERE NOT is_sem_receita)    AS ton_para_pmv,
    SUM(vlrfrete_alocado)                            AS frete_alocado,
    SUM(qtd * cusger) FILTER (WHERE NOT custo_escala_suspeita) AS custo_cusger,
    SUM(vlrtot)       FILTER (WHERE NOT custo_escala_suspeita) AS receita_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codparc, parceiro, uf_cliente, cidade_cliente,
         ramo_atividade, codvend, vendedor, codreg, regiao_comercial;

CREATE INDEX ON analytics.mv_sales_customer_month (ano, mes);
CREATE INDEX ON analytics.mv_sales_customer_month (codparc);

-- Trigo x custo x PMV: custo por tonelada agora derivado do custo por unidade
CREATE MATERIALIZED VIEW analytics.mv_trigo_cost_month AS
SELECT
    COALESCE(t.ano_mes, e.ano_mes, s.ano_mes)  AS ano_mes,
    t.preco_medio                              AS trigo_preco_medio,
    t.ton_total                                AS trigo_ton_comprada,
    e.ton_estoque                              AS trigo_ton_estoque,
    e.preco_medio                              AS trigo_estoque_preco_medio,
    s.receita_para_pmv / NULLIF(s.ton_para_pmv, 0)   AS pmv,
    s.custo_cusmed      / NULLIF(s.ton_com_custo, 0) AS cusmed_por_ton,
    s.custo_cusger      / NULLIF(s.ton_com_custo, 0) AS cusger_por_ton,
    s.custo_cusvariavel / NULLIF(s.ton_com_custo, 0) AS cusvariavel_por_ton,
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
