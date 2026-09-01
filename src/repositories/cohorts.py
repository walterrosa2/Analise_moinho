"""
Coortes de positivados e comportamento de clientes.

"Positivado" = mes da PRIMEIRA compra do cliente (RN-15, verificado: 2.871
vinculos para 2.871 clientes distintos). A tabela e, na pratica, o registro
de coortes de entrada.
"""
from __future__ import annotations

import polars as pl

from src.config import load_yaml
from src.db.engine import read_sql
from src.repositories.filters import Filtros


def _inicio_padrao() -> str:
    return (load_yaml("settings.yaml").get("positivados") or {}).get("analise_inicio", "2021-05")


def serie_positivados(incluir_implantacao: bool = False) -> pl.DataFrame:
    """Positivados por mes. Por padrao comeca apos a implantacao do ERP."""
    filtro = "" if incluir_implantacao else "WHERE NOT periodo_implantacao_erp"
    return read_sql(
        f"""
        SELECT ano_mes, ano, mes, qtd_positivados_fonte AS positivados,
               qtd_positivados_explodido, vlrtot_positivados, vlrtot_geral,
               perc_positivados_geral, periodo_implantacao_erp
        FROM analytics.fact_positivado_mes
        {filtro}
        ORDER BY ano_mes
        """
    )


def resumo_coortes(incluir_implantacao: bool = False) -> pl.DataFrame:
    """
    Uma linha por coorte de entrada, com recompra e receita acumulada.

    `taxa_recompra_pct` = clientes que voltaram a comprar em qualquer mes
    posterior ao da entrada.
    """
    filtro = "" if incluir_implantacao else "WHERE NOT c.periodo_implantacao_erp"
    return read_sql(
        f"""
        WITH base AS (
            SELECT c.coorte, c.codparc, c.periodo_implantacao_erp,
                   MAX(CASE WHEN c.meses_desde_entrada > 0 THEN 1 ELSE 0 END) AS recomprou,
                   COALESCE(SUM(c.receita), 0)                                AS receita_total,
                   COALESCE(SUM(c.receita) FILTER (WHERE c.meses_desde_entrada = 0), 0) AS receita_entrada,
                   COALESCE(SUM(c.ton), 0)                                    AS ton_total,
                   MAX(c.meses_desde_entrada)                                 AS ultimo_mes_ativo,
                   COUNT(DISTINCT c.mes_compra) FILTER (WHERE c.receita IS NOT NULL) AS meses_com_compra
            FROM analytics.mv_positivados_cohort c
            {filtro}
            GROUP BY c.coorte, c.codparc, c.periodo_implantacao_erp
        )
        SELECT coorte, periodo_implantacao_erp,
               COUNT(*)                                  AS clientes,
               SUM(recomprou)                            AS clientes_com_recompra,
               100.0 * SUM(recomprou) / NULLIF(COUNT(*), 0) AS taxa_recompra_pct,
               SUM(receita_total)                        AS receita_acumulada,
               SUM(receita_entrada)                      AS receita_primeira_compra,
               AVG(receita_total)                        AS receita_media_por_cliente,
               AVG(meses_com_compra)                     AS meses_ativos_medio,
               SUM(ton_total)                            AS ton_acumulada
        FROM base
        GROUP BY coorte, periodo_implantacao_erp
        ORDER BY coorte
        """
    )


def matriz_retencao(incluir_implantacao: bool = False, meses: int = 12) -> pl.DataFrame:
    """Matriz coorte x meses desde a entrada (% de clientes ainda comprando)."""
    filtro = "" if incluir_implantacao else "WHERE NOT periodo_implantacao_erp"
    return read_sql(
        f"""
        WITH tamanho AS (
            SELECT coorte, COUNT(DISTINCT codparc) AS clientes
            FROM analytics.mv_positivados_cohort {filtro}
            GROUP BY coorte
        ),
        ativos AS (
            SELECT coorte, meses_desde_entrada, COUNT(DISTINCT codparc) AS ativos
            FROM analytics.mv_positivados_cohort
            {filtro} {"AND" if not incluir_implantacao else "WHERE"}
                  meses_desde_entrada BETWEEN 0 AND :m AND receita IS NOT NULL
            GROUP BY coorte, meses_desde_entrada
        )
        SELECT a.coorte, a.meses_desde_entrada, a.ativos, t.clientes,
               100.0 * a.ativos / NULLIF(t.clientes, 0) AS retencao_pct
        FROM ativos a JOIN tamanho t ON t.coorte = a.coorte
        ORDER BY a.coorte, a.meses_desde_entrada
        """,
        {"m": meses},
    )


def recompra_por_janela(incluir_implantacao: bool = False) -> pl.DataFrame:
    """Taxa de recompra em 30/60/90/180/365 dias após a primeira compra."""
    filtro = "" if incluir_implantacao else "WHERE NOT p.periodo_implantacao_erp"
    return read_sql(
        f"""
        WITH entrada AS (
            SELECT p.codparc, p.ano_mes AS coorte, make_date(p.ano, p.mes, 1) AS data_entrada
            FROM analytics.fact_positivado p
            {filtro}
        ),
        compras AS (
            SELECT e.codparc, e.coorte, e.data_entrada,
                   MIN(i.data_referencia) FILTER (
                       WHERE i.data_referencia > e.data_entrada AND NOT i.is_devolucao
                   ) AS proxima_compra
            FROM entrada e
            LEFT JOIN analytics.fact_venda_item i ON i.codparc = e.codparc
            GROUP BY e.codparc, e.coorte, e.data_entrada
        )
        SELECT coorte,
               COUNT(*) AS clientes,
               COUNT(*) FILTER (WHERE proxima_compra - data_entrada <= 30)  AS recompra_30d,
               COUNT(*) FILTER (WHERE proxima_compra - data_entrada <= 60)  AS recompra_60d,
               COUNT(*) FILTER (WHERE proxima_compra - data_entrada <= 90)  AS recompra_90d,
               COUNT(*) FILTER (WHERE proxima_compra - data_entrada <= 180) AS recompra_180d,
               COUNT(*) FILTER (WHERE proxima_compra - data_entrada <= 365) AS recompra_365d,
               COUNT(*) FILTER (WHERE proxima_compra IS NULL)               AS sem_recompra
        FROM compras
        GROUP BY coorte ORDER BY coorte
        """
    )


def clientes_da_coorte(coorte: str) -> pl.DataFrame:
    """Lista de clientes de uma coorte, para o drill-down."""
    return read_sql(
        """
        SELECT c.codparc, cl.parceiro, cl.uf, cl.cidade, cl.ramo_atividade,
               cl.primeira_compra, cl.ultima_compra, cl.qtd_meses_ativos,
               COALESCE(SUM(c.receita), 0) AS receita_acumulada,
               COALESCE(SUM(c.ton), 0)     AS ton_acumulada,
               MAX(c.meses_desde_entrada)  AS ultimo_mes_ativo,
               v.apelido                   AS vendedor_atual
        FROM analytics.mv_positivados_cohort c
        LEFT JOIN analytics.dim_cliente cl ON cl.codparc = c.codparc
        LEFT JOIN LATERAL (
            SELECT codvend FROM analytics.fact_venda_item i
            WHERE i.codparc = c.codparc ORDER BY data_referencia DESC LIMIT 1
        ) ult ON TRUE
        LEFT JOIN analytics.dim_vendedor v ON v.codvend = ult.codvend
        WHERE c.coorte = :c
        GROUP BY c.codparc, cl.parceiro, cl.uf, cl.cidade, cl.ramo_atividade,
                 cl.primeira_compra, cl.ultima_compra, cl.qtd_meses_ativos, v.apelido
        ORDER BY receita_acumulada DESC
        """,
        {"c": coorte},
    )


# =====================================================================
# Clientes: RFM, ativos/novos/perdidos
# =====================================================================


def movimento_de_base(f: Filtros) -> pl.DataFrame:
    """
    Clientes ativos, novos, reativados e perdidos por mes.

    Definicoes (explicitas, para nao virarem convencao oculta):
      novo       = primeira compra da historia no mes
      reativado  = comprou no mes apos 6+ meses sem comprar
      perdido    = comprou no mes anterior e nao compra ha 6 meses
    """
    where, params = f.where({"periodo": "ano_mes"})
    return read_sql(
        f"""
        WITH mensal AS (
            SELECT codparc, ano_mes, MIN(data_referencia) AS primeira_no_mes
            FROM analytics.fact_venda_item
            WHERE NOT is_devolucao
            GROUP BY codparc, ano_mes
        ),
        com_lag AS (
            SELECT m.*,
                   LAG(ano_mes) OVER (PARTITION BY codparc ORDER BY ano_mes) AS mes_anterior,
                   MIN(ano_mes) OVER (PARTITION BY codparc)                  AS primeiro_mes
            FROM mensal m
        )
        SELECT ano_mes,
               COUNT(DISTINCT codparc)                                        AS ativos,
               COUNT(DISTINCT codparc) FILTER (WHERE ano_mes = primeiro_mes)  AS novos,
               COUNT(DISTINCT codparc) FILTER (
                   WHERE mes_anterior IS NOT NULL
                     AND (EXTRACT(YEAR FROM to_date(ano_mes,'YYYY-MM')) * 12
                        + EXTRACT(MONTH FROM to_date(ano_mes,'YYYY-MM')))
                       - (EXTRACT(YEAR FROM to_date(mes_anterior,'YYYY-MM')) * 12
                        + EXTRACT(MONTH FROM to_date(mes_anterior,'YYYY-MM'))) >= 6
               ) AS reativados
        FROM com_lag
        WHERE {where}
        GROUP BY ano_mes ORDER BY ano_mes
        """,
        params,
    )


def rfm(f: Filtros, limite: int = 2000) -> pl.DataFrame:
    """RFM simplificado: recencia (dias), frequencia (meses), valor (receita)."""
    where, params = f.where({
        "periodo": "i.ano_mes", "uf": "c.uf", "vendedor": "i.codvend",
        "cliente": "i.codparc", "ramo": "c.ramo_atividade", "regiao": "i.codreg",
    })
    return read_sql(
        f"""
        WITH base AS (
            SELECT i.codparc,
                   MAX(i.data_referencia)          AS ultima_compra,
                   COUNT(DISTINCT i.ano_mes)       AS meses_com_compra,
                   COUNT(DISTINCT i.nunota)        AS documentos,
                   SUM(i.vlrtot)                   AS receita,
                   SUM(i.tonliq)                   AS ton,
                   COUNT(DISTINCT i.codprod)       AS produtos
            FROM analytics.fact_venda_item i
            LEFT JOIN analytics.dim_cliente c ON c.codparc = i.codparc
            WHERE NOT i.is_devolucao AND {where}
            GROUP BY i.codparc
        ),
        referencia AS (SELECT MAX(data_referencia) AS hoje FROM analytics.fact_venda_item)
        SELECT b.codparc, c.parceiro, c.uf, c.cidade, c.ramo_atividade,
               b.ultima_compra, (r.hoje - b.ultima_compra) AS recencia_dias,
               b.meses_com_compra AS frequencia_meses, b.documentos,
               b.receita, b.ton, b.produtos,
               CASE WHEN b.documentos > 0 THEN b.receita / b.documentos END AS ticket_medio,
               NTILE(5) OVER (ORDER BY (r.hoje - b.ultima_compra) DESC) AS score_recencia,
               NTILE(5) OVER (ORDER BY b.meses_com_compra)              AS score_frequencia,
               NTILE(5) OVER (ORDER BY b.receita)                       AS score_valor
        FROM base b
        CROSS JOIN referencia r
        LEFT JOIN analytics.dim_cliente c ON c.codparc = b.codparc
        ORDER BY b.receita DESC
        LIMIT {int(limite)}
        """,
        params,
    )


def crescimento_clientes(f: Filtros, periodo_a, periodo_b, limite: int = 500) -> pl.DataFrame:
    """Matriz crescimento x contribuição: onde o consultor deve olhar primeiro."""
    from src.repositories.sales import comparar_periodos

    df = comparar_periodos(f, "cliente", periodo_a, periodo_b)
    if df.height == 0:
        return df
    total_b = float(df["valor_b"].sum() or 0)
    return df.with_columns(
        (100 * pl.col("valor_b") / total_b if total_b else pl.lit(None)).alias("participacao_pct")
    ).sort("valor_b", descending=True).head(limite)
