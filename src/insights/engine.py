"""
Motor de insights quantitativos.

Regras determinísticas sobre os dados — sem LLM. Cada insight carrega a
consulta que o originou, para que a interface ofereça "Ver evidência".

O motor descreve o que os números mostram. Ele não julga pessoas nem
recomenda demissão, e nunca chama correlação de causalidade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl

from src.config import load_yaml
from src.repositories.filters import Filtros
from src.repositories.sales import comparar_periodos, por_dimensao


@dataclass
class Insight:
    id: str
    categoria: str
    titulo: str
    descricao: str
    severidade: str = "INFO"        # INFO | ATENCAO | ALERTA
    metrica: str = ""
    valor_atual: float | None = None
    valor_comparacao: float | None = None
    variacao: float | None = None
    dimensoes: dict[str, Any] = field(default_factory=dict)
    evidencia: pl.DataFrame | None = None
    periodo: str = ""

    @property
    def icone(self) -> str:
        return {"ALERTA": "🔴", "ATENCAO": "🟡", "INFO": "🔵"}.get(self.severidade, "🔵")


def _cfg() -> dict[str, Any]:
    return load_yaml("settings.yaml").get("insights") or {}


def _fmt_moeda(v: float | None) -> str:
    if v is None:
        return "—"
    sinal = "-" if v < 0 else ""
    valor = abs(v)
    if valor >= 1e6:
        return f"{sinal}R$ {valor / 1e6:,.2f} mi".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{sinal}R$ {valor:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{v:,.1f}%".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


# =====================================================================
# Regras
# =====================================================================


def crescimento_e_queda(
    f: Filtros, periodo_a: tuple[str, str], periodo_b: tuple[str, str],
    dimensao: str = "classificacao", top_n: int = 3,
) -> list[Insight]:
    """Maiores crescimentos e quedas, com a contribuição de cada um."""
    cfg = _cfg()
    minimo = float(cfg.get("variacao_minima_relevante_pct", 10.0))
    df = comparar_periodos(f, dimensao, periodo_a, periodo_b)
    if df.height == 0:
        return []

    rotulo_periodo = f"{periodo_b[0]}..{periodo_b[1]} vs {periodo_a[0]}..{periodo_a[1]}"
    out: list[Insight] = []

    altas = df.filter(
        (pl.col("variacao") > 0) & (pl.col("variacao_pct").abs() >= minimo)
    ).head(top_n)
    quedas = df.filter(
        (pl.col("variacao") < 0) & (pl.col("variacao_pct").abs() >= minimo)
    ).sort("variacao").head(top_n)

    for r in altas.iter_rows(named=True):
        out.append(Insight(
            id=f"crescimento_{dimensao}_{r['chave']}",
            categoria="CRESCIMENTO",
            titulo=f"{r['rotulo']} cresceu {_fmt_pct(r['variacao_pct'])}",
            descricao=(
                f"Receita passou de {_fmt_moeda(r['valor_a'])} para {_fmt_moeda(r['valor_b'])} "
                f"({_fmt_moeda(r['variacao'])}). Efeito volume {_fmt_moeda(r['efeito_volume'])}, "
                f"efeito preço {_fmt_moeda(r['efeito_preco'])}."
            ),
            severidade="INFO",
            metrica="receita_liquida",
            valor_atual=r["valor_b"], valor_comparacao=r["valor_a"],
            variacao=r["variacao_pct"],
            dimensoes={dimensao: r["rotulo"]},
            evidencia=df, periodo=rotulo_periodo,
        ))

    for r in quedas.iter_rows(named=True):
        out.append(Insight(
            id=f"queda_{dimensao}_{r['chave']}",
            categoria="QUEDA",
            titulo=f"{r['rotulo']} caiu {_fmt_pct(abs(r['variacao_pct'] or 0))}",
            descricao=(
                f"Receita passou de {_fmt_moeda(r['valor_a'])} para {_fmt_moeda(r['valor_b'])} "
                f"({_fmt_moeda(r['variacao'])}). Efeito volume {_fmt_moeda(r['efeito_volume'])}, "
                f"efeito preço {_fmt_moeda(r['efeito_preco'])} — a decomposição indica se a "
                f"queda foi de quantidade ou de preço."
            ),
            severidade="ALERTA" if abs(r["variacao_pct"] or 0) > 25 else "ATENCAO",
            metrica="receita_liquida",
            valor_atual=r["valor_b"], valor_comparacao=r["valor_a"],
            variacao=r["variacao_pct"],
            dimensoes={dimensao: r["rotulo"]},
            evidencia=df, periodo=rotulo_periodo,
        ))
    return out


def concentracao(f: Filtros, dimensao: str = "cliente", top: int = 5) -> list[Insight]:
    """Pareto: quanto os N maiores representam do total."""
    cfg = _cfg()
    limite = float(cfg.get("concentracao_alerta_pct", 50.0))
    df = por_dimensao(f, dimensao, ordenar_por="receita_liquida")
    if df.height <= top:
        return []

    total = float(df["receita_liquida"].sum() or 0)
    if total <= 0:
        return []
    topo = df.head(top)
    parte = float(topo["receita_liquida"].sum() or 0)
    pct = 100 * parte / total

    nomes = {"cliente": "clientes", "vendedor": "vendedores", "produto": "produtos",
             "regiao": "regiões", "uf": "UFs"}.get(dimensao, dimensao)
    return [Insight(
        id=f"concentracao_{dimensao}",
        categoria="CONCENTRACAO",
        titulo=f"Top {top} {nomes} concentram {_fmt_pct(pct)} da receita",
        descricao=(
            f"{_fmt_moeda(parte)} de {_fmt_moeda(total)}, distribuídos entre {df.height} "
            f"{nomes} no recorte. Concentração é um fato de estrutura, não um problema "
            f"em si — mas define o risco de dependência."
        ),
        severidade="ATENCAO" if pct >= limite else "INFO",
        metrica="receita_liquida",
        valor_atual=pct,
        dimensoes={"dimensao": dimensao, "top": top},
        evidencia=topo,
    )]


def mudanca_de_mix(
    f: Filtros, periodo_a: tuple[str, str], periodo_b: tuple[str, str]
) -> list[Insight]:
    """Classificações que ganharam ou perderam participação em toneladas."""
    df = comparar_periodos(f, "classificacao", periodo_a, periodo_b)
    if df.height == 0:
        return []

    tot_a = float(df["ton_a"].sum() or 0)
    tot_b = float(df["ton_b"].sum() or 0)
    if not tot_a or not tot_b:
        return []

    df = df.with_columns(
        (100 * pl.col("ton_a") / tot_a).alias("share_a"),
        (100 * pl.col("ton_b") / tot_b).alias("share_b"),
    ).with_columns((pl.col("share_b") - pl.col("share_a")).alias("delta_share"))

    out = []
    for r in df.sort(pl.col("delta_share").abs(), descending=True).head(2).iter_rows(named=True):
        if abs(r["delta_share"] or 0) < 1:
            continue
        sentido = "ganhou" if r["delta_share"] > 0 else "perdeu"
        out.append(Insight(
            id=f"mix_{r['chave']}",
            categoria="MIX",
            titulo=f"{r['rotulo']} {sentido} {_fmt_pct(abs(r['delta_share']))} de participação em volume",
            descricao=(
                f"Participação passou de {_fmt_pct(r['share_a'])} para {_fmt_pct(r['share_b'])} "
                f"das toneladas. Mudança de mix altera o PMV consolidado mesmo sem alteração "
                f"de preço em nenhum produto."
            ),
            severidade="ATENCAO" if abs(r["delta_share"]) >= 3 else "INFO",
            metrica="volume_liquido_t",
            valor_atual=r["share_b"], valor_comparacao=r["share_a"],
            variacao=r["delta_share"],
            dimensoes={"classificacao": r["rotulo"]},
            evidencia=df.select("rotulo", "ton_a", "ton_b", "share_a", "share_b", "delta_share"),
        ))
    return out


def clientes_em_retracao(f: Filtros, periodo_a, periodo_b, top_n: int = 5) -> list[Insight]:
    """Clientes relevantes com queda forte de receita."""
    cfg = _cfg()
    limite = float(cfg.get("queda_cliente_alerta_pct", 30.0))
    df = comparar_periodos(f, "cliente", periodo_a, periodo_b)
    if df.height == 0:
        return []

    total_a = float(df["valor_a"].sum() or 0)
    relevantes = df.filter(
        (pl.col("valor_a") > 0.002 * total_a)          # ignora cauda irrelevante
        & (pl.col("variacao_pct") <= -limite)
    ).sort("variacao").head(top_n)
    if relevantes.height == 0:
        return []

    perda = float(relevantes["variacao"].sum() or 0)
    return [Insight(
        id="clientes_retracao",
        categoria="CLIENTES",
        titulo=f"{relevantes.height} cliente(s) relevante(s) com queda acima de {_fmt_pct(limite)}",
        descricao=(
            f"Juntos representam {_fmt_moeda(perda)} de retração. "
            f"Maior queda: {relevantes['rotulo'][0]} "
            f"({_fmt_pct(relevantes['variacao_pct'][0])})."
        ),
        severidade="ALERTA",
        metrica="receita_liquida",
        valor_atual=perda,
        evidencia=relevantes.select("rotulo", "valor_a", "valor_b", "variacao", "variacao_pct"),
    )]


def rca_com_perda_de_clientes(f: Filtros, periodo_a, periodo_b) -> list[Insight]:
    """Vendedores que perderam base de clientes."""
    a = por_dimensao(
        Filtros(**{**f.__dict__, "periodo_inicio": periodo_a[0], "periodo_fim": periodo_a[1]}),
        "vendedor",
    ).select("chave", "rotulo", pl.col("clientes").alias("clientes_a"),
             pl.col("receita_liquida").alias("receita_a"))
    b = por_dimensao(
        Filtros(**{**f.__dict__, "periodo_inicio": periodo_b[0], "periodo_fim": periodo_b[1]}),
        "vendedor",
    ).select("chave", "rotulo", pl.col("clientes").alias("clientes_b"),
             pl.col("receita_liquida").alias("receita_b"))
    if a.height == 0 or b.height == 0:
        return []

    df = a.join(b, on=["chave", "rotulo"], how="inner").with_columns(
        (pl.col("clientes_b") - pl.col("clientes_a")).alias("delta_clientes"),
        (100 * (pl.col("clientes_b") - pl.col("clientes_a")) / pl.col("clientes_a")).alias("delta_pct"),
    )
    piores = df.filter((pl.col("delta_clientes") < 0) & (pl.col("clientes_a") >= 10)).sort("delta_pct").head(3)
    if piores.height == 0:
        return []

    r = piores.to_dicts()[0]
    return [Insight(
        id="rca_perda_clientes",
        categoria="RCA",
        titulo=f"{r['rotulo']} perdeu {abs(int(r['delta_clientes']))} clientes ativos",
        descricao=(
            f"Base passou de {int(r['clientes_a'])} para {int(r['clientes_b'])} clientes "
            f"({_fmt_pct(r['delta_pct'])}). Receita: {_fmt_moeda(r['receita_a'])} → "
            f"{_fmt_moeda(r['receita_b'])}. "
            f"O dado mostra performance inferior ao grupo comparável; avaliar esforço e "
            f"contexto exige informação que a base não contém."
        ),
        severidade="ATENCAO",
        metrica="clientes_ativos",
        valor_atual=r["clientes_b"], valor_comparacao=r["clientes_a"],
        variacao=r["delta_pct"],
        evidencia=piores,
    )]


def rota_cara(f: Filtros) -> list[Insight]:
    """Rotas com R$/t acima do percentil 90 do conjunto."""
    from src.repositories.logistics import rotas

    df = rotas(f)
    if df.height < 10:
        return []
    validas = df.filter(pl.col("frete_por_ton").is_not_null() & (pl.col("ton") > 1))
    if validas.height < 10:
        return []

    p90 = float(validas["frete_por_ton"].quantile(0.9) or 0)
    caras = validas.filter(pl.col("frete_por_ton") > p90).sort("frete", descending=True).head(5)
    if caras.height == 0:
        return []

    return [Insight(
        id="rota_cara",
        categoria="LOGISTICA",
        titulo=f"{caras.height} rota(s) acima do percentil 90 de frete por tonelada",
        descricao=(
            f"O percentil 90 do recorte é {_fmt_moeda(p90)}/t. A rota mais cara em valor "
            f"absoluto é {caras['rota'][0]}, com "
            f"{_fmt_moeda(caras['frete_por_ton'][0])}/t. "
            f"Distância e perfil de carga explicam parte da diferença — o número indica "
            f"onde olhar, não uma conclusão."
        ),
        severidade="ATENCAO",
        metrica="frete_por_ton",
        valor_atual=float(caras["frete_por_ton"][0] or 0),
        valor_comparacao=p90,
        evidencia=caras,
    )]


def custo_crescendo_mais_que_pmv(f: Filtros, base_custo: str = "cusger") -> list[Insight]:
    """Produtos em que o custo subiu mais rápido que o preço."""
    from src.repositories.costs import evolucao_custo_pmv_produto

    df = evolucao_custo_pmv_produto(f, base_custo)
    if df.height == 0:
        return []
    piores = df.filter(
        pl.col("var_custo_pct").is_not_null() & pl.col("var_pmv_pct").is_not_null()
        & (pl.col("var_custo_pct") > pl.col("var_pmv_pct") + 5)
    ).sort(pl.col("var_custo_pct") - pl.col("var_pmv_pct"), descending=True).head(5)
    if piores.height == 0:
        return []

    r = piores.to_dicts()[0]
    return [Insight(
        id="custo_acima_pmv",
        categoria="CUSTOS",
        titulo=f"{piores.height} produto(s) com custo subindo mais que o preço",
        descricao=(
            f"Maior descolamento: {r['descrprod']} — custo {_fmt_pct(r['var_custo_pct'])} "
            f"contra PMV {_fmt_pct(r['var_pmv_pct'])} no período. "
            f"Base de custo: {base_custo.upper()} (conceito não homologado)."
        ),
        severidade="ATENCAO",
        metrica=f"margem_proxy_{base_custo}",
        valor_atual=r["var_custo_pct"], valor_comparacao=r["var_pmv_pct"],
        evidencia=piores,
    )]


def coorte_sem_recompra(f: Filtros) -> list[Insight]:
    """Coortes de positivados com baixa taxa de segunda compra."""
    from src.repositories.cohorts import resumo_coortes

    df = resumo_coortes(incluir_implantacao=False)
    if df.height == 0:
        return []
    recentes = df.sort("coorte", descending=True).head(13).tail(12)
    if recentes.height == 0:
        return []

    media = float(recentes["taxa_recompra_pct"].mean() or 0)
    piores = recentes.filter(pl.col("taxa_recompra_pct") < media * 0.7).sort("taxa_recompra_pct")
    if piores.height == 0:
        return []

    r = piores.to_dicts()[0]
    return [Insight(
        id="coorte_baixa_recompra",
        categoria="POSITIVADOS",
        titulo=f"Coorte {r['coorte']} tem recompra de {_fmt_pct(r['taxa_recompra_pct'])}",
        descricao=(
            f"Contra média de {_fmt_pct(media)} nas coortes recentes. "
            f"{int(r['clientes'])} clientes entraram nesse mês e "
            f"{int(r['clientes_com_recompra'])} voltaram a comprar."
        ),
        severidade="ATENCAO",
        metrica="clientes_novos",
        valor_atual=r["taxa_recompra_pct"], valor_comparacao=media,
        evidencia=recentes,
    )]


# =====================================================================
# Orquestração
# =====================================================================


def gerar(
    f: Filtros,
    periodo_a: tuple[str, str],
    periodo_b: tuple[str, str],
    base_custo: str = "cusger",
) -> list[Insight]:
    """Roda todas as regras. Falha de uma regra não derruba as demais."""
    insights: list[Insight] = []
    regras = [
        lambda: crescimento_e_queda(f, periodo_a, periodo_b, "classificacao"),
        lambda: crescimento_e_queda(f, periodo_a, periodo_b, "regiao", top_n=2),
        lambda: mudanca_de_mix(f, periodo_a, periodo_b),
        lambda: concentracao(f, "cliente", 5),
        lambda: concentracao(f, "vendedor", 3),
        lambda: clientes_em_retracao(f, periodo_a, periodo_b),
        lambda: rca_com_perda_de_clientes(f, periodo_a, periodo_b),
        lambda: rota_cara(f),
        lambda: custo_crescendo_mais_que_pmv(f, base_custo),
        lambda: coorte_sem_recompra(f),
    ]
    for regra in regras:
        try:
            insights.extend(regra())
        except Exception:  # noqa: BLE001 — um insight que falha não invalida os outros
            continue

    ordem = {"ALERTA": 0, "ATENCAO": 1, "INFO": 2}
    return sorted(insights, key=lambda i: ordem.get(i.severidade, 3))
