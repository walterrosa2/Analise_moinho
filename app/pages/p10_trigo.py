"""
Trigo × Custo × PMV — análise exploratória.

Não há granularidade de fornecedor, origem, lote, qualidade, frete de entrada
ou rendimento de moagem. Portanto: correlação aqui NUNCA é causalidade.
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.db.engine import read_sql

st.title("Trigo × Custo × PMV")
barra_lateral()
ui.aviso_correlacao()


@st.cache_data(ttl=600, show_spinner=False)
def _serie() -> pl.DataFrame:
    return read_sql(
        """
        SELECT ano_mes, trigo_preco_medio, trigo_ton_comprada, trigo_ton_estoque,
               trigo_estoque_preco_medio, pmv, cusmed_por_ton, cusger_por_ton,
               cusvariavel_por_ton, ton_liquida, receita_liquida
        FROM analytics.mv_trigo_cost_month
        WHERE ano_mes IS NOT NULL
        ORDER BY ano_mes
        """
    )


serie = _serie().filter(pl.col("trigo_preco_medio").is_not_null())
if serie.height == 0:
    st.warning("Sem dados de compra de trigo carregados.")
    st.stop()

st.caption(
    f"Compra de trigo cobre **{serie['ano_mes'].min()} a {serie['ano_mes'].max()}** "
    f"({serie.height} meses). O estoque tem cobertura menor. "
    "Períodos diferentes das vendas: a análise usa só a interseção."
)

SERIES = {
    "trigo_preco_medio": "Preço médio do trigo (R$/t)",
    "pmv": "PMV (R$/t)",
    "cusmed_por_ton": "CUSMED por tonelada",
    "cusger_por_ton": "CUSGER por tonelada",
    "cusvariavel_por_ton": "CUSVARIAVEL por tonelada",
    "trigo_ton_estoque": "Estoque de trigo (t)",
    "trigo_ton_comprada": "Trigo comprado (t)",
}

abas = st.tabs(["Séries", "Base 100", "Correlação e defasagem"])

# ---------------------------------------------------------------------
with abas[0]:
    escolhidas = st.multiselect(
        "Séries", list(SERIES), default=["trigo_preco_medio", "pmv", "cusger_por_ton"],
        format_func=lambda k: SERIES[k], key="trigo_series",
    )
    if escolhidas:
        ui.grafico(ui.linha(serie, "ano_mes", escolhidas, altura=460), serie, "series_trigo")

    col1, col2 = st.columns(2)
    with col1:
        ui.secao("Compra de trigo")
        ui.grafico(ui.barra(serie, "ano_mes", "trigo_ton_comprada", altura=320),
                   serie.select("ano_mes", "trigo_ton_comprada"), "compra_trigo")
    with col2:
        estoque = serie.filter(pl.col("trigo_ton_estoque").is_not_null())
        if estoque.height:
            ui.secao("Estoque de trigo")
            ui.grafico(ui.linha(estoque, "ano_mes",
                                ["trigo_ton_estoque"], altura=320),
                       estoque.select("ano_mes", "trigo_ton_estoque"), "estoque_trigo")

    ui.tabela(serie, "trigo_custo_pmv", altura=340, chave="trigo_tab")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Normalização base 100", "Todas as séries partem de 100 no primeiro mês com dado.")
    escolhidas = st.multiselect(
        "Séries", list(SERIES), default=["trigo_preco_medio", "pmv", "cusger_por_ton"],
        format_func=lambda k: SERIES[k], key="trigo_b100",
    )
    if escolhidas:
        base = serie.select(["ano_mes"] + escolhidas).drop_nulls()
        if base.height:
            normalizado = base.with_columns([
                (100 * pl.col(c) / pl.col(c).first()).alias(c) for c in escolhidas
            ])
            ui.grafico(ui.linha(normalizado, "ano_mes", escolhidas, altura=460),
                       normalizado, "base_100")
            st.caption(
                "Séries que sobem juntas indicam repasse; divergência indica compressão ou "
                "expansão de spread. Nenhuma das duas leituras prova causalidade."
            )

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao(
        "Correlação com defasagem de 0 a 6 meses",
        "Testa se o preço do trigo aparece no custo ou no PMV com atraso.",
    )
    c1, c2 = st.columns(2)
    origem = c1.selectbox("Série de origem", list(SERIES), index=0,
                          format_func=lambda k: SERIES[k], key="corr_x")
    destino = c2.selectbox("Série de destino", list(SERIES), index=3,
                           format_func=lambda k: SERIES[k], key="corr_y")

    base = serie.select("ano_mes", origem, destino).drop_nulls()
    if base.height < 6:
        st.info("Dados insuficientes para calcular correlação (mínimo de 6 meses em comum).")
    else:
        linhas = []
        for lag in range(7):
            deslocado = base.with_columns(pl.col(origem).shift(lag).alias("_x")).drop_nulls()
            if deslocado.height >= 4:
                corr = deslocado.select(pl.corr("_x", destino)).item()
                linhas.append({"defasagem_meses": lag, "correlacao": corr,
                               "meses_comparados": deslocado.height})
        if linhas:
            corr_df = pl.DataFrame(linhas)
            melhor = corr_df.sort(pl.col("correlacao").abs(), descending=True).head(1).to_dicts()[0]

            col1, col2 = st.columns([3, 2])
            with col1:
                ui.grafico(ui.barra(corr_df, "defasagem_meses", "correlacao",
                                    f"Correlação: {SERIES[origem]} → {SERIES[destino]}",
                                    cor_por_sinal=True, altura=360),
                           corr_df, "correlacao_defasagem")
            with col2:
                ui.cartao(
                    col2,
                    "Maior correlação (em módulo)",
                    f"{melhor['correlacao']:.3f}".replace(".", ","),
                    f"defasagem de {melhor['defasagem_meses']} mês(es)",
                    ajuda="Maior associação linear encontrada entre as séries. Não estabelece causalidade.",
                )
                st.caption(
                    f"Calculada sobre {melhor['meses_comparados']} meses. "
                    "Correlação forte sugere onde investigar — **não** estabelece causa. "
                    "Sem dados de rendimento de moagem e qualidade do trigo, a relação "
                    "causal permanece fora do alcance desta base."
                )
                ui.tabela(corr_df, "correlacao", altura=240, chave="corr")

            ui.grafico(
                ui.dispersao(base, origem, destino, titulo="Dispersão (defasagem 0)", altura=420),
                base, "dispersao_trigo",
            )
