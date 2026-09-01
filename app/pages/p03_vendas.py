"""
Vendas e Devoluções, com drill-down até a transação original.

Caminho previsto na especificação (§20):
  ano → mês → classificação → produto → região → RCA → cliente → NF → item
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import aplicar_trilha, barra_lateral, breadcrumb, descer, trilha
from src.repositories import logistics, sales

st.title("Vendas e Devoluções")
f_global, base_custo = barra_lateral()

breadcrumb()
f = aplicar_trilha(f_global)

NIVEIS = ["classificacao", "produto", "regiao", "vendedor", "cliente"]
ROTULOS = {
    "classificacao": "Classificação", "produto": "Produto", "regiao": "Região comercial",
    "vendedor": "Vendedor", "cliente": "Cliente", "uf": "UF", "ramo": "Ramo",
    "cidade": "Cidade", "operacao": "Operação", "cif_fob": "Modalidade de frete",
}


def _proximo_nivel() -> str:
    usados = {n["dimensao"] for n in trilha()}
    for nivel in NIVEIS:
        if nivel not in usados:
            return nivel
    return "cliente"


serie = sales.serie_mensal(f, base_custo)
if serie.height == 0:
    st.warning("Nenhum dado para o recorte selecionado.")
    st.stop()

kpis = sales.kpis_gerais(f, base_custo)
c = st.columns(6)
ui.cartao(c[0], "Receita líquida", ui.moeda(kpis["receita_liquida"], compacto=True))
ui.cartao(c[1], "Vendas brutas", ui.moeda(kpis["vendas_brutas"], compacto=True))
ui.cartao(c[2], "Devoluções", ui.moeda(kpis["devolucoes"], compacto=True))
ui.cartao(c[3], "Volume", f"{ui.numero(kpis['ton_liquida'], 0)} t")
ui.cartao(c[4], "PMV", ui.moeda(kpis["pmv"]) + "/t")
ui.cartao(c[5], "Desconto", ui.moeda(kpis["desconto"], compacto=True))

abas = st.tabs(["Série e drill-down", "Dispersão de preço", "Concentração", "Documentos e itens"])

# ---------------------------------------------------------------------
with abas[0]:
    col1, col2 = st.columns(2)
    with col1:
        ui.secao("Vendas × devoluções")
        fig = ui.linha(serie, "ano_mes", ["vendas_brutas"], altura=320)
        fig.add_bar(x=serie["ano_mes"].to_list(),
                    y=[abs(v or 0) for v in serie["devolucoes"].to_list()],
                    name="Devoluções (módulo)", marker_color=ui.COR_NEGATIVA, opacity=0.6)
        ui.grafico(fig, serie.select("ano_mes", "vendas_brutas", "devolucoes"), "vendas_devolucoes")
    with col2:
        ui.secao("PMV e desconto")
        fig = ui.linha(serie, "ano_mes", "pmv", altura=320)
        fig.add_bar(x=serie["ano_mes"].to_list(), y=serie["desconto"].to_list(),
                    name="Desconto", yaxis="y2", marker_color=ui.CORES[1], opacity=0.45)
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", showgrid=False))
        ui.grafico(fig, serie.select("ano_mes", "pmv", "desconto"), "pmv_desconto")

    nivel = _proximo_nivel()
    ui.secao(
        f"Detalhe por {ROTULOS.get(nivel, nivel)}",
        "Clique em uma linha e use **Aprofundar** para descer um nível.",
    )
    dimensao = st.selectbox(
        "Agrupar por", list(ROTULOS), index=list(ROTULOS).index(nivel),
        format_func=lambda d: ROTULOS[d], key="vd_dim",
    )
    top_n = st.select_slider("Top N", [5, 10, 20, 50, 100, 500], value=20, key="vd_topn")
    detalhe = sales.por_dimensao(f, dimensao, base_custo, limite=top_n)

    if detalhe.height:
        col1, col2 = st.columns([3, 2])
        with col1:
            ui.grafico(
                ui.barra(detalhe.head(20), "rotulo", "receita_liquida",
                         "Receita por " + ROTULOS[dimensao].lower(),
                         horizontal=True, altura=max(320, 22 * min(20, detalhe.height))),
                detalhe.head(20), f"receita_{dimensao}",
            )
        with col2:
            ui.grafico(ui.dispersao(detalhe.head(50), "ton_liquida", "pmv",
                                    tamanho="receita_liquida", rotulo="rotulo",
                                    titulo="Volume × PMV", altura=380),
                       detalhe.head(50), f"disp_{dimensao}")

        st.dataframe(
            detalhe.select("rotulo", "receita_liquida", "vendas_brutas", "devolucoes",
                           "ton_liquida", "pmv", "clientes", "documentos", "desconto",
                           "frete", "margem_proxy_pct").to_pandas(),
            use_container_width=True, height=340, hide_index=True,
        )
        ui.botoes_export(detalhe, f"vendas_{dimensao}", chave="vd_tab")

        c1, c2 = st.columns([3, 1])
        escolha = c1.selectbox(
            "Aprofundar em", detalhe["rotulo"].to_list(), key="vd_drill_valor"
        )
        if c2.button("Aprofundar ↓", use_container_width=True, key="vd_drill_btn"):
            linha = detalhe.filter(pl.col("rotulo") == escolha)
            if linha.height:
                descer(dimensao, linha["chave"][0], f"{ROTULOS[dimensao]}: {escolha}")
                st.rerun()

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Dispersão de preço",
             "Cada ponto é um produto no recorte. Dispersão alta indica política de preço heterogênea.")
    prod = sales.por_dimensao(f, "produto", base_custo, limite=200)
    if prod.height:
        ui.grafico(
            ui.dispersao(prod, "ton_liquida", "pmv", tamanho="receita_liquida",
                         cor="margem_proxy_pct", rotulo=None,
                         titulo="Volume × PMV (cor = margem proxy %)", altura=460),
            prod, "dispersao_preco",
        )
        ui.tabela(prod.select("rotulo", "ton_liquida", "pmv", "receita_liquida",
                              "desconto", "margem_proxy_pct", "clientes"),
                  "dispersao_produto", altura=340, chave="disp_prod")

# ---------------------------------------------------------------------
with abas[2]:
    dimensao = st.selectbox(
        "Concentração por", ["cliente", "produto", "vendedor", "regiao", "uf"],
        format_func=lambda d: ROTULOS.get(d, d), key="conc_dim",
    )
    conc = sales.por_dimensao(f, dimensao, base_custo, limite=60)
    if conc.height:
        total = float(conc["receita_liquida"].sum() or 0)
        c = st.columns(4)
        for i, n in enumerate([5, 10, 20, 50]):
            parte = float(conc.head(n)["receita_liquida"].sum() or 0)
            ui.cartao(c[i], f"Top {n}", ui.percentual(100 * parte / total if total else 0),
                      ajuda=f"{ui.moeda(parte, compacto=True)} de {ui.moeda(total, compacto=True)}")

        ui.grafico(ui.pareto(conc.head(30), "rotulo", "receita_liquida",
                             f"Pareto — {ROTULOS.get(dimensao, dimensao)}", altura=420),
                   conc, f"pareto_{dimensao}")
        ui.grafico(ui.treemap(conc.head(40), "rotulo", "receita_liquida", altura=460),
                   conc.head(40), f"treemap_{dimensao}")

        st.caption(
            "Concentração é um fato de estrutura. A leitura de risco depende do contexto "
            "comercial — a plataforma mede, não julga."
        )

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao("Documentos", "Último nível antes da transação original.")
    docs = sales.detalhe_documentos(f, limite=500)
    if docs.height == 0:
        st.info("Nenhum documento no recorte.")
    else:
        ui.tabela(docs, "documentos", altura=380, chave="docs")

        nunota = st.selectbox(
            "Abrir documento (NUNOTA)", docs["nunota"].to_list(),
            format_func=lambda n: f"NUNOTA {n}", key="doc_sel",
        )
        if nunota:
            cab = sales.cabecalho_documento(int(nunota))
            if cab:
                c = st.columns(6)
                ui.cartao(c[0], "Nota", str(cab.get("numnota") or "—"),
                          ajuda="Número fiscal do documento selecionado.")
                ui.cartao(c[1], "Data", str(cab.get("data_referencia") or "—"),
                          ajuda="Data de referência usada nas análises do documento.")
                ui.cartao(c[2], "Cliente", (cab.get("parceiro") or "—")[:22],
                          ajuda="Cliente/parceiro do documento aberto.")
                ui.cartao(c[3], "Vendedor", (cab.get("vendedor") or "—")[:18],
                          ajuda="Código comercial associado ao documento; papel analítico vem da configuração.")
                ui.cartao(c[4], "Modalidade", cab.get("cif_fob") or "—",
                          ajuda="Modalidade CIF/FOB normalizada pela primeira letra da origem.")
                ui.cartao(c[5], "Valor do documento", ui.moeda(cab.get("vlrnota")),
                          ajuda="Valor no grão do documento. Não somar por item para evitar duplicação.")
                st.caption(
                    f"Chave NF-e: `{cab.get('chavenfe') or '—'}` · "
                    f"Rota: {cab.get('cidorigem') or '—'} → {cab.get('ciddestino') or '—'} · "
                    f"Transportador: {cab.get('nome_transp') or '—'} · "
                    f"Ordem de carga: {cab.get('ordemcarga') or '—'}"
                )
                st.caption(
                    "⚠️ `VLRNOTA` é medida do **documento**. Somá-la no grão de item infla a "
                    "receita em 321,7% — por isso ela não existe em `fact_venda_item` (RN-02)."
                )

            ui.secao("Itens do documento")
            itens = sales.itens_do_documento(int(nunota))
            ui.tabela(itens, f"itens_nunota_{nunota}", altura=300, chave="itens")

            ctes = logistics.ctes_do_documento(int(nunota))
            if ctes.height:
                ui.secao("CT-e vinculados a esta nota")
                st.caption(
                    "O frete é rateado entre as notas cobertas pelo mesmo CT-e, por tonelagem. "
                    "O peso do rateio aparece na coluna `allocation_weight`."
                )
                ui.tabela(ctes, f"cte_nunota_{nunota}", altura=240, chave="ctes")
