"""Clientes — base, retenção, RFM e matriz crescimento × contribuição."""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.repositories import cohorts, sales

st.title("Clientes")
f, base_custo = barra_lateral()

serie = sales.serie_mensal(f, base_custo)
if serie.height == 0:
    st.warning("Nenhum dado para o recorte selecionado.")
    st.stop()

periodos = serie["ano_mes"].to_list()
kpis = sales.kpis_gerais(f, base_custo)

abas = st.tabs(["Movimento da base", "Matriz crescimento × contribuição", "RFM", "Carteira"])

# ---------------------------------------------------------------------
with abas[0]:
    mov = cohorts.movimento_de_base(f)
    if mov.height:
        c = st.columns(4)
        ui.cartao(c[0], "Clientes ativos (último mês)", ui.inteiro(mov["ativos"][-1]))
        ui.cartao(c[1], "Novos no período", ui.inteiro(mov["novos"].sum()))
        ui.cartao(c[2], "Reativados no período", ui.inteiro(mov["reativados"].sum()),
                  ajuda="Voltaram a comprar após 6+ meses sem movimento.")
        ui.cartao(c[3], "Média de clientes ativos/mês", ui.inteiro(mov["ativos"].mean()))

        ui.grafico(ui.linha(mov, "ano_mes", ["ativos", "novos", "reativados"], altura=400),
                   mov, "movimento_base")
        st.caption(
            "**Definições explícitas:** *novo* = primeira compra da história no mês; "
            "*reativado* = comprou após 6+ meses sem movimento. "
            "Nenhuma dessas regras é convenção oculta — todas estão em `src/repositories/cohorts.py`."
        )

    ui.secao("Clientes por ramo e UF")
    col1, col2 = st.columns(2)
    with col1:
        ramo = sales.por_dimensao(f, "ramo", base_custo)
        if ramo.height:
            ui.grafico(ui.barra(ramo, "rotulo", "clientes", "Clientes por ramo",
                                horizontal=True, altura=340), ramo, "clientes_ramo")
    with col2:
        uf = sales.por_dimensao(f, "uf", base_custo)
        if uf.height:
            ui.grafico(ui.barra(uf.head(15), "rotulo", "clientes", "Clientes por UF",
                                horizontal=True, altura=340), uf, "clientes_uf")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao(
        "Matriz crescimento × contribuição",
        "O quadrante superior direito são clientes grandes que ainda crescem; "
        "o inferior direito, clientes grandes em retração — a prioridade de investigação.",
    )
    c1, c2, c3, c4 = st.columns(4)
    a_ini = c1.selectbox("Período A — de", periodos, index=0, key="cli_a1")
    a_fim = c2.selectbox("A — até", periodos, index=min(11, len(periodos) - 1), key="cli_a2")
    b_ini = c3.selectbox("Período B — de", periodos, index=max(0, len(periodos) - 12), key="cli_b1")
    b_fim = c4.selectbox("B — até", periodos, index=len(periodos) - 1, key="cli_b2")

    matriz = cohorts.crescimento_clientes(f, (a_ini, a_fim), (b_ini, b_fim), limite=400)
    if matriz.height:
        dados = matriz.filter(
            pl.col("variacao_pct").is_not_null() & (pl.col("valor_b") > 0)
        ).with_columns(pl.col("variacao_pct").clip(-100, 300))
        if dados.height:
            fig = ui.dispersao(dados.head(200), "participacao_pct", "variacao_pct",
                               tamanho="valor_b", rotulo=None,
                               titulo="Participação (%) × variação (%)", altura=500)
            fig.add_hline(y=0, line_dash="dot", line_color="rgba(200,200,200,0.5)")
            ui.grafico(fig, dados, "matriz_clientes")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Maiores quedas (clientes relevantes)**")
            quedas = matriz.filter(
                (pl.col("valor_a") > 0) & (pl.col("variacao") < 0)
            ).sort("variacao").head(20)
            ui.tabela(quedas.select("rotulo", "valor_a", "valor_b", "variacao",
                                    "variacao_pct", "participacao_pct"),
                      "clientes_queda", altura=380, chave="queda")
        with col2:
            st.markdown("**Maiores crescimentos**")
            altas = matriz.filter(pl.col("variacao") > 0).sort("variacao", descending=True).head(20)
            ui.tabela(altas.select("rotulo", "valor_a", "valor_b", "variacao",
                                   "variacao_pct", "participacao_pct"),
                      "clientes_crescimento", altura=380, chave="alta")

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao(
        "RFM simplificado",
        "Recência (dias desde a última compra), Frequência (meses com compra) e Valor (receita). "
        "Cada eixo é dividido em 5 faixas iguais dentro do recorte.",
    )
    rfm = cohorts.rfm(f, limite=2000)
    if rfm.height:
        rfm = rfm.with_columns(
            (pl.col("score_recencia") + pl.col("score_frequencia") + pl.col("score_valor"))
            .alias("score_total")
        )
        c = st.columns(4)
        ui.cartao(c[0], "Clientes analisados", ui.inteiro(rfm.height))
        ui.cartao(c[1], "Recência mediana", f"{ui.inteiro(rfm['recencia_dias'].median())} dias")
        ui.cartao(c[2], "Frequência mediana",
                  f"{ui.inteiro(rfm['frequencia_meses'].median())} meses")
        ui.cartao(c[3], "Ticket médio", ui.moeda(rfm["ticket_medio"].median()))

        col1, col2 = st.columns([3, 2])
        with col1:
            ui.grafico(
                ui.dispersao(rfm.head(400), "recencia_dias", "frequencia_meses",
                             tamanho="receita", cor="score_total",
                             titulo="Recência × Frequência (tamanho = receita)", altura=460),
                rfm.head(400), "rfm_scatter",
            )
        with col2:
            faixas = rfm.group_by("score_total").agg(
                pl.len().alias("clientes"), pl.col("receita").sum().alias("receita")
            ).sort("score_total", descending=True)
            ui.grafico(ui.barra(faixas, "score_total", "clientes",
                                "Clientes por score RFM (3 a 15)", altura=460),
                       faixas, "rfm_faixas")

        ui.tabela(
            rfm.select("parceiro", "uf", "cidade", "ramo_atividade", "ultima_compra",
                       "recencia_dias", "frequencia_meses", "documentos", "receita",
                       "ton", "produtos", "ticket_medio", "score_recencia",
                       "score_frequencia", "score_valor", "score_total")
               .sort("score_total", descending=True),
            "rfm_clientes", altura=420, chave="rfm",
        )

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao("Carteira: cross-sell e concentração de produto")
    cli = sales.por_dimensao(f, "cliente", base_custo, limite=500)
    if cli.height:
        mono = cli.filter(pl.col("produtos") == 1)
        c = st.columns(4)
        ui.cartao(c[0], "Clientes no recorte", ui.inteiro(cli.height))
        ui.cartao(c[1], "Mono-produto", ui.inteiro(mono.height),
                  ajuda="Compraram um único produto no período — oportunidade de cross-sell.")
        ui.cartao(c[2], "Produtos por cliente (mediana)", ui.inteiro(cli["produtos"].median()))
        ui.cartao(c[3], "Receita dos mono-produto",
                  ui.moeda(mono["receita_liquida"].sum(), compacto=True))

        ui.grafico(
            ui.dispersao(cli.head(300), "produtos", "receita_liquida",
                         tamanho="ton_liquida", cor="pmv",
                         titulo="Nº de produtos × receita por cliente", altura=440),
            cli.head(300), "cross_sell",
        )
        ui.tabela(
            cli.select("rotulo", "receita_liquida", "ton_liquida", "pmv", "produtos",
                       "documentos", "desconto", "frete_por_ton", "margem_proxy_pct"),
            "carteira_clientes", altura=420, chave="carteira",
        )
