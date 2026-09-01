"""
Estado da sessao: filtros globais, base de custo e trilha de drill-down.

O objeto Filtros vive aqui e e lido por todas as paginas, garantindo que dois
graficos lado a lado estejam sempre falando do mesmo recorte.
"""
from __future__ import annotations

from typing import Any

import polars as pl
import streamlit as st

from src.config import load_yaml
from src.repositories.filters import Filtros
from src.repositories.sales import opcoes_filtro

TTL_CACHE = 600  # 10 min: suficiente para uma reuniao sem servir dado velho


@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def _opcoes() -> dict[str, Any]:
    return {k: v.to_dicts() for k, v in opcoes_filtro().items()}


def opcoes() -> dict[str, list[dict]]:
    return _opcoes()


def base_custo_padrao() -> str:
    return (load_yaml("settings.yaml").get("custos") or {}).get("base_padrao", "cusger")


def get_filtros() -> Filtros:
    if "filtros" not in st.session_state:
        st.session_state.filtros = Filtros()
    return st.session_state.filtros


def get_base_custo() -> str:
    if "base_custo" not in st.session_state:
        st.session_state.base_custo = base_custo_padrao()
    return st.session_state.base_custo


# ---------------------------------------------------------------------
# Drill-down: pilha de niveis com breadcrumb
# ---------------------------------------------------------------------


def trilha() -> list[dict[str, Any]]:
    if "drill" not in st.session_state:
        st.session_state.drill = []
    return st.session_state.drill


def descer(dimensao: str, chave: Any, rotulo: str) -> None:
    trilha().append({"dimensao": dimensao, "chave": chave, "rotulo": rotulo})


def subir() -> None:
    if trilha():
        trilha().pop()


def limpar_trilha() -> None:
    st.session_state.drill = []


def aplicar_trilha(f: Filtros) -> Filtros:
    """Aplica os niveis do drill-down sobre uma copia dos filtros globais."""
    dados = dict(f.__dict__)
    for nivel in trilha():
        dim, chave = nivel["dimensao"], nivel["chave"]
        campo = {
            "classificacao": "classificacoes",
            "produto": "produtos",
            "cliente": "clientes",
            "vendedor": "vendedores",
            "papel": "papeis",
            "regiao": "regioes",
            "uf": "ufs",
            "ramo": "ramos",
        }.get(dim)
        if campo:
            dados[campo] = [chave]
    return Filtros(**dados)


def breadcrumb() -> None:
    """Trilha de navegacao + botao de voltar nivel (especificacao secao 31)."""
    caminho = trilha()
    if not caminho:
        return
    partes = " › ".join(f"**{n['rotulo']}**" for n in caminho)
    c1, c2 = st.columns([8, 2])
    c1.markdown(f"Brasil › {partes}")
    with c2:
        b1, b2 = st.columns(2)
        if b1.button("← Voltar", use_container_width=True, key="drill_voltar"):
            subir()
            st.rerun()
        if b2.button("⟲ Início", use_container_width=True, key="drill_limpar"):
            limpar_trilha()
            st.rerun()


# ---------------------------------------------------------------------
# Barra lateral de filtros
# ---------------------------------------------------------------------


def barra_lateral() -> tuple[Filtros, str]:
    """Desenha os filtros globais e devolve (filtros, base de custo)."""
    op = opcoes()
    f = get_filtros()

    with st.sidebar:
        st.markdown("### Filtros globais")

        periodos = [p["ano_mes"] for p in op["periodos"]]
        if periodos:
            padrao_ini = f.periodo_inicio or periodos[0]
            padrao_fim = f.periodo_fim or periodos[-1]
            i_ini = periodos.index(padrao_ini) if padrao_ini in periodos else 0
            i_fim = periodos.index(padrao_fim) if padrao_fim in periodos else len(periodos) - 1
            c1, c2 = st.columns(2)
            f.periodo_inicio = c1.selectbox("De", periodos, index=i_ini, key="flt_ini")
            f.periodo_fim = c2.selectbox("Até", periodos, index=i_fim, key="flt_fim")

            atalhos = st.columns(4)
            if atalhos[0].button("12m", use_container_width=True, help="Últimos 12 meses"):
                f.periodo_inicio, f.periodo_fim = periodos[max(0, len(periodos) - 12)], periodos[-1]
                st.rerun()
            if atalhos[1].button("24m", use_container_width=True):
                f.periodo_inicio, f.periodo_fim = periodos[max(0, len(periodos) - 24)], periodos[-1]
                st.rerun()
            if atalhos[2].button("Ano", use_container_width=True, help="Ano corrente da base"):
                ano = periodos[-1][:4]
                f.periodo_inicio = next((p for p in periodos if p.startswith(ano)), periodos[0])
                f.periodo_fim = periodos[-1]
                st.rerun()
            if atalhos[3].button("Tudo", use_container_width=True):
                f.periodo_inicio, f.periodo_fim = periodos[0], periodos[-1]
                st.rerun()

        f.classificacoes = st.multiselect(
            "Classificação",
            [c["classificacao"] for c in op["classificacoes"]],
            default=f.classificacoes, key="flt_cla",
        )

        with st.expander("Produto, cliente e canal"):
            produtos = {p["descrprod"]: p["codprod"] for p in op["produtos"] if p["descrprod"]}
            escolhidos = st.multiselect(
                "Produto", list(produtos),
                default=[k for k, v in produtos.items() if v in f.produtos], key="flt_prod",
            )
            f.produtos = [produtos[p] for p in escolhidos]

            f.ramos = st.multiselect(
                "Ramo de atividade",
                [r["ramo_atividade"] for r in op["ramos"] if r["ramo_atividade"]],
                default=f.ramos, key="flt_ramo",
            )
            f.cif_fob = st.multiselect(
                "Modalidade de frete",
                [c["cif_fob"] for c in op["cif_fob"] if c["cif_fob"]],
                default=f.cif_fob, key="flt_cif",
            )
            f.empresas = st.multiselect(
                "Empresa", [e["codemp"] for e in op["empresas"]],
                default=f.empresas, key="flt_emp",
            )

        with st.expander("Território e equipe"):
            f.ufs = st.multiselect(
                "UF do cliente", [u["uf"] for u in op["ufs"] if u["uf"]],
                default=f.ufs, key="flt_uf",
                help="Geografia REAL do cliente — não confundir com região comercial.",
            )
            regioes = {r["nomereg"]: r["codreg"] for r in op["regioes"] if r["nomereg"]}
            reg_escolhidas = st.multiselect(
                "Região comercial", list(regioes),
                default=[k for k, v in regioes.items() if v in f.regioes], key="flt_reg",
                help="Atribuição comercial interna — não é a geografia do cliente.",
            )
            f.regioes = [regioes[r] for r in reg_escolhidas]

            f.papeis = st.multiselect(
                "Papel do vendedor",
                [p["papel_analitico"] for p in op["papeis"] if p["papel_analitico"]],
                default=f.papeis, key="flt_papel",
                help="Vem de config/seller_roles.yaml. Ainda NÃO homologado (Q-01).",
            )
            vendedores = {
                f"{v['apelido']} ({v['codvend']})": v["codvend"]
                for v in op["vendedores"] if v["apelido"]
            }
            vend_escolhidos = st.multiselect(
                "Vendedor", list(vendedores),
                default=[k for k, v in vendedores.items() if v in f.vendedores], key="flt_vend",
            )
            f.vendedores = [vendedores[v] for v in vend_escolhidos]

        st.markdown("---")
        modo_dev = st.radio(
            "Devoluções", ["Incluir", "Excluir", "Apenas devoluções"],
            index=0, horizontal=False, key="flt_dev",
        )
        f.incluir_devolucoes = modo_dev != "Excluir"
        f.apenas_devolucoes = modo_dev == "Apenas devoluções"

        st.markdown("---")
        st.markdown("### Base de custo")
        bases = (load_yaml("settings.yaml").get("custos") or {}).get("bases") or []
        rotulos = {b["label"]: b["id"] for b in bases}
        atual = get_base_custo()
        indice = next((i for i, b in enumerate(bases) if b["id"] == atual), 0)
        escolha = st.selectbox(
            "Conceito", list(rotulos), index=indice, key="flt_custo",
            help="Nenhum conceito é o custo oficial. A escolha muda a Margem Proxy.",
        )
        st.session_state.base_custo = rotulos[escolha]
        st.caption("⚠️ Conceitos de custo **não homologados** — margem é proxy (Q-04, Q-15).")

        st.markdown("---")
        if st.button("Limpar todos os filtros", use_container_width=True):
            st.session_state.filtros = Filtros()
            limpar_trilha()
            st.rerun()

        st.caption(f"Recorte ativo: {f.descricao()}")

    st.session_state.filtros = f
    return f, get_base_custo()


def cache_dados(ttl: int = TTL_CACHE):
    """Decorador de cache para consultas de pagina."""
    return st.cache_data(ttl=ttl, show_spinner="Consultando…")


def df_cache(fn):
    """
    Cacheia funcoes que devolvem polars.DataFrame.

    O Streamlit nao sabe hashear Filtros: convertemos para dict antes.
    """
    @st.cache_data(ttl=TTL_CACHE, show_spinner=False)
    def _inner(assinatura: str, *args, **kwargs) -> pl.DataFrame:
        return fn(*args, **kwargs)

    def wrapper(*args, **kwargs):
        assinatura = repr([
            a.__dict__ if isinstance(a, Filtros) else a for a in args
        ]) + repr(kwargs)
        return _inner(assinatura, *args, **kwargs)

    return wrapper
