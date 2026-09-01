"""
Positivados e Coortes.

Fato verificado na carga (RN-15): "positivado" é o mês da PRIMEIRA compra do
cliente — 2.871 vínculos para 2.871 clientes distintos, nenhum repetido.
A tabela é, na prática, o registro de coortes de entrada.
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.config import load_yaml
from src.repositories import cohorts

st.title("Positivados e Coortes")
barra_lateral()

cfg = load_yaml("settings.yaml").get("positivados") or {}
inicio_padrao = cfg.get("analise_inicio", "2021-05")
meses_implantacao = cfg.get("implantacao_erp") or []

st.info(
    "**Positivado = mês da primeira compra do cliente.** Verificado na carga: 2.871 vínculos "
    "para 2.871 clientes distintos, e a soma bate com `QTD_POSITIVADOS` da fonte. "
    "Não é 'cliente que comprou no mês'.",
    icon="🌱",
)

incluir = st.checkbox(
    f"Incluir período de implantação do ERP ({', '.join(meses_implantacao)})",
    value=False,
    help=f"Esses meses estão fora do padrão (fev/2021: 729 positivados contra mediana de ~40). "
         f"Os dados nunca são excluídos do banco — apenas ficam de fora da análise por padrão, "
         f"que começa em {inicio_padrao}.",
)

serie = cohorts.serie_positivados(incluir)
resumo = cohorts.resumo_coortes(incluir)

if serie.height == 0:
    st.warning("Sem dados de positivados.")
    st.stop()

c = st.columns(5)
ui.cartao(c[0], "Total de positivados", ui.inteiro(serie["positivados"].sum()))
ui.cartao(c[1], "Média mensal", ui.inteiro(serie["positivados"].mean()))
ui.cartao(c[2], "Último mês", ui.inteiro(serie["positivados"][-1]))
recompra_media = float(resumo["taxa_recompra_pct"].mean() or 0) if resumo.height else 0
ui.cartao(c[3], "Recompra média", ui.percentual(recompra_media),
          ajuda="Percentual de clientes da coorte que voltaram a comprar.")
ui.cartao(c[4], "Receita acumulada",
          ui.moeda(resumo["receita_acumulada"].sum() if resumo.height else 0, compacto=True))

abas = st.tabs(["Entrada de clientes", "Coortes e retenção", "Recompra", "Clientes da coorte"])

# ---------------------------------------------------------------------
with abas[0]:
    ui.secao("Positivados por mês")
    fig = ui.barra(serie, "ano_mes", "positivados", altura=380)
    ui.grafico(fig, serie, "positivados_mes")

    col1, col2 = st.columns(2)
    with col1:
        ui.secao("Receita dos positivados")
        ui.grafico(ui.linha(serie, "ano_mes", ["vlrtot_positivados"], altura=320),
                   serie.select("ano_mes", "vlrtot_positivados"), "receita_positivados")
    with col2:
        ui.secao("Participação na receita do mês")
        ui.grafico(ui.linha(serie, "ano_mes", "perc_positivados_geral", altura=320),
                   serie.select("ano_mes", "perc_positivados_geral"), "perc_positivados")

    ui.tabela(serie, "positivados_mensal", altura=340, chave="pos_serie")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Resumo das coortes de entrada")
    if resumo.height:
        ui.tabela(
            resumo.select("coorte", "clientes", "clientes_com_recompra", "taxa_recompra_pct",
                          "receita_primeira_compra", "receita_acumulada",
                          "receita_media_por_cliente", "meses_ativos_medio", "ton_acumulada"),
            "resumo_coortes", altura=400, chave="coortes",
        )
        col1, col2 = st.columns(2)
        with col1:
            ui.grafico(ui.linha(resumo, "coorte", "taxa_recompra_pct",
                                "Taxa de recompra por coorte (%)", altura=340),
                       resumo.select("coorte", "taxa_recompra_pct"), "taxa_recompra")
        with col2:
            ui.grafico(ui.barra(resumo, "coorte", "receita_media_por_cliente",
                                "Receita média por cliente da coorte", altura=340),
                       resumo.select("coorte", "receita_media_por_cliente"), "receita_coorte")
        st.caption(
            "As coortes mais recentes têm recompra naturalmente menor: os clientes ainda não "
            "tiveram tempo de voltar. Compare coortes de maturidade semelhante."
        )

    ui.secao("Matriz de retenção (coorte × meses desde a entrada)")
    retencao = cohorts.matriz_retencao(incluir, meses=12)
    if retencao.height:
        ui.grafico(
            ui.heatmap(retencao, "meses_desde_entrada", "coorte", "retencao_pct",
                       "Retenção % por coorte", altura=520),
            retencao, "matriz_retencao",
        )

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao("Recompra em 30, 60, 90, 180 e 365 dias")
    rec = cohorts.recompra_por_janela(incluir)
    if rec.height:
        pct = rec.with_columns([
            (100 * pl.col(f"recompra_{j}d") / pl.col("clientes")).round(1).alias(f"{j}d_pct")
            for j in (30, 60, 90, 180, 365)
        ])
        c = st.columns(6)
        ui.cartao(c[0], "Clientes", ui.inteiro(rec["clientes"].sum()))
        for i, j in enumerate((30, 60, 90, 180, 365)):
            taxa = 100 * float(rec[f"recompra_{j}d"].sum()) / float(rec["clientes"].sum() or 1)
            ui.cartao(c[i + 1], f"Recompra {j}d", ui.percentual(taxa))

        longo = pct.unpivot(
            index="coorte",
            on=[f"{j}d_pct" for j in (30, 60, 90, 180, 365)],
            variable_name="janela", value_name="taxa_pct",
        )
        ui.grafico(ui.linha(longo, "coorte", "taxa_pct", cor="janela",
                            titulo="Taxa de recompra por janela", altura=420),
                   pct, "recompra_janelas")

        sem = rec.with_columns(
            (100 * pl.col("sem_recompra") / pl.col("clientes")).round(1).alias("sem_recompra_pct")
        )
        ui.secao("Clientes novos sem nenhuma recompra")
        ui.grafico(ui.barra(sem, "coorte", "sem_recompra_pct",
                            "% da coorte que nunca voltou a comprar", altura=340),
                   sem, "sem_recompra")
        ui.tabela(pct, "recompra_coorte", altura=360, chave="recompra")

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao("Abrir uma coorte", "Clientes que entraram no mês escolhido e o que fizeram depois.")
    if resumo.height:
        coorte = st.selectbox("Coorte", resumo["coorte"].to_list(),
                              index=max(0, resumo.height - 13), key="coorte_sel")
        clientes = cohorts.clientes_da_coorte(coorte)
        if clientes.height:
            c = st.columns(4)
            ui.cartao(c[0], "Clientes na coorte", ui.inteiro(clientes.height))
            ui.cartao(c[1], "Receita acumulada",
                      ui.moeda(clientes["receita_acumulada"].sum(), compacto=True))
            ativos = clientes.filter(pl.col("ultimo_mes_ativo") > 0).height
            ui.cartao(c[2], "Voltaram a comprar", ui.inteiro(ativos))
            ui.cartao(c[3], "Receita média por cliente",
                      ui.moeda(clientes["receita_acumulada"].mean()))
            ui.tabela(clientes, f"coorte_{coorte}", altura=440, chave="coorte_cli")
        else:
            st.info("Nenhum cliente encontrado nessa coorte.")
