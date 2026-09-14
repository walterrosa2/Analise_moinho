import sys
import os
sys.path.insert(0, os.path.abspath("."))
from src.db.engine import read_sql
import polars as pl
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# Comparar devolução por DTFATUR vs DTNEG
dev_dtneg = read_sql("""
    SELECT 
        to_char(dtneg, 'YYYY-MM') as ano_mes_neg,
        ABS(SUM(tonliq)) as ton_dev,
        ABS(SUM(vlrtot)) as vlr_dev
    FROM analytics.fact_venda_item
    WHERE is_devolucao AND to_char(dtneg, 'YYYY') = '2026'
    GROUP BY to_char(dtneg, 'YYYY-MM')
    ORDER BY ano_mes_neg
""")
print("Devoluções por DTNEG:")
print(dev_dtneg.to_pandas().to_string())

# Verificar CR Promoções (codvend 29) e Cláudio
cr_detalhe = read_sql("""
    SELECT * FROM analytics.dim_vendedor WHERE codvend = 29
""")
print("\nDim Vendedor codvend 29:")
print(cr_detalhe.to_pandas().to_string())
