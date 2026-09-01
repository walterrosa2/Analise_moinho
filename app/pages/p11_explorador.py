"""
Explorador — construtor de visões.

O consultor monta uma análise nova escolhendo dimensão, métrica, gráfico,
Top N e comparação temporal, sem alterar código. A configuração pode ser
salva em app.saved_views e reaberta depois.
"""
from __future__ import annotations

import json
from datetime import datetime

import polars as pl
import streamlit as st
from sqlalchemy import text

from app.components import ui
from app.state.session import barra_lateral
from src.db.engine import get_connection, read_sql
from src.metrics import registry
from src.repositories import sales

st.title("Explorador")
st.caption("Monte uma visão nova sem alterar código. Salve para reutilizar em outra reunião.")

f, base_custo = barra_lateral()

DIMENSOES = {
    "ano_mes": "Mês", "ano": "Ano", "classificacao": "Classificação", "produto": "Produto",
    "grupo_produto": "Grupo de produto", "cliente": "Cliente", "ramo": "Ramo de atividade",
    "perfil": "Perfil da empresa", "vendedor": "Vendedor", "papel": "Papel do vendedor",
    "regiao": "Região comercial", "uf": "UF do cliente", "cidade": "Cidade do cliente",
    "cif_fob": "Modalidade de frete", "empresa": "Empresa", "operacao": "Operação",
}

METRICAS = {
    "receita_liquida": "Receita líquida (R$)",
    "vendas_brutas": "Vendas brutas (R$)",
    "devolucoes": "Devoluções (R$)",
    "ton_liquida": "Volume líquido (t)",
    "pmv": "PMV (R$/t)",
    "clientes": "Clientes ativos",
    "documentos": "Documentos",
    "produtos": "Produtos distintos",
    "desconto": "Desconto (R$)",
    "comissao": "Comissão (R$)",
    "frete": "Frete alocado (R$)",
    "frete_por_ton": "Frete por tonelada (R$/t)",
    "custo": "Custo total (R$)",
    "margem_proxy": "Margem Proxy (R$)",
    "margem_proxy_pct": "Margem Proxy (%)",
}

GRAFICOS = ["Tabela", "Barra", "Barra horizontal", "Linha", "Área empilhada",
            "Área 100%", "Dispersão", "Treemap", "Pareto", "Heatmap"]


# ---------------------------------------------------------------------
# Visões salvas
# ---------------------------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def _visoes_salvas() -> pl.DataFrame:
    return read_sql(
        "SELECT view_id, name, description, owner, config, updated_at "
        "FROM app.saved_views ORDER BY updated_at DESC"
    )


def _salvar(nome: str, descricao: str, config: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            text(
                """
                INSERT INTO app.saved_views (name, description, owner, config)
                VALUES (:n, :d, :o, CAST(:c AS jsonb))
                ON CONFLICT (owner, name) DO UPDATE
                SET config = EXCLUDED.config,
                    description = EXCLUDED.description,
                    updated_at = now()
                """
            ),
            {"n": nome, "d": descricao, "o": "consultor",
             "c": json.dumps(config, ensure_ascii=False)},
        )


def _excluir(view_id: int) -> None:
    with get_connection() as conn:
        conn.execute(text("DELETE FROM app.saved_views WHERE view_id = :v"), {"v": view_id})


salvas = _visoes_salvas()

with st.expander("📁 Visões salvas", expanded=False):
    if salvas.height == 0:
        st.caption("Nenhuma visão salva ainda. Monte uma abaixo e clique em **Salvar visão**.")
    else:
        c1, c2, c3 = st.columns([4, 1, 1])
        escolhida = c1.selectbox(
            "Abrir", salvas["name"].to_list(), key="vs_abrir",
            format_func=lambda n: n,
        )
        if c2.button("Carregar", use_container_width=True, key="vs_load"):
            linha = salvas.filter(pl.col("name") == escolhida)
            if linha.height:
                cfg = linha["config"][0]
                st.session_state.explorador_config = cfg if isinstance(cfg, dict) else json.loads(cfg)
                st.rerun()
        if c3.button("Excluir", use_container_width=True, key="vs_del"):
            linha = salvas.filter(pl.col("name") == escolhida)
            if linha.height:
                _excluir(int(linha["view_id"][0]))
                _visoes_salvas.clear()
                st.rerun()
        ui.tabela(salvas.select("name", "description", "updated_at"),
                  "visoes_salvas", altura=200, chave="vs")

cfg = st.session_state.get("explorador_config", {})

# ---------------------------------------------------------------------
# Construtor
# ---------------------------------------------------------------------
st.markdown("#### Configuração da visão")
c1, c2, c3, c4 = st.columns(4)

dimensao = c1.selectbox(
    "Dimensão", list(DIMENSOES),
    index=list(DIMENSOES).index(cfg.get("dimensao", "classificacao")),
    format_func=lambda d: DIMENSOES[d], key="ex_dim",
)
metrica = c2.selectbox(
    "Métrica", list(METRICAS),
    index=list(METRICAS).index(cfg.get("metrica", "receita_liquida")),
    format_func=lambda m: METRICAS[m], key="ex_met",
)
tipo_grafico = c3.selectbox(
    "Visual", GRAFICOS,
    index=GRAFICOS.index(cfg.get("grafico", "Barra")), key="ex_graf",
)
top_n = c4.select_slider(
    "Top N", [5, 10, 20, 50, 100, 500], value=cfg.get("top_n", 20), key="ex_topn",
)

c1, c2, c3 = st.columns(3)
comparacao = c1.selectbox(
    "Comparação temporal", ["Nenhuma", "Período anterior", "Ano anterior (YoY)"],
    index=["Nenhuma", "Período anterior", "Ano anterior (YoY)"].index(
        cfg.get("comparacao", "Nenhuma")),
    key="ex_comp",
)
serie_temporal = c2.checkbox(
    "Quebrar por mês (série temporal)", value=cfg.get("serie", False), key="ex_serie",
)
ordenacao = c3.selectbox(
    "Ordenar por", ["Métrica (desc)", "Métrica (asc)", "Rótulo"],
    index=["Métrica (desc)", "Métrica (asc)", "Rótulo"].index(
        cfg.get("ordenacao", "Métrica (desc)")),
    key="ex_ord",
)

c1, c2, c3 = st.columns(3)
acumulado = c1.checkbox("Acumulado", value=cfg.get("acumulado", False), key="ex_acum")
media_movel = c2.checkbox("Média móvel (3 meses)", value=cfg.get("mm", False), key="ex_mm")
participacao = c3.checkbox("Mostrar participação %", value=cfg.get("part", True), key="ex_part")

st.divider()

# ---------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------
periodos_disponiveis = sales.serie_mensal(f, base_custo)["ano_mes"].to_list()
if not periodos_disponiveis:
    st.warning("Nenhum dado para o recorte selecionado.")
    st.stop()


def _meses_antes(ano_mes: str, k: int) -> str:
    ano, mes = int(ano_mes[:4]), int(ano_mes[5:7])
    total = ano * 12 + (mes - 1) - k
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


if serie_temporal:
    dados = sales.serie_por_dimensao(f, dimensao, top_n=min(top_n, 12), metrica=metrica) \
        if dimensao not in ("ano_mes", "ano") else sales.serie_mensal(f, base_custo)
    if dimensao in ("ano_mes", "ano"):
        dados = dados.rename({"ano_mes": "rotulo"}) if "ano_mes" in dados.columns else dados
else:
    dados = sales.por_dimensao(f, dimensao, base_custo, limite=top_n, ordenar_por="receita_liquida")

if dados.height == 0:
    st.warning("Nenhum resultado para esta combinação.")
    st.stop()

if metrica not in dados.columns:
    st.warning(
        f"A métrica **{METRICAS[metrica]}** não está disponível para esta combinação. "
        "Escolha outra métrica ou desative a série temporal."
    )
    st.stop()

# Ordenação
if not serie_temporal:
    if ordenacao == "Métrica (desc)":
        dados = dados.sort(metrica, descending=True, nulls_last=True)
    elif ordenacao == "Métrica (asc)":
        dados = dados.sort(metrica, nulls_last=True)
    else:
        dados = dados.sort("rotulo")

# Participação
if participacao and metrica in dados.columns and not serie_temporal:
    total = float(dados[metrica].sum() or 0)
    if total:
        dados = dados.with_columns(
            (100 * pl.col(metrica) / total).round(2).alias("participacao_pct")
        )

# Acumulado e média móvel
if acumulado and metrica in dados.columns:
    dados = dados.with_columns(pl.col(metrica).cum_sum().alias(f"{metrica}_acumulado"))
if media_movel and serie_temporal and metrica in dados.columns:
    dados = dados.with_columns(
        pl.col(metrica).rolling_mean(3).over("rotulo" if "rotulo" in dados.columns else None)
        .alias(f"{metrica}_mm3")
    )

# Comparação temporal
comp_df = None
if comparacao != "Nenhuma" and not serie_temporal:
    ini, fim = f.periodo_inicio or periodos_disponiveis[0], f.periodo_fim or periodos_disponiveis[-1]
    n_meses = len([p for p in periodos_disponiveis if ini <= p <= fim])
    if comparacao == "Ano anterior (YoY)":
        periodo_a = (_meses_antes(ini, 12), _meses_antes(fim, 12))
    else:
        periodo_a = (_meses_antes(ini, n_meses), _meses_antes(ini, 1))
    comp_df = sales.comparar_periodos(f, dimensao, periodo_a, (ini, fim), metrica, base_custo)

# ---------------------------------------------------------------------
# Renderização
# ---------------------------------------------------------------------
titulo = f"{METRICAS[metrica]} por {DIMENSOES[dimensao]}"
eixo_x = "ano_mes" if serie_temporal and "ano_mes" in dados.columns else "rotulo"
nome_export = f"explorador_{dimensao}_{metrica}"

if tipo_grafico == "Tabela":
    ui.tabela(dados, nome_export, altura=520, chave="ex_tab")
elif tipo_grafico == "Barra":
    ui.grafico(ui.barra(dados.head(60), eixo_x, metrica, titulo,
                        cor_por_sinal=metrica in ("devolucoes", "margem_proxy"), altura=460),
               dados, nome_export)
elif tipo_grafico == "Barra horizontal":
    ui.grafico(ui.barra(dados.head(40), eixo_x, metrica, titulo, horizontal=True,
                        altura=max(400, 20 * min(40, dados.height))), dados, nome_export)
elif tipo_grafico == "Linha":
    cor = "rotulo" if serie_temporal and "rotulo" in dados.columns and eixo_x == "ano_mes" else None
    ui.grafico(ui.linha(dados, eixo_x, metrica, titulo, cor=cor, altura=460), dados, nome_export)
elif tipo_grafico in ("Área empilhada", "Área 100%"):
    if serie_temporal and "rotulo" in dados.columns:
        ui.grafico(ui.area_empilhada(dados, "ano_mes", metrica, "rotulo", titulo,
                                     percentual_100=(tipo_grafico == "Área 100%"), altura=460),
                   dados, nome_export)
    else:
        st.info("Área empilhada exige a quebra por mês. Marque **Quebrar por mês**.")
elif tipo_grafico == "Dispersão":
    eixos = [c for c in ("ton_liquida", "pmv", "receita_liquida", "clientes") if c in dados.columns]
    if len(eixos) >= 2:
        c1, c2 = st.columns(2)
        ex = c1.selectbox("Eixo X", eixos, index=0, key="ex_disp_x")
        ey = c2.selectbox("Eixo Y", eixos, index=1, key="ex_disp_y")
        ui.grafico(ui.dispersao(dados, ex, ey, tamanho=metrica if metrica in dados.columns else None,
                                rotulo="rotulo" if "rotulo" in dados.columns else None,
                                titulo=titulo, altura=520), dados, nome_export)
elif tipo_grafico == "Treemap":
    ui.grafico(ui.treemap(dados.head(60), "rotulo", metrica, titulo=titulo, altura=520),
               dados, nome_export)
elif tipo_grafico == "Pareto":
    ui.grafico(ui.pareto(dados.head(40), "rotulo", metrica, titulo, altura=460),
               dados, nome_export)
elif tipo_grafico == "Heatmap":
    if serie_temporal and "rotulo" in dados.columns:
        ui.grafico(ui.heatmap(dados, "ano_mes", "rotulo", metrica, titulo, altura=520),
                   dados, nome_export)
    else:
        st.info("Heatmap exige a quebra por mês. Marque **Quebrar por mês**.")

if tipo_grafico != "Tabela":
    with st.expander("Tabela completa da visão"):
        ui.tabela(dados, nome_export, altura=420, chave="ex_full")

if comp_df is not None and comp_df.height:
    ui.secao(f"Comparação: {comparacao}")
    ui.tabela(
        comp_df.select("rotulo", "valor_a", "valor_b", "variacao", "variacao_pct",
                       "contribuicao_pct", "efeito_volume", "efeito_preco"),
        f"{nome_export}_comparacao", altura=380, chave="ex_comp_tab",
    )
    ui.grafico(
        ui.waterfall(comp_df.head(15)["rotulo"].to_list(),
                     [float(v or 0) for v in comp_df.head(15)["variacao"].to_list()],
                     "Contribuição para a variação", altura=400),
        comp_df.head(15), f"{nome_export}_waterfall",
    )

# ---------------------------------------------------------------------
# Salvar
# ---------------------------------------------------------------------
st.divider()
with st.form("salvar_visao"):
    st.markdown("**Salvar esta visão**")
    c1, c2 = st.columns([2, 3])
    nome = c1.text_input("Nome", value=cfg.get("nome", ""), placeholder="Volume por RCA e região")
    descricao = c2.text_input("Descrição", value=cfg.get("descricao", ""),
                              placeholder="Para a reunião mensal de comercial")
    if st.form_submit_button("Salvar visão", use_container_width=True):
        if not nome.strip():
            st.error("Informe um nome para a visão.")
        else:
            config = {
                "nome": nome, "descricao": descricao,
                "dimensao": dimensao, "metrica": metrica, "grafico": tipo_grafico,
                "top_n": top_n, "comparacao": comparacao, "serie": serie_temporal,
                "ordenacao": ordenacao, "acumulado": acumulado, "mm": media_movel,
                "part": participacao, "base_custo": base_custo,
                "filtros": dict(f.__dict__),
                "salvo_em": datetime.now().isoformat(timespec="seconds"),
            }
            _salvar(nome.strip(), descricao.strip(), config)
            _visoes_salvas.clear()
            st.success(f"Visão **{nome}** salva.")

# Rastreabilidade da métrica escolhida
try:
    m = registry.get(metrica if metrica in registry.REGISTRY else "receita_liquida")
    st.caption(
        f"**{m.label}** — {m.descricao} · Fórmula: `{m.formula}` · Grão: {m.grao} · "
        f"Status: {ui.selo_status(m.status.value)}"
    )
except KeyError:
    pass
