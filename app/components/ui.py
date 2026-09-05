"""
Componentes visuais compartilhados.

Padrao: formatacao pt-BR em todo numero, avisos permanentes onde a
especificacao exige, e nenhuma regra de negocio — apenas apresentacao.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from html import escape
from math import isfinite
from typing import Any

# O projeto usa polars, mas o Plotly importa pandas de forma preguicosa dentro
# de update_layout/update_geos. O Streamlit roda cada pagina numa thread, e duas
# threads entrando nesse import ao mesmo tempo produzem "partially initialized
# module 'pandas' ... most likely due to a circular import" — erro intermitente
# que derrubava a tela inteira. Importar junto com o plotly resolve o import uma
# vez so, e toda pagina passa por aqui. Nao remover por parecer sem uso.
import pandas  # noqa: F401
import plotly.graph_objects as go
import polars as pl
import streamlit as st

from src.insights import chart_agent

# Paleta: azul-petroleo como cor primaria, ambar para alerta, coral para queda.
# Evita vermelho/verde puros (guia de UI) e mantem contraste em tema escuro.
CORES = [
    "#00A8B5", "#F5A524", "#7C6BF5", "#E1656E", "#4CAF93",
    "#B58900", "#5A9BD5", "#D97757", "#8E7CC3", "#6AA84F",
]
COR_POSITIVA = "#4CAF93"
COR_NEGATIVA = "#E1656E"
COR_NEUTRA = "#8A8F98"


# ---------------------------------------------------------------------
# Formatacao pt-BR
# ---------------------------------------------------------------------


def moeda(v: float | None, casas: int = 2, compacto: bool = False) -> str:
    if v is None:
        return "—"
    sinal = "-" if v < 0 else ""
    valor = abs(v)
    if compacto:
        for limite, sufixo in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
            if valor >= limite:
                return f"{sinal}R$ {_num(valor / limite, 2)}{sufixo}"
    return f"{sinal}R$ {_num(valor, casas)}"


def numero(v: float | None, casas: int = 2, compacto: bool = False) -> str:
    if v is None:
        return "—"
    if compacto:
        for limite, sufixo in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
            if abs(v) >= limite:
                return f"{_num(v / limite, 2)}{sufixo}"
    return _num(v, casas)


def percentual(v: float | None, casas: int = 1) -> str:
    return "—" if v is None else f"{_num(v, casas)}%"


def _num(v: float, casas: int) -> str:
    """Formata no padrao pt-BR: milhar com ponto, decimal com virgula."""
    return f"{v:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def inteiro(v: float | int | None) -> str:
    return "—" if v is None else f"{int(v):,}".replace(",", ".")


# ---------------------------------------------------------------------
# Cartoes
# ---------------------------------------------------------------------


def cartao(
    col: Any,
    titulo: str,
    valor: str,
    delta: str | None = None,
    ajuda: str | None = None,
    delta_invertido: bool = False,
) -> None:
    col.metric(
        label=titulo,
        value=valor,
        delta=delta,
        delta_color="inverse" if delta_invertido else "normal",
        help=ajuda or chart_agent.ajuda_indicador(titulo),
    )


def variacao_texto(atual: float | None, anterior: float | None) -> str | None:
    if atual is None or anterior in (None, 0):
        return None
    return f"{_num(100 * (atual - anterior) / abs(anterior), 1)}%"


# ---------------------------------------------------------------------
# Avisos exigidos pela especificacao
# ---------------------------------------------------------------------


def aviso_custo() -> None:
    st.warning(
        "**Os conceitos de custo ainda não foram homologados economicamente.** "
        "Todas as análises de margem são exploratórias — o resultado é uma "
        "**Margem Proxy**, não margem contábil. Ver `docs/open_questions.md` (Q-04, Q-15).",
        icon="⚠️",
    )


def aviso_correlacao() -> None:
    st.info(
        "Esta página mostra **correlação exploratória mensal**. Não há granularidade de "
        "fornecedor, rendimento de moagem ou qualidade do trigo — portanto **correlação "
        "aqui não é prova de causalidade**.",
        icon="ℹ️",
    )


def aviso_performance_interna() -> None:
    st.info(
        "A plataforma mede **performance interna atual**. Baixa venda em uma região "
        "não significa baixo potencial de mercado — potencial externo exigiria dados "
        "que ainda não temos.",
        icon="ℹ️",
    )


def aviso_cobertura_frete(pct_nao_alocado: float, pct_cte_sem_nfe: float) -> None:
    st.warning(
        f"**{percentual(pct_nao_alocado)} do frete não foi alocado** a notas de venda e "
        f"**{percentual(pct_cte_sem_nfe)} dos CT-e não têm NF-e vinculada**. "
        "Os valores abaixo cobrem apenas a parte alocada.",
        icon="🚚",
    )


def selo_status(status: str) -> str:
    return {
        "HOMOLOGADA": "✅ Homologada",
        "RECONCILIADA": "🔵 Reconciliada",
        "PROVISIONAL": "🟡 Provisional",
        "PASS": "✅ OK",
        "WARN": "🟡 Atenção",
        "FAIL": "🔴 Falha",
        "SKIPPED": "⚪ Não executada",
        "OK": "✅ OK",
        "DIVERGENTE": "🔴 Divergente",
        "EXPLICADO": "🔵 Explicado",
        "SEM_FONTE": "⚪ Sem fonte",
    }.get(status, status)


def guia_rapido_navegacao() -> None:
    """Orientacao curta para consultores que entram na plataforma durante reuniao."""
    with st.sidebar.expander("Ajuda rápida de navegação", expanded=False):
        st.markdown(
            """
- **Comece por Visão Geral:** veja KPIs, tendência, mix e alertas do recorte.
- **Valide em Qualidade:** confirme reconciliação, pendências e métricas provisionais antes de apresentar.
- **Aprofunde em Comercial:** use Vendas, Regional, RCAs, Clientes e Positivados para sair do total e chegar ao detalhe.
- **Use Econômico para hipóteses:** Custos, Logística e Trigo explicam pressão de margem proxy, frete e correlações exploratórias.
- **Use o Explorador:** monte cortes novos quando a pergunta da reunião não estiver pronta em uma página.
"""
        )


# ---------------------------------------------------------------------
# Graficos
# ---------------------------------------------------------------------


def _layout(fig: go.Figure, titulo: str = "", altura: int = 380) -> go.Figure:
    fig.update_layout(
        title=titulo or None,
        height=altura,
        margin=dict(l=10, r=10, t=40 if titulo else 10, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        colorway=CORES,
        separators=",.",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    return fig


def linha(
    df: pl.DataFrame, x: str, y: str | list[str], titulo: str = "",
    cor: str | None = None, altura: int = 380,
) -> go.Figure:
    fig = go.Figure()
    if cor:
        for i, (chave,) in enumerate(df.select(cor).unique().sort(cor).iter_rows()):
            sub = df.filter(pl.col(cor) == chave).sort(x)
            fig.add_trace(go.Scatter(
                x=sub[x].to_list(), y=sub[y].to_list(), name=str(chave),
                mode="lines+markers", line=dict(width=2, color=CORES[i % len(CORES)]),
                marker=dict(size=5),
            ))
    else:
        colunas = [y] if isinstance(y, str) else y
        for i, c in enumerate(colunas):
            fig.add_trace(go.Scatter(
                x=df[x].to_list(), y=df[c].to_list(), name=c,
                mode="lines+markers", line=dict(width=2, color=CORES[i % len(CORES)]),
                marker=dict(size=5),
            ))
    return _layout(fig, titulo, altura)


def barra(
    df: pl.DataFrame, x: str, y: str, titulo: str = "",
    horizontal: bool = False, cor_por_sinal: bool = False, altura: int = 380,
) -> go.Figure:
    valores = df[y].to_list()
    cores = (
        [COR_POSITIVA if (v or 0) >= 0 else COR_NEGATIVA for v in valores]
        if cor_por_sinal else CORES[0]
    )
    if horizontal:
        fig = go.Figure(go.Bar(x=valores, y=df[x].to_list(), orientation="h", marker_color=cores))
        fig.update_layout(yaxis=dict(autorange="reversed"))
    else:
        fig = go.Figure(go.Bar(x=df[x].to_list(), y=valores, marker_color=cores))
    return _layout(fig, titulo, altura)


def area_empilhada(
    df: pl.DataFrame, x: str, y: str, cor: str, titulo: str = "",
    percentual_100: bool = False, altura: int = 400,
) -> go.Figure:
    fig = go.Figure()
    for i, (chave,) in enumerate(df.select(cor).unique().sort(cor).iter_rows()):
        sub = df.filter(pl.col(cor) == chave).sort(x)
        fig.add_trace(go.Scatter(
            x=sub[x].to_list(), y=sub[y].to_list(), name=str(chave),
            mode="lines", stackgroup="um",
            groupnorm="percent" if percentual_100 else None,
            line=dict(width=0.5, color=CORES[i % len(CORES)]),
            fillcolor=CORES[i % len(CORES)],
        ))
    fig = _layout(fig, titulo, altura)
    if percentual_100:
        fig.update_yaxes(ticksuffix="%", range=[0, 100])
    return fig


def barras_empilhadas(
    df: pl.DataFrame, x: str, y: str, cor: str, titulo: str = "", altura: int = 400
) -> go.Figure:
    fig = go.Figure()
    for i, (chave,) in enumerate(df.select(cor).unique().sort(cor).iter_rows()):
        sub = df.filter(pl.col(cor) == chave).sort(x)
        fig.add_trace(go.Bar(
            x=sub[x].to_list(), y=sub[y].to_list(), name=str(chave),
            marker_color=CORES[i % len(CORES)],
        ))
    fig.update_layout(barmode="stack")
    return _layout(fig, titulo, altura)


def dispersao(
    df: pl.DataFrame, x: str, y: str, tamanho: str | None = None,
    cor: str | None = None, rotulo: str | None = None,
    titulo: str = "", altura: int = 460,
) -> go.Figure:
    tamanhos = None
    if tamanho and df.height:
        vals = [abs(v or 0) for v in df[tamanho].to_list()]
        maximo = max(vals) or 1
        tamanhos = [8 + 42 * (v / maximo) for v in vals]

    marker: dict[str, Any] = {"size": tamanhos or 12, "opacity": 0.75,
                              "line": dict(width=1, color="rgba(255,255,255,0.35)")}
    if cor and cor in df.columns:
        # Plotly rejeita None na escala de cor. Nulo vira 0 — e o rótulo do
        # eixo de cor avisa, para o leitor não confundir "sem dado" com "zero".
        valores_cor = [float(v) if v is not None else 0.0 for v in df[cor].to_list()]
        tem_nulo = any(v is None for v in df[cor].to_list())
        marker["color"] = valores_cor
        marker["colorscale"] = "Teal"
        marker["showscale"] = True
        marker["colorbar"] = dict(
            title=f"{cor} (nulo=0)" if tem_nulo else cor, thickness=12
        )

    fig = go.Figure(go.Scatter(
        x=df[x].to_list(), y=df[y].to_list(), mode="markers+text" if rotulo else "markers",
        text=df[rotulo].to_list() if rotulo else None,
        textposition="top center", textfont=dict(size=9),
        marker=marker,
        hovertext=df[rotulo].to_list() if rotulo else None,
    ))
    fig = _layout(fig, titulo, altura)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title=x)
    fig.update_yaxes(title=y)
    return fig


def waterfall(
    categorias: list[str], valores: list[float], titulo: str = "", altura: int = 420
) -> go.Figure:
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative"] * len(valores) + ["total"],
        x=categorias + ["Variação total"],
        y=valores + [sum(valores)],
        connector=dict(line=dict(color="rgba(128,128,128,0.4)")),
        increasing=dict(marker=dict(color=COR_POSITIVA)),
        decreasing=dict(marker=dict(color=COR_NEGATIVA)),
        totals=dict(marker=dict(color=CORES[0])),
    ))
    return _layout(fig, titulo, altura)


def heatmap(
    df: pl.DataFrame, x: str, y: str, z: str, titulo: str = "", altura: int = 420
) -> go.Figure:
    pivot = df.pivot(values=z, index=y, on=x, aggregate_function="sum").fill_null(0)
    colunas = [c for c in pivot.columns if c != y]
    fig = go.Figure(go.Heatmap(
        z=[[row[c] for c in colunas] for row in pivot.iter_rows(named=True)],
        x=colunas, y=pivot[y].to_list(),
        colorscale="Teal", hoverongaps=False,
    ))
    return _layout(fig, titulo, altura)


def treemap(
    df: pl.DataFrame, rotulos: str, valores: str, pai: str | None = None,
    titulo: str = "", altura: int = 460,
) -> go.Figure:
    fig = go.Figure(go.Treemap(
        labels=df[rotulos].to_list(),
        parents=df[pai].to_list() if pai else [""] * df.height,
        values=[abs(v or 0) for v in df[valores].to_list()],
        textinfo="label+value+percent root",
        marker=dict(colorscale="Teal"),
    ))
    return _layout(fig, titulo, altura)


def pareto(
    df: pl.DataFrame, categoria: str, valor: str, titulo: str = "", altura: int = 420
) -> go.Figure:
    d = df.sort(valor, descending=True)
    total = float(d[valor].sum()) or 1
    acumulado = []
    soma = 0.0
    for v in d[valor].to_list():
        soma += float(v or 0)
        acumulado.append(100 * soma / total)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=d[categoria].to_list(), y=d[valor].to_list(),
                         name=valor, marker_color=CORES[0]))
    fig.add_trace(go.Scatter(x=d[categoria].to_list(), y=acumulado, name="% acumulado",
                             yaxis="y2", mode="lines+markers",
                             line=dict(color=CORES[1], width=2)))
    fig = _layout(fig, titulo, altura)
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right", range=[0, 105], ticksuffix="%", showgrid=False)
    )
    return fig


def boxplot(
    df: pl.DataFrame, categoria: str, valor: str, titulo: str = "", altura: int = 420
) -> go.Figure:
    fig = go.Figure()
    for i, (chave,) in enumerate(df.select(categoria).unique().sort(categoria).iter_rows()):
        sub = df.filter(pl.col(categoria) == chave)
        fig.add_trace(go.Box(y=sub[valor].to_list(), name=str(chave),
                             marker_color=CORES[i % len(CORES)], boxpoints="outliers"))
    return _layout(fig, titulo, altura)


# ---------------------------------------------------------------------
# Tabela + exportacao
# ---------------------------------------------------------------------


def tabela(
    df: pl.DataFrame,
    nome_export: str = "visao",
    altura: int = 420,
    formatos: dict[str, str] | None = None,
    chave: str | None = None,
) -> None:
    """Exibe a tabela e oferece exportacao CSV e XLSX com nome carimbado."""
    if df.height == 0:
        st.info("Nenhum dado para o recorte selecionado.")
        return

    st.dataframe(_df_exibicao(df, formatos), use_container_width=True, height=altura, hide_index=True)
    botoes_export(df, nome_export, chave=chave)


def botoes_export(df: pl.DataFrame, nome: str, chave: str | None = None) -> None:
    """Exportacao CSV/XLSX. O nome do arquivo carrega data e hora (especificacao 32)."""
    from src.exports.files import para_csv, para_xlsx

    carimbo = datetime.now().strftime("%Y%m%d_%H%M")
    base = f"{nome}_{carimbo}"
    sufixo = chave or nome

    c1, c2, _ = st.columns([1, 1, 6])
    c1.download_button(
        "⬇ CSV", data=para_csv(df), file_name=f"{base}.csv",
        mime="text/csv", key=f"csv_{sufixo}_{carimbo}", use_container_width=True,
    )
    c2.download_button(
        "⬇ XLSX", data=para_xlsx(df), file_name=f"{base}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"xlsx_{sufixo}_{carimbo}", use_container_width=True,
    )


def grafico(
    fig: go.Figure,
    dados: pl.DataFrame | None = None,
    nome: str = "grafico",
    ajuda: str | None = None,
) -> None:
    """
    Renderiza o grafico e, opcionalmente, permite baixar os dados que o geraram
    (exigencia da especificacao secao 32).
    """
    st.plotly_chart(fig, use_container_width=True, config={
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": "png", "scale": 2,
            "filename": f"{nome}_{datetime.now():%Y%m%d_%H%M}",
        },
    })

    analise = chart_agent.analisar(nome, dados, fig=fig, ajuda=ajuda)
    if analise is not None:
        with st.expander("Ajuda e análise IA do gráfico", expanded=False):
            st.markdown(_paragrafo_html("Objetivo.", analise.objetivo), unsafe_allow_html=True)
            st.markdown(_paragrafo_html("Como ler.", analise.como_ler), unsafe_allow_html=True)
            st.markdown("**Leitura do agente especialista.**")
            st.markdown(_lista_html(analise.analise), unsafe_allow_html=True)
            if analise.atencoes:
                st.markdown("**Atenções.**")
                st.markdown(_lista_html(analise.atencoes), unsafe_allow_html=True)

    if dados is not None and dados.height:
        with st.expander("Dados que geraram este gráfico"):
            st.dataframe(_df_exibicao(dados), use_container_width=True, height=260, hide_index=True)
            botoes_export(dados, nome, chave=f"g_{nome}")


def secao(titulo: str, ajuda: str | None = None) -> None:
    st.markdown(f"#### {titulo}")
    if ajuda:
        st.caption(ajuda)


def texto_seguro(texto: str) -> None:
    """Renderiza texto dinamico sem parser de LaTeX/Markdown sobre `R$`."""
    st.markdown(f"<p>{escape(str(texto))}</p>", unsafe_allow_html=True)


def markdown_seguro(texto: str) -> None:
    """Renderiza Markdown mantendo `R$` literal, sem acionar LaTeX inline."""
    st.markdown(str(texto).replace("$", r"\$"))


def _df_exibicao(df: pl.DataFrame, formatos: dict[str, str] | None = None) -> Any:
    pdf = df.to_pandas()
    formatos = formatos or {}
    for coluna in pdf.columns:
        estilo = formatos.get(coluna) or _estilo_coluna(str(coluna))
        if estilo is None:
            continue
        pdf[coluna] = pdf[coluna].map(lambda v, e=estilo: _formatar_celula(v, e))
    return pdf


def _estilo_coluna(coluna: str) -> str | None:
    c = _normalizar_coluna(coluna)
    if _eh_codigo(c):
        return "codigo"
    if _eh_percentual(c):
        return "percentual"
    if _eh_moeda(c):
        return "moeda_ton" if _eh_por_ton(c) else "moeda"
    if _eh_tonelada(c):
        return "ton"
    if _eh_contagem(c):
        return "inteiro"
    return None


def _formatar_celula(valor: Any, estilo: str) -> Any:
    numero_valor = _como_float(valor)
    if numero_valor is None:
        return "—" if _valor_vazio(valor) else valor
    if estilo == "codigo":
        return str(int(numero_valor)) if numero_valor.is_integer() else str(valor)
    if estilo == "percentual":
        return percentual(numero_valor)
    if estilo == "moeda_ton":
        return f"{moeda(numero_valor)}/t"
    if estilo == "moeda":
        return moeda(numero_valor)
    if estilo == "ton":
        return f"{numero(numero_valor, 1)} t"
    if estilo == "inteiro":
        return inteiro(numero_valor)
    if estilo == "numero":
        return numero(numero_valor)
    return valor


def _como_float(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, int | float | Decimal):
        v = float(valor)
        return v if isfinite(v) else None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    return v if isfinite(v) else None


def _valor_vazio(valor: Any) -> bool:
    if valor is None:
        return True
    try:
        return bool(valor != valor)
    except Exception:  # noqa: BLE001
        return False


def _normalizar_coluna(coluna: str) -> str:
    mapa = str.maketrans("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
    return coluna.translate(mapa).lower().replace(" ", "_").replace("-", "_")


def _eh_codigo(c: str) -> bool:
    return (
        c.startswith("cod")
        or c.endswith("_id")
        or c in {"id", "chave", "nunota", "sequencia", "numnota", "ano", "mes"}
        or c.endswith("_hash")
    )


def _eh_percentual(c: str) -> bool:
    return (
        "pct" in c
        or "percentual" in c
        or c.startswith("perc")
        or c.startswith("%")
        or "taxa" in c
        or "atingimento" in c
        or c == "markup"
    )


def _eh_moeda(c: str) -> bool:
    return any(token in c for token in (
        "receita", "valor", "vlr", "frete", "custo", "cus", "margem", "desconto",
        "comissao", "icms", "subst", "ticket", "preco", "pmv", "orcado", "realizado",
        "spread", "r$/t", "rs_por_ton",
    ))


def _eh_por_ton(c: str) -> bool:
    return any(token in c for token in ("por_ton", "r$/t", "rs_por_ton")) or c == "pmv"


def _eh_tonelada(c: str) -> bool:
    return "ton" in c or "volume" in c


def _eh_contagem(c: str) -> bool:
    return any(token in c for token in (
        "clientes", "documentos", "produtos", "linhas", "notas", "cte", "rotas",
        "meses", "verificacoes", "avisos", "vendedores", "positivados", "ativos",
        "novos", "reativados", "rows", "qtd",
    ))


def _paragrafo_html(rotulo: str, texto: str) -> str:
    return f"<p><strong>{escape(rotulo)}</strong> {escape(str(texto))}</p>"


def _lista_html(linhas: tuple[str, ...] | list[str]) -> str:
    itens = "".join(f"<li>{escape(str(linha))}</li>" for linha in linhas)
    return f"<ul>{itens}</ul>"
