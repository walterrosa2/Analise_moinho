"""
Custos — página deliberadamente exploratória.

Os seis conceitos coexistem e nenhum é eleito "o custo". A diferença entre
preço e custo é sempre "Margem Proxy — Base <CUSTO>".
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.metrics.registry import bases_custo
from src.repositories import costs

st.title("Custos")
f, base_custo = barra_lateral()
ui.aviso_custo()

BASES = bases_custo()
ROTULOS = {b[0]: b[1] for b in BASES}

modo = st.radio(
    "Modo de análise",
    ["Base selecionada", "Comparar todos os conceitos"],
    horizontal=True, key="custo_modo",
)

abas = st.tabs(["PMV × custo", "Por produto", "Dispersão entre conceitos", "Histórico do produto"])

# ---------------------------------------------------------------------
with abas[0]:
    if modo == "Base selecionada":
        serie = costs.serie_custo_pmv(f, base_custo)
        if serie.height == 0:
            st.warning("Nenhum dado no recorte.")
            st.stop()

        c = st.columns(4)
        ui.cartao(c[0], "PMV médio", ui.moeda(serie["pmv"].mean()) + "/t")
        ui.cartao(c[1], f"Custo médio ({ROTULOS[base_custo]})",
                  ui.moeda(serie["custo_por_ton"].mean()) + "/t")
        spread = float((serie["pmv"] - serie["custo_por_ton"]).mean() or 0)
        ui.cartao(c[2], "Spread médio", ui.moeda(spread) + "/t",
                  ajuda="PMV menos custo por tonelada. NÃO é margem contábil.")
        ui.cartao(c[3], f"Margem Proxy — {ROTULOS[base_custo]}",
                  ui.percentual(serie["margem_proxy_pct"].mean()))

        ui.secao(f"PMV × custo por tonelada — base {ROTULOS[base_custo]}")
        ui.grafico(ui.linha(serie, "ano_mes", ["pmv", "custo_por_ton"], altura=400),
                   serie, f"pmv_custo_{base_custo}")

        col1, col2 = st.columns(2)
        with col1:
            spread_df = serie.with_columns(
                (pl.col("pmv") - pl.col("custo_por_ton")).alias("spread_por_ton")
            )
            ui.grafico(ui.barra(spread_df, "ano_mes", "spread_por_ton",
                                "Spread PMV − custo (R$/t)", cor_por_sinal=True, altura=340),
                       spread_df.select("ano_mes", "spread_por_ton"), "spread")
        with col2:
            ui.grafico(ui.linha(serie, "ano_mes", "margem_proxy_pct",
                                "Margem proxy (%)", altura=340),
                       serie.select("ano_mes", "margem_proxy_pct"), "margem_pct")

        if serie["linhas_outlier"].sum():
            st.caption(
                f"⚠️ {ui.inteiro(serie['linhas_outlier'].sum())} linha(s) do recorte ficaram fora "
                "do cálculo por terem custo atípico na origem — valores até 7.000× a mediana do "
                "próprio produto (Q-15). O dado bruto permanece intacto no banco."
            )
    else:
        comp = costs.comparar_bases(f)
        if comp.height == 0:
            st.warning("Nenhum dado no recorte.")
            st.stop()

        ui.secao("Todos os conceitos de custo, lado a lado (R$/t)")
        colunas = ["pmv"] + [b[0] for b in BASES]
        ui.grafico(ui.linha(comp, "ano_mes", colunas, altura=460), comp, "comparar_custos")

        medias = pl.DataFrame({
            "Conceito": ["PMV"] + [b[1] for b in BASES],
            "Média R$/t": [float(comp["pmv"].mean() or 0)]
                          + [float(comp[b[0]].mean() or 0) for b in BASES],
        }).with_columns(
            (100 * (pl.col("Média R$/t") / float(comp["pmv"].mean() or 1) - 1)).round(1)
            .alias("vs PMV %")
        )
        col1, col2 = st.columns([2, 3])
        with col1:
            ui.tabela(medias, "medias_conceitos", altura=300, chave="medias")
        with col2:
            ui.grafico(ui.barra(medias.tail(len(BASES)), "Conceito", "Média R$/t",
                                "Custo médio por conceito (R$/t)", altura=300),
                       medias.tail(len(BASES)), "conceitos_media")

        st.caption(
            "A distância entre os conceitos é a medida de quanto a escolha da base muda o "
            "resultado — e de quão urgente é a homologação pela Controladoria."
        )

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao(f"Produtos — base {ROTULOS[base_custo]}")
    prod = costs.por_produto(f, base_custo, limite=120)
    if prod.height:
        ui.tabela(
            prod.select("descrprod", "classificacao", "unidade_produto", "ton", "quantidade",
                        "preco_unitario_medio", "custo_unitario_medio", "pmv", "custo_por_ton",
                        "margem_proxy", "margem_proxy_pct", "receita", "linhas_outlier"),
            f"custos_produto_{base_custo}", altura=420, chave="custo_prod",
        )
        col1, col2 = st.columns(2)
        with col1:
            ui.grafico(
                ui.dispersao(prod, "custo_por_ton", "pmv", tamanho="receita",
                             cor="margem_proxy_pct",
                             titulo="Custo × PMV por produto (R$/t)", altura=440),
                prod, "custo_pmv_produto",
            )
        with col2:
            piores = prod.filter(pl.col("margem_proxy_pct").is_not_null()) \
                         .sort("margem_proxy_pct").head(20)
            ui.grafico(ui.barra(piores, "descrprod", "margem_proxy_pct",
                                "Menores margens proxy (%)", horizontal=True,
                                cor_por_sinal=True, altura=440),
                       piores, "menores_margens")

        st.caption(
            "O custo da origem está na **unidade de venda** (FD, SC, CX, KG, PT), não por "
            "tonelada — confirmado comparando `CUSGER` com `VLRUNIT` (Q-15). "
            "`custo_por_ton` é derivado: `SUM(QTD × custo) / SUM(TONLIQ)`."
        )

    ui.secao("Custo subindo mais que o preço")
    evol = costs.evolucao_custo_pmv_produto(f, base_custo)
    if evol.height:
        criticos = evol.filter(
            pl.col("var_custo_pct").is_not_null() & pl.col("var_pmv_pct").is_not_null()
            & (pl.col("var_custo_pct") > pl.col("var_pmv_pct"))
        ).sort(pl.col("var_custo_pct") - pl.col("var_pmv_pct"), descending=True)
        if criticos.height:
            st.warning(
                f"**{criticos.height} produto(s)** tiveram alta de custo maior que a de preço "
                "entre a primeira e a segunda metade do período filtrado.",
                icon="📈",
            )
            ui.tabela(
                criticos.select("descrprod", "pmv_inicio", "pmv_fim", "var_pmv_pct",
                                "custo_inicio", "custo_fim", "var_custo_pct", "receita"),
                "custo_acima_pmv", altura=360, chave="custo_pmv",
            )
        else:
            st.success("Nenhum produto com custo subindo acima do preço neste recorte.")

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao(
        "Dispersão entre os conceitos de custo",
        "Quanto maior a amplitude, mais a escolha da base altera a conclusão sobre o produto.",
    )
    disp = costs.dispersao_entre_bases(f, limite=80)
    if disp.height:
        ui.tabela(
            disp.select(["descrprod", "classificacao"] + [b[0] for b in BASES]
                        + ["custo_minimo", "custo_maximo", "amplitude", "amplitude_pct", "receita"]),
            "dispersao_conceitos", altura=440, chave="disp_custo",
        )
        ui.grafico(ui.barra(disp.head(25), "descrprod", "amplitude_pct",
                            "Amplitude entre o maior e o menor conceito (%)",
                            horizontal=True, altura=520),
                   disp.head(25), "amplitude_custos")

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao("Histórico completo de um produto")
    prod = costs.por_produto(f, base_custo, limite=200)
    if prod.height:
        escolhido = st.selectbox(
            "Produto", prod["descrprod"].to_list(), key="hist_prod",
        )
        linha = prod.filter(pl.col("descrprod") == escolhido)
        if linha.height:
            hist = costs.custo_historico_produto(int(linha["codprod"][0]))
            if hist.height:
                ui.grafico(
                    ui.linha(hist, "ano_mes", [b[0] for b in BASES],
                             f"Evolução dos seis conceitos — {escolhido}", altura=440),
                    hist, f"historico_{linha['codprod'][0]}",
                )
                ui.tabela(hist, f"custo_historico_{linha['codprod'][0]}",
                          altura=340, chave="hist")
