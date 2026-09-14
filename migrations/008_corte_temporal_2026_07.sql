-- =====================================================================
-- Migration 008: Corte temporal oficial (2023-01 a 2026-07)
-- =====================================================================
-- Expurgar notas e registros residuais posteriores a 2026-07 (ex.: estornos de 08/2026
-- que entraram sem mês de venda correspondente) e atualizar todas as Materialized Views.
-- =====================================================================

DELETE FROM analytics.fact_venda_item 
WHERE ano_mes > '2026-07' OR data_referencia > '2026-07-31';

DELETE FROM analytics.fact_venda_documento 
WHERE ano_mes > '2026-07' OR data_referencia > '2026-07-31';

DELETE FROM analytics.fact_positivado 
WHERE ano_mes > '2026-07';

DELETE FROM analytics.fact_positivado_mes 
WHERE ano_mes > '2026-07';

-- Refresh em todas as Materialized Views para propagar a exclusão imediatamente
REFRESH MATERIALIZED VIEW analytics.mv_custo_mediana_produto;
REFRESH MATERIALIZED VIEW analytics.mv_sales_month;
REFRESH MATERIALIZED VIEW analytics.mv_sales_product_month;
REFRESH MATERIALIZED VIEW analytics.mv_sales_region_month;
REFRESH MATERIALIZED VIEW analytics.mv_sales_seller_month;
REFRESH MATERIALIZED VIEW analytics.mv_sales_customer_month;
REFRESH MATERIALIZED VIEW analytics.mv_freight_route_month;
REFRESH MATERIALIZED VIEW analytics.mv_freight_carrier_month;
REFRESH MATERIALIZED VIEW analytics.mv_cost_product_month;
REFRESH MATERIALIZED VIEW analytics.mv_positivados_cohort;
REFRESH MATERIALIZED VIEW analytics.mv_trigo_cost_month;
REFRESH MATERIALIZED VIEW analytics.mv_vendas_municipio_mg;
REFRESH MATERIALIZED VIEW analytics.mv_mercado_municipio_mg;
