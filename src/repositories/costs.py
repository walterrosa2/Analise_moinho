"""
Consultas de custo e margem proxy.

Regra permanente: nenhum conceito de custo e "o custo". Toda diferenca entre
preco e custo e MARGEM PROXY, e a base usada aparece sempre no rotulo.
"""
from __future__ import annotations

import polars as pl

from src.db.engine import read_sql
from src.metrics.registry import bases_custo
from src.repositories.filters import COLUNAS_VENDA_ITEM, Filtros

CUSTOS = [b[0] for b in bases_custo()]


def serie_custo_pmv(f: Filtros, base_custo: str = "cusger") -> pl.DataFrame:
    """PMV x custo por tonelada, mes a mes."""
    where, params = f.where(COLUNAS_VENDA_ITEM)
    return read_sql(
        f"""
        SELECT ano_mes,
               SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
               SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT custo_outlier), 0)  AS custo_por_ton,
               SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                 - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier) AS margem_proxy,
               CASE WHEN SUM(vlrtot) FILTER (WHERE NOT custo_outlier) <> 0
                    THEN 100 * (SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                              - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier))
                       / SUM(vlrtot) FILTER (WHERE NOT custo_outlier) END   AS margem_proxy_pct,
               SUM(tonliq)                                                  AS ton,
               COUNT(*) FILTER (WHERE custo_outlier)                        AS linhas_outlier
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY ano_mes ORDER BY ano_mes
        """,
        params,
    )


def comparar_bases(f: Filtros) -> pl.DataFrame:
    """Todos os seis conceitos lado a lado, por mes (modo 'Comparar todos')."""
    where, params = f.where(COLUNAS_VENDA_ITEM)
    colunas = ",\n".join(
        f"""SUM(qtd * {c}) FILTER (WHERE NOT custo_outlier)
              / NULLIF(SUM(tonliq) FILTER (WHERE NOT custo_outlier), 0) AS {c}"""
        for c in CUSTOS
    )
    return read_sql(
        f"""
        SELECT ano_mes,
               SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
               {colunas}
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY ano_mes ORDER BY ano_mes
        """,
        params,
    )


def por_produto(f: Filtros, base_custo: str = "cusger", limite: int = 100) -> pl.DataFrame:
    where, params = f.where(COLUNAS_VENDA_ITEM)
    return read_sql(
        f"""
        SELECT codprod, descrprod, classificacao, unidade_produto,
               SUM(tonliq)                                                  AS ton,
               SUM(qtd)                                                     AS quantidade,
               SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
               SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT custo_outlier), 0)  AS custo_por_ton,
               AVG({base_custo}) FILTER (WHERE NOT custo_outlier)           AS custo_unitario_medio,
               AVG(vlrunit)                                                 AS preco_unitario_medio,
               SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                 - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier) AS margem_proxy,
               CASE WHEN SUM(vlrtot) FILTER (WHERE NOT custo_outlier) <> 0
                    THEN 100 * (SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                              - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier))
                       / SUM(vlrtot) FILTER (WHERE NOT custo_outlier) END   AS margem_proxy_pct,
               SUM(vlrtot)                                                  AS receita,
               COUNT(*) FILTER (WHERE custo_outlier)                        AS linhas_outlier
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY codprod, descrprod, classificacao, unidade_produto
        HAVING SUM(tonliq) <> 0
        ORDER BY receita DESC NULLS LAST
        LIMIT {int(limite)}
        """,
        params,
    )


def dispersao_entre_bases(f: Filtros, limite: int = 60) -> pl.DataFrame:
    """
    Produtos com maior diferenca entre os conceitos de custo.

    Quanto maior a dispersao, mais a escolha da base muda o resultado — e mais
    urgente e a homologacao pela Controladoria.
    """
    where, params = f.where(COLUNAS_VENDA_ITEM)
    medias = ",\n".join(
        f"AVG({c}) FILTER (WHERE NOT custo_outlier) AS {c}" for c in CUSTOS
    )
    df = read_sql(
        f"""
        SELECT codprod, descrprod, classificacao, {medias},
               SUM(vlrtot) AS receita
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY codprod, descrprod, classificacao
        HAVING SUM(vlrtot) <> 0
        ORDER BY receita DESC
        LIMIT {int(limite)}
        """,
        params,
    )
    if df.height == 0:
        return df
    return df.with_columns(
        pl.min_horizontal(CUSTOS).alias("custo_minimo"),
        pl.max_horizontal(CUSTOS).alias("custo_maximo"),
    ).with_columns(
        (pl.col("custo_maximo") - pl.col("custo_minimo")).alias("amplitude"),
        pl.when(pl.col("custo_minimo") > 0)
        .then(100 * (pl.col("custo_maximo") - pl.col("custo_minimo")) / pl.col("custo_minimo"))
        .otherwise(None)
        .alias("amplitude_pct"),
    ).sort("amplitude_pct", descending=True, nulls_last=True)


def evolucao_custo_pmv_produto(f: Filtros, base_custo: str = "cusger") -> pl.DataFrame:
    """
    Variação do custo x variação do PMV por produto, entre a primeira e a
    última metade do período filtrado. Base do insight 'custo acima do PMV'.
    """
    where, params = f.where(COLUNAS_VENDA_ITEM)
    df = read_sql(
        f"""
        WITH base AS (
            SELECT codprod, descrprod, ano_mes,
                   SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                     / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
                   AVG({base_custo}) FILTER (WHERE NOT custo_outlier) AS custo,
                   SUM(vlrtot) AS receita
            FROM analytics.v_venda_item
            WHERE {where}
            GROUP BY codprod, descrprod, ano_mes
        ),
        ordenado AS (
            SELECT *, NTILE(2) OVER (PARTITION BY codprod ORDER BY ano_mes) AS metade
            FROM base
        )
        SELECT codprod, descrprod,
               AVG(pmv)   FILTER (WHERE metade = 1) AS pmv_inicio,
               AVG(pmv)   FILTER (WHERE metade = 2) AS pmv_fim,
               AVG(custo) FILTER (WHERE metade = 1) AS custo_inicio,
               AVG(custo) FILTER (WHERE metade = 2) AS custo_fim,
               SUM(receita) AS receita
        FROM ordenado
        GROUP BY codprod, descrprod
        HAVING SUM(receita) <> 0
        """,
        params,
    )
    if df.height == 0:
        return df
    return df.with_columns(
        pl.when(pl.col("pmv_inicio") > 0)
        .then(100 * (pl.col("pmv_fim") - pl.col("pmv_inicio")) / pl.col("pmv_inicio"))
        .alias("var_pmv_pct"),
        pl.when(pl.col("custo_inicio") > 0)
        .then(100 * (pl.col("custo_fim") - pl.col("custo_inicio")) / pl.col("custo_inicio"))
        .alias("var_custo_pct"),
    ).sort("receita", descending=True)


def custo_historico_produto(codprod: int) -> pl.DataFrame:
    """Serie completa de todos os conceitos para um produto."""
    return read_sql(
        """
        SELECT ano_mes, codprod, produto, grupo_produto,
               cusmed, cusmedicm, cussemicm, cusrep, cusger, cusvariavel,
               registros, primeira_data, ultima_data
        FROM analytics.mv_cost_product_month
        WHERE codprod = :p ORDER BY ano_mes
        """,
        {"p": codprod},
    )
