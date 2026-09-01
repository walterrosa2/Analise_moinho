"""
Logística e CT-e.

Indicador permanente nesta página: **% de frete não alocado**. O rateio de um
CT-e entre várias notas nunca é escondido (RN-08).
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.repositories import logistics

st.title("Logística e CT-e")
f, base_custo = barra_lateral()

cobertura = logistics.cobertura()
ui.aviso_cobertura_frete(cobertura["pct_frete_nao_alocado"], cobertura["pct_cte_sem_nfe"])

c = st.columns(6)
ui.cartao(c[0], "Frete total (CT-e)", ui.moeda(cobertura["frete_total"], compacto=True))
ui.cartao(c[1], "Frete alocado", ui.moeda(cobertura["frete_alocado"], compacto=True))
ui.cartao(c[2], "% não alocado", ui.percentual(cobertura["pct_frete_nao_alocado"]),
          ajuda="CT-e sem NF-e de venda identificada.")
ui.cartao(c[3], "CT-e", ui.inteiro(cobertura["cte_total"]))
ui.cartao(c[4], "% sem NF-e", ui.percentual(cobertura["pct_cte_sem_nfe"]))
ui.cartao(c[5], "% sem ordem de carga", ui.percentual(cobertura["pct_cte_sem_ordem"]),
          ajuda="Confirma por que ORDEMCARGA não pode ser a chave de relacionamento.")

abas = st.tabs(["Série mensal", "Rotas", "Transportadores e destinos", "Dispersão de carga"])

# ---------------------------------------------------------------------
with abas[0]:
    serie = logistics.serie_mensal(f)
    if serie.height == 0:
        st.warning("Nenhum frete alocado no recorte selecionado.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        ui.secao("Frete mensal")
        fig = ui.barra(serie, "ano_mes", "frete", altura=340)
        fig.add_scatter(x=serie["ano_mes"].to_list(), y=serie["frete_por_ton"].to_list(),
                        name="R$/t", yaxis="y2", mode="lines+markers",
                        line=dict(color=ui.CORES[1], width=2))
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title="R$/t"))
        ui.grafico(fig, serie, "frete_mensal")
    with col2:
        ui.secao("Frete sobre receita")
        ui.grafico(ui.linha(serie, "ano_mes", "frete_sobre_receita", altura=340),
                   serie.select("ano_mes", "frete_sobre_receita"), "frete_receita")

    ui.tabela(serie, "frete_mensal", altura=320, chave="frete_serie")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Rotas", "Origem → destino, com frete por tonelada e carga média.")
    rotas = logistics.rotas(f, limite=200)
    if rotas.height:
        p90 = float(rotas["frete_por_ton"].quantile(0.9) or 0)
        c = st.columns(4)
        ui.cartao(c[0], "Rotas no recorte", ui.inteiro(rotas.height))
        ui.cartao(c[1], "R$/t mediano", ui.moeda(rotas["frete_por_ton"].median()))
        ui.cartao(c[2], "R$/t percentil 90", ui.moeda(p90))
        acima = rotas.filter(pl.col("frete_por_ton") > p90)
        ui.cartao(c[3], "Rotas acima do p90", ui.inteiro(acima.height))

        col1, col2 = st.columns(2)
        with col1:
            ui.grafico(ui.barra(rotas.head(20), "rota", "frete",
                                "Maiores rotas por valor de frete", horizontal=True, altura=460),
                       rotas.head(20), "rotas_frete")
        with col2:
            caras = rotas.filter(pl.col("ton") > 5).sort("frete_por_ton", descending=True).head(20)
            ui.grafico(ui.barra(caras, "rota", "frete_por_ton",
                                "Rotas mais caras por tonelada (mín. 5 t)",
                                horizontal=True, altura=460),
                       caras, "rotas_caras")

        ui.secao("Distribuição de R$/t por UF de destino")
        por_uf = logistics.dispersao_carga(f, limite=3000)
        if por_uf.height:
            ui.grafico(ui.boxplot(por_uf.filter(pl.col("ufdestino").is_not_null()),
                                  "ufdestino", "frete_por_ton",
                                  "Dispersão de R$/t por UF de destino", altura=440),
                       por_uf.filter(pl.col("ufdestino").is_not_null()), "boxplot_uf")

        ui.tabela(rotas, "rotas", altura=400, chave="rotas")

# ---------------------------------------------------------------------
with abas[2]:
    dimensao = st.selectbox(
        "Analisar por",
        ["transportador", "uf_destino", "cidade_destino", "cliente", "vendedor",
         "cif_fob", "uf_origem"],
        format_func=lambda d: d.replace("_", " ").title(), key="log_dim",
    )
    dados = logistics.por_dimensao_logistica(f, dimensao, limite=50)
    if dados.height:
        col1, col2 = st.columns(2)
        with col1:
            ui.grafico(ui.barra(dados.head(20), "rotulo", "frete",
                                f"Frete por {dimensao.replace('_', ' ')}",
                                horizontal=True, altura=460),
                       dados.head(20), f"frete_{dimensao}")
        with col2:
            ui.grafico(ui.barra(dados.head(20), "rotulo", "frete_por_ton",
                                "R$/t", horizontal=True, altura=460),
                       dados.head(20), f"rs_ton_{dimensao}")
        ui.tabela(dados, f"logistica_{dimensao}", altura=400, chave="log_dim_tab")

        if dimensao == "transportador":
            ui.grafico(ui.pareto(dados.head(25), "rotulo", "frete",
                                 "Pareto de transportadores", altura=420),
                       dados.head(25), "pareto_transportador")

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao(
        "Tamanho da carga × custo por tonelada",
        "Testa a hipótese de que cargas pequenas custam desproporcionalmente mais.",
    )
    disp = logistics.dispersao_carga(f, limite=3000)
    if disp.height:
        ui.grafico(
            ui.dispersao(disp, "ton", "frete_por_ton", tamanho="frete",
                         titulo="Tonelagem da nota × R$/t", altura=500),
            disp, "dispersao_carga",
        )

        faixas = disp.with_columns(
            pl.when(pl.col("ton") < 1).then(pl.lit("até 1 t"))
            .when(pl.col("ton") < 5).then(pl.lit("1 a 5 t"))
            .when(pl.col("ton") < 15).then(pl.lit("5 a 15 t"))
            .when(pl.col("ton") < 30).then(pl.lit("15 a 30 t"))
            .otherwise(pl.lit("acima de 30 t")).alias("faixa")
        ).group_by("faixa").agg(
            pl.len().alias("notas"),
            pl.col("frete").sum().alias("frete"),
            pl.col("ton").sum().alias("toneladas"),
            pl.col("frete_por_ton").median().alias("rs_por_ton_mediano"),
        ).sort("toneladas")

        col1, col2 = st.columns([2, 3])
        with col1:
            ui.tabela(faixas, "faixas_carga", altura=300, chave="faixas")
        with col2:
            ui.grafico(ui.barra(faixas, "faixa", "rs_por_ton_mediano",
                                "R$/t mediano por faixa de carga", altura=300),
                       faixas, "faixas_carga_gr")

        st.caption(
            "Distância e perfil de produto também explicam parte da diferença. "
            "O gráfico indica onde investigar, não a conclusão."
        )
