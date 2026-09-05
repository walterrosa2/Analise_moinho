"""
Regional e Territorial — uma das páginas prioritárias.

Investiga a hipótese do projeto: "divisão territorial antiga e forte
concentração das grandes contas na liderança".

Regra estrutural: REGIÃO COMERCIAL (atribuição interna) e GEOGRAFIA REAL
DO CLIENTE são dimensões distintas e nunca se misturam.
"""
from __future__ import annotations

import plotly.graph_objects as go
import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.db.engine import read_sql
from src.repositories import sales

st.title("Regional e Territorial")
f, base_custo = barra_lateral()
ui.aviso_performance_interna()


@st.cache_data(ttl=600, show_spinner=False)
def _cobertura_territorial() -> pl.DataFrame:
    """Vendedores com movimento ausentes do mapa de região comercial (Q-10)."""
    return read_sql(
        """
        SELECT v.codvend, v.apelido, v.papel_analitico,
               COUNT(DISTINCT i.codparc)  AS clientes,
               COUNT(DISTINCT i.codreg)   AS regioes_atendidas,
               SUM(i.vlrtot)              AS receita
        FROM analytics.fact_venda_item i
        JOIN analytics.dim_vendedor v ON v.codvend = i.codvend
        GROUP BY v.codvend, v.apelido, v.papel_analitico
        ORDER BY receita DESC
        """
    )


st.info(
    "**Duas dimensões distintas nesta página:** *Região comercial* é a atribuição interna "
    "(`CODREG`); *UF / cidade* é a geografia real do cliente. Elas não são intercambiáveis.",
    icon="🧭",
)

abas = st.tabs([
    "Mapa e matriz regional", "Região comercial", "Concentração e cobertura", "Geografia real",
])

# ---------------------------------------------------------------------
with abas[0]:
    uf = sales.por_dimensao(f, "uf", base_custo)
    if uf.height == 0:
        st.warning("Nenhum dado para o recorte.")
        st.stop()

    metrica = st.radio(
        "Métrica no mapa",
        ["receita_liquida", "ton_liquida", "pmv", "clientes", "margem_proxy_pct"],
        format_func=lambda m: {"receita_liquida": "Receita", "ton_liquida": "Toneladas",
                               "pmv": "PMV", "clientes": "Clientes",
                               "margem_proxy_pct": f"Margem proxy % ({base_custo.upper()})"}[m],
        horizontal=True, key="reg_metrica",
    )

    col1, col2 = st.columns([3, 2])
    with col1:
        fig = go.Figure(go.Choropleth(
            geojson="https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson",
            locations=uf["rotulo"].to_list(),
            z=[float(v or 0) for v in uf[metrica].to_list()],
            featureidkey="properties.sigla",
            # Sem locationmode='geojson-id' o Plotly cai no default 'ISO-3' e
            # tenta casar 'MG' com codigo de pais: o mapa monta e fica vazio.
            locationmode="geojson-id",
            colorscale="Teal", marker_line_color="rgba(255,255,255,0.3)",
        ))
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(height=440, margin=dict(l=0, r=0, t=10, b=0),
                          paper_bgcolor="rgba(0,0,0,0)")
        ui.grafico(fig, uf.select("rotulo", metrica), f"mapa_uf_{metrica}")
        st.caption(
            "O mapa depende de um GeoJSON externo. Se não carregar (sem internet), "
            "use o ranking ao lado — os números são os mesmos."
        )
    with col2:
        ui.grafico(ui.barra(uf.head(15), "rotulo", metrica, "Ranking por UF",
                            horizontal=True, altura=440),
                   uf.head(15).select("rotulo", metrica), f"uf_{metrica}")

    ui.secao("Matriz regional",
             "Receita, volume, PMV, clientes, frete e margem proxy lado a lado.")
    matriz = sales.por_dimensao(f, "regiao", base_custo, limite=60)
    ui.tabela(
        matriz.select("rotulo", "receita_liquida", "ton_liquida", "pmv", "clientes",
                      "documentos", "produtos", "frete", "frete_por_ton",
                      "margem_proxy_pct", "desconto"),
        "matriz_regional", altura=420, chave="matriz_reg",
    )

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Evolução por região comercial")
    serie_reg = sales.serie_por_dimensao(f, "regiao", top_n=10)
    if serie_reg.height:
        metrica = st.radio(
            "Métrica", ["receita_liquida", "ton_liquida", "pmv", "clientes"],
            format_func=lambda m: m.replace("_", " ").title(),
            horizontal=True, key="reg_serie_metrica",
        )
        ui.grafico(ui.linha(serie_reg, "ano_mes", metrica, cor="rotulo", altura=400),
                   serie_reg, f"regiao_{metrica}")
        ui.grafico(ui.heatmap(serie_reg, "ano_mes", "rotulo", "receita_liquida",
                              "Heatmap região × mês (receita)", altura=420),
                   serie_reg.select("ano_mes", "rotulo", "receita_liquida"), "heatmap_regiao")

    ui.secao("Região comercial × RCA")
    cruzamento = read_sql(
        """
        SELECT COALESCE(r.regiao_comercial, '—') AS regiao,
               COALESCE(r.vendedor, '—')         AS vendedor,
               SUM(r.receita_liquida)            AS receita,
               SUM(r.ton_liquida)                AS toneladas,
               SUM(r.clientes)                   AS clientes
        FROM (
            SELECT s.ano_mes, c.regiao_comercial, s.vendedor,
                   s.receita_liquida, s.ton_liquida, s.clientes
            FROM analytics.mv_sales_seller_month s
            LEFT JOIN LATERAL (
                SELECT regiao_comercial FROM analytics.mv_sales_region_month rm
                WHERE rm.ano_mes = s.ano_mes LIMIT 1
            ) c ON TRUE
        ) r GROUP BY 1, 2 ORDER BY receita DESC LIMIT 200
        """
    )
    st.caption(
        "Cruzamento agregado a partir das views mensais. Para o cruzamento exato "
        "região × RCA no grão de item, use o Explorador."
    )

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao(
        "Concentração das grandes contas",
        "Compara a receita que passa por representante com a que é atendida diretamente "
        "pela liderança.",
    )
    papel = sales.por_dimensao(f, "papel", base_custo)
    if papel.height:
        total = float(papel["receita_liquida"].sum() or 0)
        cols = st.columns(len(papel))
        for i, r in enumerate(papel.iter_rows(named=True)):
            pct = 100 * (r["receita_liquida"] or 0) / total if total else 0
            ui.cartao(cols[i], r["rotulo"], ui.percentual(pct),
                      ajuda=f"{ui.moeda(r['receita_liquida'], compacto=True)} · "
                            f"{int(r['clientes'] or 0)} clientes")

        col1, col2 = st.columns(2)
        with col1:
            ui.grafico(ui.barra(papel, "rotulo", "receita_liquida",
                                "Receita por papel do vendedor", altura=340),
                       papel, "receita_papel")
        with col2:
            serie_papel = sales.serie_por_dimensao(f, "papel", top_n=6)
            if serie_papel.height:
                ui.grafico(ui.area_empilhada(serie_papel, "ano_mes", "receita_liquida",
                                             "rotulo", percentual_100=True, altura=340),
                           serie_papel.select("ano_mes", "rotulo", "receita_liquida"),
                           "papel_share")

        st.warning(
            "O papel analítico vem de `config/seller_roles.yaml` e **ainda não foi homologado**. "
            "Códigos que aparentam ser canais (V DIRETA FARELO, TELEMK/BALCÃO, VDA SUBPRODUTO) "
            "estão como `NAO_CLASSIFICADO` para não criarem representantes fictícios (Q-01).",
            icon="⚠️",
        )

    ui.secao("Cobertura territorial")
    cob = _cobertura_territorial()
    if cob.height:
        c = st.columns(4)
        ui.cartao(c[0], "Vendedores com movimento", ui.inteiro(cob.height))
        ui.cartao(c[1], "Regiões atendidas (máx. por vendedor)",
                  ui.inteiro(cob["regioes_atendidas"].max()))
        ui.cartao(c[2], "Clientes por vendedor (mediana)",
                  ui.inteiro(cob["clientes"].median()))
        ui.cartao(c[3], "Receita do maior vendedor",
                  ui.moeda(cob["receita"].max(), compacto=True))
        ui.tabela(cob, "cobertura_territorial", altura=380, chave="cob")

        st.caption(
            "Doze códigos que vendem não constam do arquivo de região comercial "
            "(`0, 6, 17, 24, 44, 49, 382, 446, 456, 457, 467, 470`) — lacuna registrada em Q-10."
        )

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao("Geografia real do cliente", "UF e cidade de entrega — não é a região comercial.")
    col1, col2 = st.columns(2)
    with col1:
        uf = sales.por_dimensao(f, "uf", base_custo)
        ui.tabela(uf.select("rotulo", "receita_liquida", "ton_liquida", "pmv",
                            "clientes", "frete_por_ton", "margem_proxy_pct"),
                  "por_uf", altura=380, chave="uf_tab")
    with col2:
        cidade = sales.por_dimensao(f, "cidade", base_custo, limite=60)
        ui.tabela(cidade.select("rotulo", "receita_liquida", "ton_liquida", "pmv",
                                "clientes", "frete_por_ton"),
                  "por_cidade", altura=380, chave="cid_tab")

    ui.secao("Ramo de atividade e perfil do cliente")
    col1, col2 = st.columns(2)
    with col1:
        ramo = sales.por_dimensao(f, "ramo", base_custo)
        if ramo.height:
            ui.grafico(ui.barra(ramo, "rotulo", "receita_liquida",
                                "Receita por ramo", horizontal=True, altura=360),
                       ramo, "ramo")
    with col2:
        perfil = sales.por_dimensao(f, "perfil", base_custo, limite=15)
        if perfil.height:
            ui.grafico(ui.barra(perfil, "rotulo", "receita_liquida",
                                "Receita por perfil de empresa", horizontal=True, altura=360),
                       perfil, "perfil")
