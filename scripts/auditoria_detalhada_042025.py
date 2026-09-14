# -*- coding: utf-8 -*-
import os
import sys
import polars as pl
import pandas as pd
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')

print("="*80)
print("AUDITORIA E INVESTIGAÇÃO PROFUNDA DO MÊS 04/2025")
print("="*80)

# Carregar Parquet
df_vendas = pl.read_parquet("data/parquet/vendas_dev.parquet")

# Tratar campos principais
df = df_vendas.with_columns([
    pl.col("DTFATUR").cast(pl.Utf8).str.slice(0, 10).alias("data_fat_str"),
    pl.col("DTNEG").cast(pl.Utf8).str.slice(0, 10).alias("data_neg_str"),
    pl.col("TONLIQ").cast(pl.Float64, strict=False).alias("tonliq"),
    pl.col("VLRTOT").cast(pl.Float64, strict=False).alias("vlrtot"),
    pl.col("QTD").cast(pl.Float64, strict=False).alias("qtd"),
    pl.col("PESOLIQ").cast(pl.Float64, strict=False).alias("pesoliq"),
])

df = df.with_columns([
    pl.coalesce(
        pl.col("data_fat_str").str.to_date("%Y-%m-%d", strict=False),
        pl.col("data_neg_str").str.to_date("%Y-%m-%d", strict=False)
    ).alias("dt_ref")
]).with_columns([
    pl.col("dt_ref").dt.strftime("%Y-%m").alias("ano_mes"),
    pl.col("dt_ref").dt.strftime("%Y-%m-%d").alias("data_str"),
    (pl.col("TIPMOV") == "D").alias("is_dev")
])

# 1. VERIFICAR SE O EXCEL ORIGINAL CONTÉM EXATAMENTE OS MESMOS DADOS (VALIDAÇÃO DE INTEGRIDADE)
print("\n--- 1. AUDITORIA DA FONTE BRUTA (EXCEL vs PARQUET) ---")
excel_file = "data/input/VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx"
# Ler amostra ou usar calamine/openpyxl para contar linhas totais
print(f"Total de linhas em vendas_dev.parquet: {df.height:,}")
# Verificar metadados de ingestão gravados no parquet
batch_ids = df["_ingestion_batch_id"].unique().to_list()
source_hashes = df["_source_file_hash"].unique().to_list()
print(f"Batch IDs: {batch_ids}, Source hash: {source_hashes}")

# 2. COMPARAR OUTROS RELATÓRIOS DO MESMO MÊS (161 - Gestão Diária e Positivados)
print("\n--- 2. CONFERÊNCIA COM OUTRAS FONTES INDEPENDENTES ---")
for f_name, f_path in [
    ("Gestão Diária 161", "data/parquet/gestao_diaria_161.parquet"),
    ("Positivados", "data/parquet/positivados_mensal.parquet"),
    ("CTE (Frete)", "data/parquet/cte.parquet")
]:
    if os.path.exists(f_path):
        df_ext = pl.read_parquet(f_path)
        print(f"Arquivo: {f_name} | Colunas: {df_ext.columns[:6]} | Linhas: {df_ext.height}")
        # Se tiver data ou mes_ano
        for c in df_ext.columns:
            if "MES" in c.upper() or "DATA" in c.upper() or "DT" in c.upper() or "ANO_MES" in c.upper():
                print(f"  Coluna temporal encontrada: {c}")

# 3. ANÁLISE COMPARATIVA: 04/2025 vs 03/2025 vs 05/2025 vs 04/2024
print("\n--- 3. COMPARATIVO DETALHADO ENTRE MESES PRÓXIMOS ---")
meses_interesse = ["2024-04", "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2026-04"]
df_comp = df.filter(pl.col("ano_mes").is_in(meses_interesse))

# Analisar por Categoria / Família / Tipo de Produto
print("\n>>> POR PRODUTO / GRUPO DE PRODUTOS:")
prod_comp = (
    df_comp.filter(pl.col("ano_mes").is_in(["2025-03", "2025-04", "2025-05", "2024-04"]))
    .group_by(["ano_mes", "DESCRPROD"])
    .agg([
        pl.col("tonliq").sum().alias("ton"),
        pl.col("vlrtot").sum().alias("receita"),
        pl.count().alias("qtd_itens")
    ])
    .sort(["ano_mes", "ton"], descending=[False, True])
)

# Top 10 produtos de 03/2025, 04/2025 e 05/2025
for m in ["2025-03", "2025-04", "2025-05"]:
    print(f"\nTop 8 Produtos em {m}:")
    top_p = prod_comp.filter(pl.col("ano_mes") == m).head(8)
    for r in top_p.iter_rows(named=True):
        print(f"  {r['DESCRPROD'][:40]:<40} | {r['ton']:>9.2f} t | R$ {r['receita']:>11,.2f} | {r['qtd_itens']:>4} itens")

# 4. ANÁLISE POR REGIÃO COMERCIAL
print("\n>>> POR REGIÃO COMERCIAL:")
reg_comp = (
    df_comp.filter(pl.col("ano_mes").is_in(["2025-03", "2025-04", "2025-05", "2024-04"]))
    .group_by(["ano_mes", "NOMEREG"])
    .agg([
        pl.col("tonliq").sum().alias("ton"),
        pl.col("vlrtot").sum().alias("receita")
    ])
    .sort(["ano_mes", "ton"], descending=[False, True])
)
for m in ["2025-03", "2025-04", "2025-05"]:
    print(f"\nTop Regiões em {m}:")
    top_r = reg_comp.filter(pl.col("ano_mes") == m).head(8)
    for r in top_r.iter_rows(named=True):
        print(f"  {str(r['NOMEREG'])[:30]:<30} | {r['ton']:>9.2f} t | R$ {r['receita']:>11,.2f}")

# 5. ANÁLISE POR CLIENTE (PERDA DE CLIENTE GRANDE OU QUEDA GERAL?)
print("\n>>> POR TOP 10 CLIENTES:")
cli_comp = (
    df_comp.filter(pl.col("ano_mes").is_in(["2025-03", "2025-04", "2025-05"]))
    .group_by(["ano_mes", "PARCEIRO", "CODPARC"])
    .agg([
        pl.col("tonliq").sum().alias("ton"),
        pl.col("vlrtot").sum().alias("receita")
    ])
    .sort(["ano_mes", "ton"], descending=[False, True])
)
for m in ["2025-03", "2025-04", "2025-05"]:
    print(f"\nTop 5 Clientes em {m}:")
    top_c = cli_comp.filter(pl.col("ano_mes") == m).head(5)
    for r in top_c.iter_rows(named=True):
        print(f"  [{r['CODPARC']}] {str(r['PARCEIRO'])[:35]:<35} | {r['ton']:>8.2f} t | R$ {r['receita']:>11,.2f}")

# 6. ANÁLISE DE DIAS ÚTEIS E DIAS TRABALHADOS
print("\n>>> ANÁLISE DE DIAS TRABALHADOS / DIAS COM FATURAMENTO:")
for m in ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2024-04", "2026-04"]:
    df_m = df.filter(pl.col("ano_mes") == m)
    dias_faturamento = df_m["data_str"].n_unique()
    nfs = df_m["NUNOTA"].n_unique()
    ton = df_m["tonliq"].sum()
    rec = df_m["vlrtot"].sum()
    ton_por_dia = ton / dias_faturamento if dias_faturamento else 0
    ton_por_nf = ton / nfs if nfs else 0
    print(f"Mês {m}: Dias c/ faturam={dias_faturamento:>2} | NFs={nfs:>4} | NFs/dia={nfs/dias_faturamento:>5.1f} | Ton={ton:>8.2f} t | Ton/dia={ton_por_dia:>6.2f} t/dia | Ton/NF={ton_por_nf:>5.2f} t/NF | Rec=R$ {rec:>11,.2f}")

# 7. ANÁLISE DE OPERAÇÕES (CODTIPOPER / DESCROPER)
print("\n>>> POR TIPO DE OPERAÇÃO EM 04/2025 vs 03/2025 e 05/2025:")
oper_comp = (
    df_comp.filter(pl.col("ano_mes").is_in(["2025-03", "2025-04", "2025-05"]))
    .group_by(["ano_mes", "CODTIPOPER", "DESCROPER"])
    .agg([
        pl.col("tonliq").sum().alias("ton"),
        pl.col("vlrtot").sum().alias("receita"),
        pl.count().alias("itens")
    ])
    .sort(["ano_mes", "ton"], descending=[False, True])
)
for m in ["2025-03", "2025-04", "2025-05"]:
    print(f"\nOperações em {m}:")
    top_o = oper_comp.filter(pl.col("ano_mes") == m).head(6)
    for r in top_o.iter_rows(named=True):
        print(f"  [{r['CODTIPOPER']}] {str(r['DESCROPER'])[:35]:<35} | {r['ton']:>8.2f} t | R$ {r['receita']:>11,.2f} | {r['itens']} itens")
