-- =====================================================================
-- 006 - Deteccao de outlier de custo (por linha, nao por produto)
-- =====================================================================
-- ACHADO (Q-15): a fonte de custos contem valores extremos pontuais.
--
--   CODPROD 20036 FAR.LUNAR 25KG     : CUSGER de 0,96 a 341.322,41 (mediana 47,08)
--   CODPROD 20048 P.M.LUNAR MIX PREM : CUSGER de 24,16 a 332.804,49 (mediana 50,47)
--   CODPROD 20128 FAR.TIA NENA 25KG  : CUSGER de -0,66 a 341.323,81 (mediana 48,38)
--
-- A mediana (~R$ 47-50 por saco de 25 kg, ou ~R$ 1.900/t) e coerente com o PMV
-- observado (~R$ 2.500-3.000/t) e confirma que o custo esta na unidade de VENDA.
-- Os extremos sao erro de cadastro no ERP em datas especificas.
--
-- TRATAMENTO (a especificacao proibe corrigir ou excluir dado da origem):
--   1. O dado bruto permanece intacto em raw.* e fact_custo_pa.
--   2. Cada ITEM recebe a flag custo_outlier, comparando o custo aplicado com
--      a mediana do proprio produto.
--   3. Os agregados de custo e margem excluem os outliers e informam quantas
--      linhas ficaram de fora — a plataforma nunca esconde o descarte.
--
-- Criterio: outlier se cusger > 5x a mediana do produto, ou <= 0.
-- Configuravel em config/settings.yaml -> custos.outlier.
-- =====================================================================

DROP MATERIALIZED VIEW IF EXISTS analytics.mv_trigo_cost_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_product_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_region_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_seller_month CASCADE;
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_sales_customer_month CASCADE;
DROP VIEW IF EXISTS analytics.v_venda_item CASCADE;

-- Mediana do custo por produto, materializada para nao recalcular a cada consulta
DROP MATERIALIZED VIEW IF EXISTS analytics.mv_custo_mediana_produto CASCADE;
CREATE MATERIALIZED VIEW analytics.mv_custo_mediana_produto AS
SELECT
    codprod,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cusmed)      AS med_cusmed,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cusmedicm)   AS med_cusmedicm,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cussemicm)   AS med_cussemicm,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cusrep)      AS med_cusrep,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cusger)      AS med_cusger,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cusvariavel) AS med_cusvariavel,
    MIN(cusger) AS min_cusger,
    MAX(cusger) AS max_cusger,
    COUNT(*)    AS registros
FROM analytics.fact_custo_pa
WHERE cusger > 0
GROUP BY codprod;

CREATE UNIQUE INDEX ON analytics.mv_custo_mediana_produto (codprod);

COMMENT ON MATERIALIZED VIEW analytics.mv_custo_mediana_produto IS
    'Mediana de cada conceito de custo por produto. Referencia para detectar '
    'outliers sem alterar o dado de origem (Q-15).';

CREATE VIEW analytics.v_venda_item AS
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
    m.med_cusger,
    -- Outlier: custo aplicado muito acima da mediana do proprio produto,
    -- ou nao positivo. Item sem custo tambem nao entra no agregado.
    (
        i.cusger IS NULL
        OR i.cusger <= 0
        OR m.med_cusger IS NULL
        OR i.cusger > 5 * m.med_cusger
    )                                           AS custo_outlier
FROM analytics.fact_venda_item i
LEFT JOIN analytics.fact_venda_documento      d ON d.nunota  = i.nunota
LEFT JOIN analytics.dim_produto               p ON p.codprod = i.codprod
LEFT JOIN analytics.dim_cliente               c ON c.codparc = i.codparc
LEFT JOIN analytics.dim_vendedor              v ON v.codvend = i.codvend
LEFT JOIN analytics.dim_regiao                r ON r.codreg  = i.codreg
LEFT JOIN analytics.mv_custo_mediana_produto  m ON m.codprod = i.codprod;

COMMENT ON VIEW analytics.v_venda_item IS
    'Item + dimensoes + flag custo_outlier. documento_vlrnota vem junto apenas '
    'para drill-down ate a nota: NUNCA soma-lo neste grao (RN-02).';

-- ---------------------------------------------------------------------
-- MVs: custo = QTD * custo_unitario, excluindo outliers
-- ---------------------------------------------------------------------
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
    SUM(qtd * cusmed)      FILTER (WHERE NOT custo_outlier)      AS custo_cusmed,
    SUM(qtd * cusmedicm)   FILTER (WHERE NOT custo_outlier)      AS custo_cusmedicm,
    SUM(qtd * cussemicm)   FILTER (WHERE NOT custo_outlier)      AS custo_cussemicm,
    SUM(qtd * cusrep)      FILTER (WHERE NOT custo_outlier)      AS custo_cusrep,
    SUM(qtd * cusger)      FILTER (WHERE NOT custo_outlier)      AS custo_cusger,
    SUM(qtd * cusvariavel) FILTER (WHERE NOT custo_outlier)      AS custo_cusvariavel,
    SUM(vlrtot) FILTER (WHERE NOT custo_outlier)                 AS receita_com_custo,
    SUM(tonliq) FILTER (WHERE NOT custo_outlier)                 AS ton_com_custo,
    COUNT(*)    FILTER (WHERE custo_outlier)                     AS linhas_custo_outlier
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes;

CREATE UNIQUE INDEX ON analytics.mv_sales_month (ano, mes);

COMMENT ON MATERIALIZED VIEW analytics.mv_sales_month IS
    'custo_* = SUM(QTD * custo_unitario) sobre itens sem outlier de custo. '
    'Compare custo com receita_com_custo (mesma populacao), nunca com receita_liquida. '
    'linhas_custo_outlier informa o que ficou de fora.';

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
    COUNT(*) FILTER (WHERE custo_outlier)            AS linhas_custo_outlier,
    SUM(qtd * cusmed)      FILTER (WHERE NOT custo_outlier) AS custo_cusmed,
    SUM(qtd * cusmedicm)   FILTER (WHERE NOT custo_outlier) AS custo_cusmedicm,
    SUM(qtd * cussemicm)   FILTER (WHERE NOT custo_outlier) AS custo_cussemicm,
    SUM(qtd * cusrep)      FILTER (WHERE NOT custo_outlier) AS custo_cusrep,
    SUM(qtd * cusger)      FILTER (WHERE NOT custo_outlier) AS custo_cusger,
    SUM(qtd * cusvariavel) FILTER (WHERE NOT custo_outlier) AS custo_cusvariavel,
    SUM(vlrtot)            FILTER (WHERE NOT custo_outlier) AS receita_com_custo,
    SUM(tonliq)            FILTER (WHERE NOT custo_outlier) AS ton_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codprod, descrprod, classificacao, grupo_produto;

CREATE UNIQUE INDEX ON analytics.mv_sales_product_month (ano, mes, codprod);

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
    SUM(qtd * cusger) FILTER (WHERE NOT custo_outlier) AS custo_cusger,
    SUM(vlrtot)       FILTER (WHERE NOT custo_outlier) AS receita_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codreg, regiao_comercial, uf_cliente, cidade_cliente;

CREATE INDEX ON analytics.mv_sales_region_month (ano, mes);
CREATE INDEX ON analytics.mv_sales_region_month (uf_cliente);

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
    SUM(qtd * cusger) FILTER (WHERE NOT custo_outlier) AS custo_cusger,
    SUM(vlrtot)       FILTER (WHERE NOT custo_outlier) AS receita_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codvend, vendedor, papel_analitico, tipo_vend;

CREATE UNIQUE INDEX ON analytics.mv_sales_seller_month (ano, mes, codvend);

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
    SUM(qtd * cusger) FILTER (WHERE NOT custo_outlier) AS custo_cusger,
    SUM(vlrtot)       FILTER (WHERE NOT custo_outlier) AS receita_com_custo
FROM analytics.v_venda_item
GROUP BY ano, mes, ano_mes, codparc, parceiro, uf_cliente, cidade_cliente,
         ramo_atividade, codvend, vendedor, codreg, regiao_comercial;

CREATE INDEX ON analytics.mv_sales_customer_month (ano, mes);
CREATE INDEX ON analytics.mv_sales_customer_month (codparc);

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
    'Correlacao aqui NUNCA e prova de causalidade.';
