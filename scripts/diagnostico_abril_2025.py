# -*- coding: utf-8 -*-
import os
import sys
import polars as pl
import pandas as pd
from datetime import datetime

# Configurar stdout para utf-8
sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("DIAGNÓSTICO DETALHADO DO MÊS 04/2025 E COMPARAÇÃO TEMPORAL")
print("="*80)

# 1. Leitura do Parquet
parquet_path = "data/parquet/vendas_dev.parquet"
df_p = pl.read_parquet(parquet_path)
print(f"Total de registros em vendas_dev.parquet: {df_p.height:,}")

# Analisar os campos de data no parquet: DTNEG, DTFATUR, DTENTSAI
print("\n--- TIPOS DE DADOS DAS COLUNAS DE DATA ---")
for col in ["DTNEG", "DTFATUR", "DTENTSAI"]:
    print(f"{col}: {df_p[col].dtype}, nulos: {df_p[col].null_count()}")

# Converter datas para string YYYY-MM
# Tratar DTFATUR, DTNEG, DTENTSAI
df_dates = df_p.select([
    pl.col("NUNOTA").alias("nunota"),
    pl.col("TIPMOV").alias("tipmov"),
    pl.col("DTNEG").alias("dtneg_raw"),
    pl.col("DTFATUR").alias("dtfatur_raw"),
    pl.col("DTENTSAI").alias("dtentsai_raw"),
    pl.col("TONLIQ").cast(pl.Float64, strict=False).alias("tonliq"),
    pl.col("VLRTOT").cast(pl.Float64, strict=False).alias("vlrtot"),
])

# Converter para data se for string ou datetime
for col in ["dtneg", "dtfatur", "dtentsai"]:
    raw_col = f"{col}_raw"
    if df_dates[raw_col].dtype == pl.Utf8:
        df_dates = df_dates.with_columns(
            pl.col(raw_col).str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias(col)
        )
    else:
        df_dates = df_dates.with_columns(
            pl.col(raw_col).cast(pl.Date, strict=False).alias(col)
        )

df_dates = df_dates.with_columns([
    pl.col("dtneg").dt.strftime("%Y-%m").alias("mes_dtneg"),
    pl.col("dtfatur").dt.strftime("%Y-%m").alias("mes_dtfatur"),
    pl.col("dtentsai").dt.strftime("%Y-%m").alias("mes_dtentsai"),
    pl.coalesce(pl.col("dtfatur"), pl.col("dtneg"), pl.col("dtentsai")).dt.strftime("%Y-%m").alias("mes_referencia"),
    pl.coalesce(pl.col("dtfatur"), pl.col("dtneg"), pl.col("dtentsai")).alias("data_referencia")
])

print("\n--- COMPARAÇÃO DE VOLUMES E LINHAS POR ANO-MÊS (DATA DE REFERÊNCIA = DTFATUR COALESCE) ---")
resumo_mes = (
    df_dates.group_by("mes_referencia")
    .agg([
        pl.count().alias("linhas"),
        pl.col("nunota").n_unique().alias("documentos"),
        pl.col("tonliq").filter(pl.col("tipmov") != "D").sum().alias("ton_vendas"),
        pl.col("tonliq").filter(pl.col("tipmov") == "D").sum().alias("ton_devol"),
        pl.col("tonliq").sum().alias("ton_liquida"),
        pl.col("vlrtot").filter(pl.col("tipmov") != "D").sum().alias("rec_vendas"),
        pl.col("vlrtot").filter(pl.col("tipmov") == "D").sum().alias("rec_devol"),
        pl.col("vlrtot").sum().alias("rec_liquida"),
    ])
    .sort("mes_referencia")
)

for row in resumo_mes.iter_rows(named=True):
    m = row["mes_referencia"]
    if m and ("2024" in m or "2025" in m or "2026" in m or "2023" in m):
        print(f"Mês {m}: Linhas={row['linhas']:>6} | NFs={row['documentos']:>5} | TonLiq={row['ton_liquida']:>10.2f} t (Vendas: {row['ton_vendas']:>10.2f}, Dev: {row['ton_devol']:>8.2f}) | RecLiq=R$ {row['rec_liquida']:>12,.2f}")

print("\n" + "="*80)
print("FOCO EM 2025: DETALHAMENTO DIA A DIA DE 04/2025 vs 03/2025 e 05/2025")
print("="*80)

# Filtrar 2025-04
df_2025_04 = df_dates.filter(pl.col("mes_referencia") == "2025-04")
print(f"Total registros em 2025-04: {df_2025_04.height}")

# Agrupamento diário em abril/2025
resumo_dia_04 = (
    df_2025_04.group_by(pl.col("data_referencia").dt.strftime("%Y-%m-%d").alias("dia"))
    .agg([
        pl.count().alias("linhas"),
        pl.col("nunota").n_unique().alias("documentos"),
        pl.col("tonliq").filter(pl.col("tipmov") != "D").sum().alias("ton_vendas"),
        pl.col("tonliq").filter(pl.col("tipmov") == "D").sum().alias("ton_devol"),
        pl.col("tonliq").sum().alias("ton_liquida"),
        pl.col("vlrtot").sum().alias("rec_liquida"),
    ])
    .sort("dia")
)

print("\nDias com movimentação em 2025-04:")
for row in resumo_dia_04.iter_rows(named=True):
    print(f"Dia {row['dia']}: Linhas={row['linhas']:>5} | NFs={row['documentos']:>4} | Ton={row['ton_liquida']:>8.2f} t | Rec=R$ {row['rec_liquida']:>10,.2f}")

# Verificar se há registros onde DTNEG é 2025-04 mas DTFATUR é outro mês, ou vice-versa!
print("\n" + "="*80)
print("CRUZAMENTO DE DATAS (DTNEG vs DTFATUR vs DTENTSAI)")
print("="*80)
cruzamento_neg = df_dates.filter(pl.col("mes_dtneg") == "2025-04").group_by("mes_dtfatur").agg([
    pl.count().alias("linhas"),
    pl.col("tonliq").sum().alias("ton_liquida")
])
print("Quando DTNEG é 2025-04, onde está o DTFATUR?")
for row in cruzamento_neg.iter_rows(named=True):
    print(f"  DTFATUR = {row['mes_dtfatur']}: Linhas={row['linhas']}, Ton={row['ton_liquida']:.2f} t")

cruzamento_fat = df_dates.filter(pl.col("mes_dtfatur") == "2025-04").group_by("mes_dtneg").agg([
    pl.count().alias("linhas"),
    pl.col("tonliq").sum().alias("ton_liquida")
])
print("\nQuando DTFATUR é 2025-04, onde está o DTNEG?")
for row in cruzamento_fat.iter_rows(named=True):
    print(f"  DTNEG = {row['mes_dtneg']}: Linhas={row['linhas']}, Ton={row['ton_liquida']:.2f} t")

# Verificar no Excel Original se existem mais registros para 04/2025
print("\n" + "="*80)
print("VERIFICAÇÃO NA PLANILHA EXCEL ORIGINAL")
print("="*80)
excel_path = "data/input/VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx"
if os.path.exists(excel_path):
    print(f"Arquivo original existe: {excel_path} (Tamanho: {os.path.getsize(excel_path):,} bytes)")
else:
    print(f"Arquivo original NÃO encontrado: {excel_path}")
