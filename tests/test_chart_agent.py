from __future__ import annotations

import plotly.graph_objects as go
import polars as pl

from app.components import ui
from src.insights import chart_agent


def test_analisar_grafico_temporal_com_objetivo_especifico() -> None:
    dados = pl.DataFrame({
        "ano_mes": ["2026-01", "2026-02", "2026-03"],
        "receita_liquida": [100.0, 150.0, 120.0],
        "ton_liquida": [10.0, 12.0, 9.0],
    })
    fig = go.Figure(go.Scatter(
        x=dados["ano_mes"].to_list(),
        y=dados["receita_liquida"].to_list(),
        name="receita_liquida",
    ))

    analise = chart_agent.analisar("receita_volume", dados, fig)

    assert analise is not None
    assert "receita líquida" in analise.objetivo
    assert any("2026-01" in linha and "2026-03" in linha for linha in analise.analise)
    assert any("Pico" in linha for linha in analise.analise)


def test_ajuda_indicador_cobre_titulos_genericos_de_receita() -> None:
    ajuda = chart_agent.ajuda_indicador("Receita total")

    assert ajuda is not None
    assert "recorte" in ajuda


def test_analisar_usa_dados_extraidos_do_plotly_quando_dataframe_nao_eh_passado() -> None:
    fig = go.Figure(go.Bar(
        x=[10.0, 5.0],
        y=["A", "B"],
        orientation="h",
        name="receita_liquida",
    ))

    analise = chart_agent.analisar("ranking_receita", None, fig)

    assert analise is not None
    assert any("A" in linha for linha in analise.analise)


def test_correlacao_e_formatada_como_numero_nao_percentual() -> None:
    dados = pl.DataFrame({
        "defasagem_meses": [0, 1],
        "correlacao": [0.25, -0.82],
        "meses_comparados": [12, 11],
    })

    analise = chart_agent.analisar("correlacao_defasagem", dados)

    assert analise is not None
    assert "0,820" in analise.analise[0]
    assert "%" not in analise.analise[0]


def test_moeda_negativa_em_texto_usa_padrao_brasileiro() -> None:
    dados = pl.DataFrame({
        "ano_mes": ["2023-01", "2026-08"],
        "receita_liquida": [825836.09, -336.74],
    })

    analise = chart_agent.analisar("receita_volume", dados)

    assert analise is not None
    linha = analise.analise[0]
    assert "R$ 825.836,09" in linha
    assert "-R$ 336,74" in linha
    assert "R$ -" not in linha
    assert "2023-01" in linha


def test_ui_moeda_negativa_usa_sinal_antes_do_real() -> None:
    assert ui.moeda(-336.74) == "-R$ 336,74"


def test_dataframe_de_exibicao_formata_colunas_analiticas() -> None:
    dados = pl.DataFrame({
        "codprod": [20059],
        "receita_liquida": [11465984.72],
        "margem_proxy_pct": [26.57],
        "ton_liquida": [1234.5],
        "frete_por_ton": [87.9],
    })

    exibicao = ui._df_exibicao(dados)

    assert exibicao["codprod"][0] == "20059"
    assert exibicao["receita_liquida"][0] == "R$ 11.465.984,72"
    assert exibicao["margem_proxy_pct"][0] == "26,6%"
    assert exibicao["ton_liquida"][0] == "1.234,5 t"
    assert exibicao["frete_por_ton"][0] == "R$ 87,90/t"
