"""
Gestão Diária e Mix.

Responde à pergunta do projeto: como as curvas de crescimento por classificação
se comportam e como o mix está se distribuindo.
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.db.engine import read_sql
from src.repositories import sales
from src.repositories.filters import Filtros

st.title("Gestão Diária e Mix")
f, base_custo = barra_lateral()


@st.cache_data(ttl=600, show_spinner=False)
def _serie_cla(chave: str, filtros: dict) -> pl.DataFrame:
    return sales.serie_por_dimensao(Filtros(**filtros), "classificacao", top_n=10)


@st.cache_data(ttl=600, show_spinner=False)
def _gestao_161() -> pl.DataFrame:
    return read_sql(
        """
        SELECT ano, mes, ano_mes, tipo, cod_cla, desc_cla, valor, tonelada, pc_medio,
               perc_ating_vlr, perc_ating_ton, markup
        FROM analytics.fact_gestao_diaria ORDER BY ano_mes, tipo, desc_cla
        """
    )


assinatura = repr(f.__dict__)
serie = _serie_cla(assinatura, f.__dict__)
g161 = _gestao_161()

if serie.height == 0:
    st.warning("Nenhum dado para o recorte selecionado.")
    st.stop()

abas = st.tabs([
    "Evolução por classificação", "Mix", "Crescimento e decomposição",
    "Orçado × realizado", "Heatmap",
])

# ---------------------------------------------------------------------
with abas[0]:
    metrica = st.radio(
        "Métrica", ["receita_liquida", "ton_liquida", "pmv"],
        format_func=lambda m: {"receita_liquida": "Receita líquida",
                               "ton_liquida": "Toneladas", "pmv": "PMV (R$/t)"}[m],
        horizontal=True, key="mix_metrica",
    )
    ui.grafico(ui.linha(serie, "ano_mes", metrica, cor="rotulo", altura=420),
               serie, f"evolucao_{metrica}")

    col1, col2 = st.columns(2)
    with col1:
        ui.secao("Receita por classificação")
        ui.grafico(ui.barras_empilhadas(serie, "ano_mes", "receita_liquida", "rotulo", altura=340),
                   serie.select("ano_mes", "rotulo", "receita_liquida"), "receita_classificacao")
    with col2:
        ui.secao("Toneladas por classificação")
        ui.grafico(ui.barras_empilhadas(serie, "ano_mes", "ton_liquida", "rotulo", altura=340),
                   serie.select("ano_mes", "rotulo", "ton_liquida"), "ton_classificacao")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Evolução do mix (100% empilhado)",
             "Mostra a redistribuição da participação, independentemente do crescimento total.")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Participação em VOLUME")
        ui.grafico(ui.area_empilhada(serie, "ano_mes", "ton_liquida", "rotulo",
                                     percentual_100=True, altura=360),
                   serie.select("ano_mes", "rotulo", "ton_liquida"), "mix_volume")
    with col2:
        st.caption("Participação em RECEITA")
        ui.grafico(ui.area_empilhada(serie, "ano_mes", "receita_liquida", "rotulo",
                                     percentual_100=True, altura=360),
                   serie.select("ano_mes", "rotulo", "receita_liquida"), "mix_receita")

    ui.secao("Alteração de mix entre dois períodos")
    periodos = serie["ano_mes"].unique().sort().to_list()
    c1, c2, c3, c4 = st.columns(4)
    a_ini = c1.selectbox("Período A — de", periodos, index=0, key="mixa1")
    a_fim = c2.selectbox("A — até", periodos, index=min(11, len(periodos) - 1), key="mixa2")
    b_ini = c3.selectbox("Período B — de", periodos, index=max(0, len(periodos) - 12), key="mixb1")
    b_fim = c4.selectbox("B — até", periodos, index=len(periodos) - 1, key="mixb2")

    comp = sales.comparar_periodos(f, "classificacao", (a_ini, a_fim), (b_ini, b_fim))
    if comp.height:
        tot_a = float(comp["ton_a"].sum() or 0) or 1
        tot_b = float(comp["ton_b"].sum() or 0) or 1
        mix = comp.with_columns(
            (100 * pl.col("ton_a") / tot_a).round(2).alias("share_A_pct"),
            (100 * pl.col("ton_b") / tot_b).round(2).alias("share_B_pct"),
        ).with_columns(
            (pl.col("share_B_pct") - pl.col("share_A_pct")).round(2).alias("delta_share_pp")
        ).select("rotulo", "ton_a", "ton_b", "share_A_pct", "share_B_pct", "delta_share_pp")
        col1, col2 = st.columns([1, 1])
        with col1:
            ui.grafico(ui.barra(mix, "rotulo", "delta_share_pp",
                                "Variação de participação (pontos percentuais)",
                                cor_por_sinal=True, altura=320), mix, "delta_mix")
        with col2:
            ui.tabela(mix, "alteracao_mix", altura=320, chave="mix_delta")

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao("Decomposição do crescimento",
             "Separa o quanto da variação veio de volume e o quanto veio de preço.")
    periodos = serie["ano_mes"].unique().sort().to_list()
    c1, c2, c3, c4 = st.columns(4)
    a_ini = c1.selectbox("Período A — de", periodos, index=0, key="cra1")
    a_fim = c2.selectbox("A — até", periodos, index=min(11, len(periodos) - 1), key="cra2")
    b_ini = c3.selectbox("Período B — de", periodos, index=max(0, len(periodos) - 12), key="crb1")
    b_fim = c4.selectbox("B — até", periodos, index=len(periodos) - 1, key="crb2")

    dimensao = st.selectbox(
        "Decompor por", ["classificacao", "produto", "regiao", "vendedor", "cliente", "uf"],
        format_func=lambda d: d.capitalize(), key="cr_dim",
    )
    comp = sales.comparar_periodos(f, dimensao, (a_ini, a_fim), (b_ini, b_fim))
    if comp.height:
        topo = comp.head(15)
        ui.grafico(
            ui.waterfall(topo["rotulo"].to_list(),
                         [float(v or 0) for v in topo["variacao"].to_list()],
                         "Contribuição para a variação de receita", altura=420),
            comp, f"waterfall_{dimensao}",
        )
        col1, col2 = st.columns(2)
        with col1:
            ui.grafico(ui.barra(topo, "rotulo", "efeito_volume",
                                "Efeito volume (R$)", horizontal=True,
                                cor_por_sinal=True, altura=380),
                       topo.select("rotulo", "efeito_volume"), "efeito_volume")
        with col2:
            ui.grafico(ui.barra(topo, "rotulo", "efeito_preco",
                                "Efeito preço (R$)", horizontal=True,
                                cor_por_sinal=True, altura=380),
                       topo.select("rotulo", "efeito_preco"), "efeito_preco")

        ui.tabela(
            comp.select("rotulo", "valor_a", "valor_b", "variacao", "variacao_pct",
                        "contribuicao_pct", "efeito_volume", "efeito_preco",
                        "ton_a", "ton_b", "pmv_a", "pmv_b"),
            f"decomposicao_{dimensao}", altura=380, chave="decomp",
        )

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao(
        "Orçado × realizado (fonte: relatório 161)",
        "Camada gerencial agregada. Usada para validação e tendência, nunca como base causal.",
    )
    if g161.height == 0:
        st.info("Relatório 161 não carregado.")
    else:
        anos = sorted(g161["ano"].unique().to_list())
        ano = st.selectbox("Ano", anos, index=len(anos) - 1, key="orc_ano")
        base = g161.filter(pl.col("ano") == ano)

        pivot = base.filter(pl.col("tipo").is_in(["ORÇADO", "REALIZADO", "REAL.-DEVOLUÇÃO"])).pivot(
            values="valor", index=["ano_mes", "desc_cla"], on="tipo", aggregate_function="sum"
        ).fill_null(0)

        if "ORÇADO" in pivot.columns and "REALIZADO" in pivot.columns:
            pivot = pivot.with_columns(
                (pl.col("REALIZADO") - pl.col("ORÇADO")).alias("desvio"),
                pl.when(pl.col("ORÇADO") != 0)
                .then(100 * pl.col("REALIZADO") / pl.col("ORÇADO"))
                .alias("atingimento_pct"),
            )
            resumo = pivot.group_by("ano_mes").agg(
                pl.col("ORÇADO").sum(), pl.col("REALIZADO").sum()
            ).sort("ano_mes")
            fig = ui.barra(resumo, "ano_mes", "ORÇADO", "Orçado × realizado (R$)", altura=380)
            fig.data[0].name = "Orçado"
            fig.add_bar(x=resumo["ano_mes"].to_list(), y=resumo["REALIZADO"].to_list(),
                        name="Realizado", marker_color=ui.CORES[2])
            fig.update_layout(barmode="group", showlegend=True)
            ui.grafico(fig, resumo, "orcado_realizado")
            ui.tabela(pivot.sort(["ano_mes", "desc_cla"]), f"orcado_realizado_{ano}",
                      altura=380, chave="orc")
        else:
            st.info("Tipos ORÇADO/REALIZADO não disponíveis para este ano.")

        st.caption(
            "A coluna `ORC/ANT` do arquivo *161 OUTROS* **não** é usada aqui: sua semântica "
            "(Orçado ou Ano Anterior) ainda não foi validada pelo negócio (Q-03)."
        )

# ---------------------------------------------------------------------
with abas[4]:
    ui.secao("Heatmap mês × classificação")
    metrica_hm = st.radio(
        "Métrica", ["receita_liquida", "ton_liquida", "pmv"],
        format_func=lambda m: {"receita_liquida": "Receita", "ton_liquida": "Toneladas",
                               "pmv": "PMV"}[m],
        horizontal=True, key="hm_metrica",
    )
    ui.grafico(ui.heatmap(serie, "ano_mes", "rotulo", metrica_hm, altura=380),
               serie, f"heatmap_{metrica_hm}")

    ui.secao("Crescimento ano a ano (YoY)")
    yoy = serie.with_columns(pl.col("ano_mes").str.slice(0, 4).alias("ano")).group_by(
        ["ano", "rotulo"]
    ).agg(
        pl.col("receita_liquida").sum(), pl.col("ton_liquida").sum()
    ).sort(["rotulo", "ano"]).with_columns(
        (100 * (pl.col("receita_liquida") / pl.col("receita_liquida").shift(1) - 1))
        .over("rotulo").round(2).alias("yoy_receita_pct"),
        (100 * (pl.col("ton_liquida") / pl.col("ton_liquida").shift(1) - 1))
        .over("rotulo").round(2).alias("yoy_ton_pct"),
    )
    ui.tabela(yoy, "yoy_classificacao", altura=340, chave="yoy")
