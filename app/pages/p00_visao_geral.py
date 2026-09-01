"""Visão Geral — ponto de entrada do consultor."""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.insights import engine as insights_engine
from src.repositories import sales
from src.repositories.filters import Filtros

st.title("Visão Geral")
f, base_custo = barra_lateral()


@st.cache_data(ttl=600, show_spinner="Consultando…")
def _kpis(chave: str, filtros: dict, base: str) -> dict:
    return sales.kpis_gerais(Filtros(**filtros), base)


@st.cache_data(ttl=600, show_spinner=False)
def _serie(chave: str, filtros: dict, base: str) -> pl.DataFrame:
    return sales.serie_mensal(Filtros(**filtros), base)


@st.cache_data(ttl=600, show_spinner=False)
def _dim(chave: str, filtros: dict, dim: str, base: str, limite: int) -> pl.DataFrame:
    return sales.por_dimensao(Filtros(**filtros), dim, base, limite)


assinatura = repr(f.__dict__) + base_custo
kpis = _kpis(assinatura, f.__dict__, base_custo)
serie = _serie(assinatura, f.__dict__, base_custo)

if serie.height == 0:
    st.warning("Nenhum dado para o recorte selecionado. Ajuste os filtros na barra lateral.")
    st.stop()

# --- Período comparativo: mesma duração, imediatamente anterior -------
periodos = serie["ano_mes"].to_list()
n = len(periodos)
periodo_b = (periodos[0], periodos[-1])


def _meses_antes(ano_mes: str, k: int) -> str:
    ano, mes = int(ano_mes[:4]), int(ano_mes[5:7])
    total = ano * 12 + (mes - 1) - k
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


periodo_a = (_meses_antes(periodos[0], n), _meses_antes(periodos[0], 1))

serie_a = _serie(repr({**f.__dict__, "periodo_inicio": periodo_a[0], "periodo_fim": periodo_a[1]}),
                 {**f.__dict__, "periodo_inicio": periodo_a[0], "periodo_fim": periodo_a[1]},
                 base_custo)


def _delta(coluna: str) -> str | None:
    if serie_a.height == 0 or coluna not in serie_a.columns:
        return None
    return ui.variacao_texto(float(serie[coluna].sum() or 0), float(serie_a[coluna].sum() or 0))


st.caption(
    f"Recorte: **{periodo_b[0]} a {periodo_b[1]}** · comparação com **{periodo_a[0]} a {periodo_a[1]}** "
    f"(mesma duração) · base de custo **{base_custo.upper()}**"
)

# --- Cartões ----------------------------------------------------------
c = st.columns(5)
ui.cartao(c[0], "Receita líquida", ui.moeda(kpis["receita_liquida"], compacto=True),
          _delta("receita_liquida"), "Soma de VLRTOT; devoluções já vêm negativas.")
ui.cartao(c[1], "Volume líquido", f"{ui.numero(kpis['ton_liquida'], 0)} t",
          _delta("ton_liquida"), "Tonelagem líquida de devolução.")
ui.cartao(c[2], "PMV", ui.moeda(kpis["pmv"]) + "/t",
          _delta("pmv"), "Exclui bonificação e amostra (tonelada sem receita).")
ui.cartao(c[3], "Clientes ativos", ui.inteiro(kpis["clientes"]),
          _delta("clientes"), "Clientes distintos com movimento no período.")
ui.cartao(c[4], "Devoluções", ui.moeda(kpis["devolucoes"], compacto=True),
          ajuda="Valor negativo, como consta na origem.")

c = st.columns(5)
ui.cartao(c[0], "Documentos", ui.inteiro(kpis["documentos"]))
ui.cartao(c[1], "Desconto", ui.moeda(kpis["desconto"], compacto=True))
ui.cartao(c[2], "Frete alocado", ui.moeda(kpis["frete"], compacto=True),
          ajuda="Somente CT-e vinculados a nota de venda.")
ui.cartao(c[3], f"Custo ({base_custo.upper()})", ui.moeda(kpis["custo"], compacto=True))
ui.cartao(c[4], f"Margem Proxy — {base_custo.upper()}",
          ui.percentual(kpis["margem_proxy_pct"]),
          ajuda="NÃO é margem contábil. Conceito de custo não homologado.")

if kpis.get("linhas_custo_outlier", 0):
    st.caption(
        f"⚠️ {ui.inteiro(kpis['linhas_custo_outlier'])} de {ui.inteiro(kpis['linhas'])} linhas "
        f"ficaram fora do cálculo de custo por terem valor atípico na origem (Q-15). "
        f"A margem compara receita e custo da mesma população de linhas."
    )

st.divider()

# --- Séries -----------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    ui.secao("Receita e volume")
    fig = ui.linha(serie, "ano_mes", ["receita_liquida"], altura=320)
    fig.add_bar(x=serie["ano_mes"].to_list(), y=serie["ton_liquida"].to_list(),
                name="Toneladas", yaxis="y2", marker_color=ui.CORES[1], opacity=0.45)
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False, title="t"))
    ui.grafico(fig, serie.select("ano_mes", "receita_liquida", "ton_liquida"), "receita_volume")

with col2:
    ui.secao("PMV mensal")
    ui.grafico(ui.linha(serie, "ano_mes", "pmv", altura=320),
               serie.select("ano_mes", "pmv"), "pmv")

col1, col2 = st.columns(2)
with col1:
    ui.secao("Mix por classificação (participação em volume)")
    mix = _dim(assinatura + "cla", f.__dict__, "classificacao", base_custo, 0) if False else None
    serie_cla = sales.serie_por_dimensao(f, "classificacao", top_n=10)
    if serie_cla.height:
        ui.grafico(
            ui.area_empilhada(serie_cla, "ano_mes", "ton_liquida", "rotulo",
                              percentual_100=True, altura=340),
            serie_cla, "mix_volume",
        )

with col2:
    ui.secao("Maiores variações vs. período anterior")
    comp = sales.comparar_periodos(f, "classificacao", periodo_a, periodo_b)
    if comp.height:
        ui.grafico(
            ui.waterfall(comp["rotulo"].to_list(),
                         [float(v or 0) for v in comp["variacao"].to_list()],
                         altura=340),
            comp.select("rotulo", "valor_a", "valor_b", "variacao", "variacao_pct",
                        "efeito_volume", "efeito_preco"),
            "variacao_classificacao",
        )

st.divider()

# --- Insights ---------------------------------------------------------
ui.secao(
    "Insights automáticos",
    "Regras quantitativas determinísticas — sem IA. Cada frase tem a tabela que a originou.",
)

with st.spinner("Analisando…"):
    lista = insights_engine.gerar(f, periodo_a, periodo_b, base_custo)

if not lista:
    st.info("Nenhum padrão relevante encontrado no recorte atual.")
else:
    for ins in lista[:12]:
        with st.expander(f"{ins.icone} **{ins.titulo}**", expanded=False):
            ui.texto_seguro(ins.descricao)
            meta = []
            if ins.periodo:
                meta.append(f"Período: {ins.periodo}")
            if ins.metrica:
                meta.append(f"Métrica: `{ins.metrica}`")
            meta.append(f"Categoria: {ins.categoria}")
            st.caption(" · ".join(meta))
            if ins.evidencia is not None and ins.evidencia.height:
                st.markdown("**Ver evidência**")
                ui.tabela(ins.evidencia, f"evidencia_{ins.id}", altura=260, chave=ins.id)
