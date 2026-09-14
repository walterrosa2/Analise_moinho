import sys
import os
sys.path.insert(0, os.path.abspath("."))
from src.db.engine import read_sql
import polars as pl
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("AUDITORIA DETALHADA: RECORTE ATÉ 2026-06 E IDENTIFICAÇÃO DE VENDEDORES")
print("="*80)

# 1. Leonel Soares até 2026-06
leonel_jun26 = read_sql("""
    SELECT 
        codvend,
        SUM(vlrtot) as rec_liq,
        SUM(tonliq) as vol_liq,
        SUM(vlrtot) FILTER (WHERE NOT is_sem_receita) / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) as pmv_sem_bonif
    FROM analytics.v_venda_item
    WHERE codvend = 455 AND ano_mes <= '2026-06' AND NOT is_devolucao
    GROUP BY codvend
""")
print("\nLeonel Soares até 2026-06:")
print(leonel_jun26.to_pandas().to_string())

# 2. Verificar quem tem ~190 clientes, ~11 cidades, ~16% positivação
vends_todos = read_sql("""
    SELECT 
        v.codvend,
        d.apelido,
        d.nomeparc,
        d.papel_analitico,
        d.tipo_vend,
        COUNT(DISTINCT v.codparc) as clientes_unicos,
        COUNT(DISTINCT v.ciddestino) as cidades_atendidas,
        COUNT(DISTINCT v.ano_mes || '-' || v.codparc::text) as total_positivacoes,
        SUM(v.vlrtot) as receita_liquida,
        SUM(v.tonliq) as volume_liquido_ton,
        SUM(v.vlrtot) FILTER (WHERE NOT v.is_sem_receita) / NULLIF(SUM(v.tonliq) FILTER (WHERE NOT v.is_sem_receita), 0) as pmv_sem_bonif,
        100.0 * COUNT(DISTINCT v.ano_mes || '-' || v.codparc::text) / 
          (SELECT COUNT(DISTINCT ano_mes || '-' || codparc::text) FROM analytics.v_venda_item WHERE NOT is_devolucao) as pct_positivacao_geral
    FROM analytics.v_venda_item v
    LEFT JOIN analytics.dim_vendedor d ON v.codvend = d.codvend
    WHERE NOT v.is_devolucao
    GROUP BY v.codvend, d.apelido, d.nomeparc, d.papel_analitico, d.tipo_vend
    ORDER BY total_positivacoes DESC
""")
print("\nRanking de Positivações por Vendedor:")
print(vends_todos.to_pandas().to_string())

# Verificar se existe algum Claudio em outra tabela ou campo
print("\nBusca por Claudio em todas as fontes:")
claudio_busca = read_sql("""
    SELECT * FROM analytics.dim_vendedor 
    WHERE apelido ILIKE '%CLAUDIO%' OR nomeparc ILIKE '%CLAUDIO%'
""")
print(claudio_busca.to_pandas().to_string())

# Verificar representantes com ~190 clientes
print("\nVendedores com clientes entre 150 e 250:")
print(vends_todos.to_pandas()[(vends_todos.to_pandas()['clientes_unicos'] >= 150) & (vends_todos.to_pandas()['clientes_unicos'] <= 250)].to_string())

# Verificar devoluções Jan/2026 e Jun/2026 com detalhe de tonelada e valor
dev_comp = read_sql("""
    SELECT 
        ano_mes,
        ABS(SUM(tonliq)) as ton_dev,
        ABS(SUM(vlrtot)) as vlr_dev,
        COUNT(DISTINCT nunota) as qtd_notas
    FROM analytics.fact_venda_item
    WHERE is_devolucao AND ano_mes IN ('2026-01', '2026-06')
    GROUP BY ano_mes
    ORDER BY ano_mes
""")
print("\nDevoluções Jan/2026 vs Jun/2026:")
print(dev_comp.to_pandas().to_string())
