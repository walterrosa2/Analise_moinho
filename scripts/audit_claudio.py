import sys
import os
sys.path.insert(0, os.path.abspath("."))
from src.db.engine import read_sql
import polars as pl
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("INVESTIGAÇÃO DE QUEM É 'CLÁUDIO' OU O REPRESENTANTE COM 190 CLIENTES / 11 CIDADES / 16% POSITIVAÇÃO")
print("="*80)

# Ver todos os vendedores em 2023-01 a 2026-06
df_vends_42m = read_sql("""
    SELECT 
        v.codvend,
        d.apelido,
        d.nomeparc,
        d.cidade as cidade_cadastro,
        d.regiao as regiao_cadastro,
        COUNT(DISTINCT v.codparc) as clientes_unicos,
        COUNT(DISTINCT v.ciddestino) as cidades_atendidas,
        COUNT(DISTINCT v.ano_mes || '-' || v.codparc::text) as total_positivacoes,
        SUM(v.vlrtot) as receita_liquida,
        SUM(v.tonliq) as volume_liquido_ton,
        100.0 * COUNT(DISTINCT v.ano_mes || '-' || v.codparc::text) / 
          (SELECT COUNT(DISTINCT ano_mes || '-' || codparc::text) FROM analytics.v_venda_item WHERE NOT is_devolucao AND ano_mes <= '2026-06') as pct_positivacao_42m
    FROM analytics.v_venda_item v
    LEFT JOIN analytics.dim_vendedor d ON v.codvend = d.codvend
    WHERE NOT v.is_devolucao AND v.ano_mes <= '2026-06'
    GROUP BY v.codvend, d.apelido, d.nomeparc, d.cidade, d.regiao
    ORDER BY total_positivacoes DESC
""")
print(df_vends_42m.to_pandas().head(15).to_string())

# Verificar clientes por ano / no último ano (2025/2026)
df_vends_2026 = read_sql("""
    SELECT 
        v.codvend,
        d.apelido,
        d.nomeparc,
        COUNT(DISTINCT v.codparc) as clientes_unicos_2026,
        COUNT(DISTINCT v.ciddestino) as cidades_2026,
        COUNT(DISTINCT v.ano_mes || '-' || v.codparc::text) as positivacoes_2026,
        100.0 * COUNT(DISTINCT v.ano_mes || '-' || v.codparc::text) / 
          (SELECT COUNT(DISTINCT ano_mes || '-' || codparc::text) FROM analytics.v_venda_item WHERE NOT is_devolucao AND ano_mes LIKE '2026%') as pct_pos_2026
    FROM analytics.v_venda_item v
    LEFT JOIN analytics.dim_vendedor d ON v.codvend = d.codvend
    WHERE NOT v.is_devolucao AND v.ano_mes LIKE '2026%'
    GROUP BY v.codvend, d.apelido, d.nomeparc
    ORDER BY positivacoes_2026 DESC
""")
print("\nVendedores em 2026:")
print(df_vends_2026.to_pandas().head(10).to_string())

# Verificar se existe algum arquivo de apresentação ou texto no repositório que menciona "Cláudio"
# ou notas anteriores
