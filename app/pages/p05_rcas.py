"""
RCAs e Vendedores.

Objetivo (§22): separar percepção de desempenho mensurável.

Regra de linguagem: a plataforma nunca rotula "RCA improdutivo". Diz
"performance inferior ao grupo comparável" — porque a base não contém
esforço, potencial de carteira nem contexto de território.
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.repositories import sales

st.title("RCAs e Vendedores")
f, base_custo = barra_lateral()

st.info(
    "A base mede **resultado**, não esforço nem potencial de carteira. Diferença de performance "
    "aqui é um ponto de partida para investigação — não um veredito sobre a pessoa.",
    icon="ℹ️",
)

vend = sales.por_dimensao(f, "vendedor", base_custo, limite=100)
if vend.height == 0:
    st.warning("Nenhum dado para o recorte selecionado.")
    st.stop()

papel = sales.por_dimensao(f, "papel", base_custo)
total_receita = float(vend["receita_liquida"].sum() or 0)

c = st.columns(5)
ui.cartao(c[0], "Vendedores com movimento", ui.inteiro(vend.height))
ui.cartao(c[1], "Receita total", ui.moeda(total_receita, compacto=True))
maior = vend.head(1)
if maior.height:
    ui.cartao(c[2], "Maior vendedor",
              ui.percentual(100 * float(maior["receita_liquida"][0] or 0) / total_receita
                            if total_receita else 0),
              ajuda=str(maior["rotulo"][0]))
top5 = float(vend.head(5)["receita_liquida"].sum() or 0)
ui.cartao(c[3], "Top 5", ui.percentual(100 * top5 / total_receita if total_receita else 0))
ui.cartao(c[4], "Clientes (mediana por vendedor)", ui.inteiro(vend["clientes"].median()))

abas = st.tabs(["Scorecard", "Quadrante", "Evolução", "Cruzamentos", "Concentração da carteira"])

# ---------------------------------------------------------------------
with abas[0]:
    ui.secao("Scorecard por vendedor")
    score = vend.select(
        pl.col("rotulo").alias("Vendedor"),
        pl.col("receita_liquida").alias("Receita"),
        pl.col("devolucoes").alias("Devoluções"),
        pl.col("ton_liquida").alias("Toneladas"),
        pl.col("pmv").alias("PMV"),
        pl.col("clientes").alias("Clientes"),
        pl.col("produtos").alias("Produtos"),
        pl.col("documentos").alias("Documentos"),
        pl.col("desconto").alias("Desconto"),
        pl.col("comissao").alias("Comissão"),
        pl.col("frete").alias("Frete"),
        pl.col("margem_proxy_pct").alias(f"Margem proxy % ({base_custo.upper()})"),
    )
    ui.tabela(score, "scorecard_vendedores", altura=460, chave="score")

    col1, col2 = st.columns(2)
    with col1:
        ui.grafico(ui.barra(vend.head(20), "rotulo", "receita_liquida",
                            "Ranking por receita", horizontal=True, altura=460),
                   vend.head(20), "ranking_receita")
    with col2:
        ui.grafico(ui.pareto(vend.head(25), "rotulo", "receita_liquida",
                             "Pareto de vendedores", altura=460),
                   vend.head(25), "pareto_vendedores")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao(
        "Quadrante de performance",
        "Eixos configuráveis. Tamanho da bolha = receita; cor = margem proxy.",
    )
    opcoes = {
        "ton_liquida": "Toneladas", "clientes": "Clientes", "pmv": "PMV",
        "receita_liquida": "Receita", "documentos": "Documentos",
        "desconto": "Desconto", "frete_por_ton": "Frete R$/t",
        "margem_proxy_pct": "Margem proxy %",
    }
    c1, c2 = st.columns(2)
    eixo_x = c1.selectbox("Eixo X", list(opcoes), index=1,
                          format_func=lambda k: opcoes[k], key="q_x")
    eixo_y = c2.selectbox("Eixo Y", list(opcoes), index=0,
                          format_func=lambda k: opcoes[k], key="q_y")

    dados = vend.filter(pl.col(eixo_x).is_not_null() & pl.col(eixo_y).is_not_null())
    if dados.height:
        fig = ui.dispersao(dados, eixo_x, eixo_y, tamanho="receita_liquida",
                           cor="margem_proxy_pct", rotulo="rotulo",
                           titulo=f"{opcoes[eixo_y]} × {opcoes[eixo_x]}", altura=520)
        mx = float(dados[eixo_x].median() or 0)
        my = float(dados[eixo_y].median() or 0)
        fig.add_vline(x=mx, line_dash="dot", line_color="rgba(200,200,200,0.4)")
        fig.add_hline(y=my, line_dash="dot", line_color="rgba(200,200,200,0.4)")
        ui.grafico(fig, dados, "quadrante_vendedores")
        st.caption(
            f"Linhas tracejadas = mediana do grupo ({opcoes[eixo_x]}: {ui.numero(mx)}, "
            f"{opcoes[eixo_y]}: {ui.numero(my)}). Estar abaixo da mediana significa "
            "**performance inferior ao grupo comparável** neste recorte — não é um julgamento."
        )

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao("Evolução temporal")
    serie = sales.serie_por_dimensao(f, "vendedor", top_n=12)
    if serie.height:
        metrica = st.radio(
            "Métrica", ["receita_liquida", "ton_liquida", "pmv", "clientes"],
            format_func=lambda m: m.replace("_", " ").title(),
            horizontal=True, key="rca_metrica",
        )
        ui.grafico(ui.linha(serie, "ano_mes", metrica, cor="rotulo", altura=440),
                   serie, f"evolucao_vendedor_{metrica}")
        ui.grafico(ui.heatmap(serie, "ano_mes", "rotulo", metrica,
                              f"Heatmap vendedor × mês ({metrica})", altura=460),
                   serie.select("ano_mes", "rotulo", metrica), "heatmap_vendedor")

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao("Papel analítico")
    if papel.height:
        ui.tabela(papel.select("rotulo", "receita_liquida", "ton_liquida", "pmv",
                               "clientes", "documentos", "margem_proxy_pct"),
                  "por_papel", altura=220, chave="papel_tab")
        st.caption(
            "`NAO_CLASSIFICADO` reúne códigos que aparentam ser canais de venda, não pessoas. "
            "Contá-los como RCA distorceria qualquer ranking de produtividade (Q-01)."
        )

    ui.secao("Vendedor × classificação de produto")
    lista_vend = vend["rotulo"].to_list()
    escolhido = st.selectbox("Vendedor", lista_vend, key="rca_prod_vend")
    linha = vend.filter(pl.col("rotulo") == escolhido)
    if linha.height:
        from src.repositories.filters import Filtros

        f_vend = Filtros(**{**f.__dict__, "vendedores": [int(linha["chave"][0])]})
        col1, col2 = st.columns(2)
        with col1:
            por_cla = sales.por_dimensao(f_vend, "classificacao", base_custo)
            if por_cla.height:
                ui.grafico(ui.barra(por_cla, "rotulo", "receita_liquida",
                                    "Mix do vendedor", altura=340), por_cla, "mix_vendedor")
        with col2:
            por_cli = sales.por_dimensao(f_vend, "cliente", base_custo, limite=15)
            if por_cli.height:
                ui.grafico(ui.barra(por_cli, "rotulo", "receita_liquida",
                                    "Principais clientes", horizontal=True, altura=340),
                           por_cli, "clientes_vendedor")

# ---------------------------------------------------------------------
with abas[4]:
    ui.secao(
        "Dependência de poucos clientes",
        "Quanto da receita de cada vendedor vem dos seus maiores clientes.",
    )
    from src.db.engine import read_sql

    dep = read_sql(
        """
        WITH por_vend_cli AS (
            SELECT codvend, vendedor, codparc, parceiro, SUM(receita_liquida) AS receita
            FROM analytics.mv_sales_customer_month
            WHERE (CAST(:ini AS text) IS NULL OR ano_mes >= CAST(:ini AS text))
              AND (CAST(:fim AS text) IS NULL OR ano_mes <= CAST(:fim AS text))
            GROUP BY codvend, vendedor, codparc, parceiro
        ),
        ranqueado AS (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY codvend ORDER BY receita DESC) AS posicao,
                   SUM(receita) OVER (PARTITION BY codvend) AS receita_vendedor,
                   COUNT(*) OVER (PARTITION BY codvend) AS clientes_vendedor
            FROM por_vend_cli
        )
        SELECT vendedor,
               MAX(clientes_vendedor)   AS clientes,
               MAX(receita_vendedor)    AS receita_total,
               SUM(receita) FILTER (WHERE posicao = 1)  AS receita_maior_cliente,
               SUM(receita) FILTER (WHERE posicao <= 3) AS receita_top3,
               SUM(receita) FILTER (WHERE posicao <= 5) AS receita_top5,
               MAX(parceiro) FILTER (WHERE posicao = 1) AS maior_cliente
        FROM ranqueado
        GROUP BY vendedor
        HAVING MAX(receita_vendedor) > 0
        ORDER BY receita_total DESC
        """,
        {"ini": f.periodo_inicio, "fim": f.periodo_fim},
    )
    if dep.height:
        dep = dep.with_columns(
            (100 * pl.col("receita_maior_cliente") / pl.col("receita_total")).round(1)
            .alias("pct_maior_cliente"),
            (100 * pl.col("receita_top3") / pl.col("receita_total")).round(1).alias("pct_top3"),
            (100 * pl.col("receita_top5") / pl.col("receita_total")).round(1).alias("pct_top5"),
        ).sort("pct_top3", descending=True)
        ui.tabela(
            dep.select("vendedor", "clientes", "receita_total", "maior_cliente",
                       "pct_maior_cliente", "pct_top3", "pct_top5"),
            "dependencia_carteira", altura=420, chave="dep",
        )
        ui.grafico(ui.barra(dep.head(20), "vendedor", "pct_top3",
                            "% da receita nos 3 maiores clientes", horizontal=True, altura=440),
                   dep.head(20), "dependencia")
