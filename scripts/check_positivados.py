# -*- coding: utf-8 -*-
import polars as pl
import sys
sys.stdout.reconfigure(encoding='utf-8')

df_pos = pl.read_parquet('data/parquet/positivados_mensal.parquet')
print('=== POSITIVADOS POR ANO E MÊS (2025) ===')
p2025 = df_pos.filter(pl.col('ANO') == '2025').sort(pl.col('MES').cast(pl.Int32))
for r in p2025.iter_rows(named=True):
    mes_num = int(r["MES"])
    qtd = r["QTD_POSITIVADOS"]
    vlr_geral = float(r["VLRTOT_GERAL"])
    vlr_pos = float(r["VLRTOT_POSITIVADOS"])
    print(f"Mês {mes_num:02d}/2025: Positivados={qtd:>4} | Vlr Geral=R$ {vlr_geral:>12,.2f} | Vlr Positivados=R$ {vlr_pos:>10,.2f}")

print('\n=== COMPARAÇÃO 2024 vs 2025 vs 2026 NA TABELA POSITIVADOS ===')
for ano in ['2024', '2025', '2026']:
    p_ano = df_pos.filter(pl.col('ANO') == ano).sort(pl.col('MES').cast(pl.Int32))
    print(f"\n--- ANO {ano} ---")
    for r in p_ano.iter_rows(named=True):
        mes_num = int(r["MES"])
        vlr_geral = float(r["VLRTOT_GERAL"])
        print(f"  {mes_num:02d}/{ano}: Vlr Geral = R$ {vlr_geral:>12,.2f}")
