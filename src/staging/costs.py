"""
fact_custo_pa e o as-of join temporal dos seis conceitos de custo.

Regra central (RN-07 / especificacao secao 15):
  O custo NAO e unido por CODPROD. Para cada item vendido, busca-se o custo
  vigente: maior DTATUAL <= data de referencia da venda.

Cascata (config/settings.yaml -> custos.asof.cascata):
  1. CODPROD + CODEMP + CODLOCAL   -> cost_match_status EXATO/ANTERIOR
  2. CODPROD + CODEMP              -> idem, nivel empresa
  3. CODPROD                       -> idem, nivel produto
  4. nada encontrado               -> SEM_CUSTO

O as-of roda no PostgreSQL com LATERAL: unir 204.037 itens a 29.135 custos em
memoria seria caro e menos auditavel que uma consulta que o consultor pode ler.
"""
from __future__ import annotations

import polars as pl
from sqlalchemy import text

from src.config import load_yaml
from src.db.engine import execute, get_connection, insert_dataframe, read_sql
from src.ingestion.loader import ler_parquet
from src.ingestion.readers import limpar_texto, para_data, para_decimal, para_inteiro
from src.logging_setup import logger

CUSTOS = ["cusmed", "cusmedicm", "cussemicm", "cusrep", "cusger", "cusvariavel"]


def construir_fact_custo_pa() -> int:
    custos = ler_parquet("custos_pa")

    df = (
        custos.select(
            para_inteiro("CODPROD").alias("codprod"),
            limpar_texto("PRODUTO").alias("produto"),
            para_inteiro("CODGRUPOPROD").alias("codgrupoprod"),
            limpar_texto("GRUPO_PRODUTO").alias("grupo_produto"),
            limpar_texto("UNIDADE").alias("unidade"),
            para_inteiro("CODEMP").alias("codemp"),
            para_inteiro("CODLOCAL").alias("codlocal"),
            para_data("DTATUAL").alias("dtatual"),
            para_decimal("CUSMED").alias("cusmed"),
            para_decimal("CUSMEDICM").alias("cusmedicm"),
            para_decimal("CUSSEMICM").alias("cussemicm"),
            para_decimal("CUSREP").alias("cusrep"),
            para_decimal("CUSGER").alias("cusger"),
            para_decimal("CUSVARIAVEL").alias("cusvariavel"),
        )
        .drop_nulls(["codprod", "dtatual"])
        .with_columns(
            pl.col("dtatual").dt.year().cast(pl.Int16).alias("ano"),
            pl.col("dtatual").dt.month().cast(pl.Int16).alias("mes"),
            pl.col("dtatual").dt.strftime("%Y-%m").alias("ano_mes"),
        )
        .sort(["codprod", "codemp", "codlocal", "dtatual"])
    )

    # Verificacao de grao (a especificacao pede validar unicidade no ETL)
    chave = ["codprod", "codemp", "codlocal", "dtatual"]
    dup = df.height - df.select(chave).unique().height
    if dup:
        logger.warning(
            f"fact_custo_pa: {dup} duplicata(s) em {chave}. "
            "Mantendo o ultimo registro de cada combinacao."
        )
        df = df.unique(subset=chave, keep="last")

    # Anomalia conhecida: custos negativos (RN-14). Carregados, nunca corrigidos.
    negativos = df.filter(
        pl.any_horizontal([pl.col(c) < 0 for c in CUSTOS])
    ).height
    if negativos:
        logger.warning(f"fact_custo_pa: {negativos} linha(s) com custo negativo (preservadas)")

    execute("TRUNCATE analytics.fact_custo_pa CASCADE")
    n = insert_dataframe(
        df.select(
            "codprod", "codemp", "codlocal", "dtatual", "ano", "mes", "ano_mes",
            "produto", "codgrupoprod", "grupo_produto", "unidade", *CUSTOS,
        ),
        "fact_custo_pa",
        "analytics",
    )
    logger.info(f"fact_custo_pa: {n:,} registros de custo".replace(",", "."))
    return n


# ---------------------------------------------------------------------
# As-of join
# ---------------------------------------------------------------------

_SQL_ASOF = """
WITH alvo AS (
    SELECT i.item_id, i.codprod, i.codemp, i.codlocalorig, i.data_referencia
    FROM analytics.fact_venda_item i
),
-- Nivel 1: produto + empresa + local
n1 AS (
    SELECT a.item_id, c.dtatual, {cols_c}, 1 AS nivel
    FROM alvo a
    CROSS JOIN LATERAL (
        SELECT * FROM analytics.fact_custo_pa c
        WHERE c.codprod = a.codprod
          AND c.codemp  = a.codemp
          AND c.codlocal = a.codlocalorig
          AND c.dtatual <= a.data_referencia
        ORDER BY c.dtatual DESC
        LIMIT 1
    ) c
),
-- Nivel 2: produto + empresa (a tabela de custo tem CODLOCAL=0, que as vendas nao usam)
n2 AS (
    SELECT a.item_id, c.dtatual, {cols_c}, 2 AS nivel
    FROM alvo a
    LEFT JOIN n1 ON n1.item_id = a.item_id
    CROSS JOIN LATERAL (
        SELECT * FROM analytics.fact_custo_pa c
        WHERE c.codprod = a.codprod
          AND c.codemp  = a.codemp
          AND c.dtatual <= a.data_referencia
        ORDER BY c.dtatual DESC
        LIMIT 1
    ) c
    WHERE n1.item_id IS NULL
),
-- Nivel 3: apenas produto
n3 AS (
    SELECT a.item_id, c.dtatual, {cols_c}, 3 AS nivel
    FROM alvo a
    LEFT JOIN n1 ON n1.item_id = a.item_id
    LEFT JOIN n2 ON n2.item_id = a.item_id
    CROSS JOIN LATERAL (
        SELECT * FROM analytics.fact_custo_pa c
        WHERE c.codprod = a.codprod
          AND c.dtatual <= a.data_referencia
        ORDER BY c.dtatual DESC
        LIMIT 1
    ) c
    WHERE n1.item_id IS NULL AND n2.item_id IS NULL
),
casado AS (
    SELECT * FROM n1
    UNION ALL SELECT * FROM n2
    UNION ALL SELECT * FROM n3
)
UPDATE analytics.fact_venda_item i
SET {sets},
    cost_match_date = k.dtatual,
    cost_age_days   = (i.data_referencia - k.dtatual),
    cost_match_status = CASE
        WHEN k.dtatual = i.data_referencia THEN 'EXATO'
        ELSE 'ANTERIOR'
    END
FROM casado k
WHERE k.item_id = i.item_id
"""


def aplicar_asof_custos() -> dict[str, int]:
    """
    Preenche os seis custos de cada item pelo custo vigente na data de
    referencia, registrando data, idade e status da correspondencia.
    """
    cfg = (load_yaml("settings.yaml").get("custos") or {}).get("asof") or {}
    idade_alerta = int(cfg.get("idade_maxima_alerta_dias", 90))

    cols_c = ", ".join(f"c.{c}" for c in CUSTOS)
    sets = ", ".join(f"{c} = k.{c}" for c in CUSTOS)
    sql = _SQL_ASOF.format(cols_c=cols_c, sets=sets)

    logger.info("Executando as-of join de custos (pode levar alguns minutos)...")
    with get_connection() as conn:
        conn.execute(text("SET LOCAL work_mem = '256MB'"))
        conn.exec_driver_sql(sql)

    # Itens que nao encontraram custo em nenhum nivel
    execute(
        """
        UPDATE analytics.fact_venda_item
        SET cost_match_status = CASE
                WHEN data_referencia IS NULL THEN 'SEM_DATA'
                ELSE 'SEM_CUSTO'
            END
        WHERE cost_match_status IS NULL
        """
    )

    resumo = read_sql(
        """
        SELECT cost_match_status AS status, COUNT(*) AS linhas,
               ROUND(AVG(cost_age_days), 1) AS idade_media,
               MAX(cost_age_days) AS idade_maxima
        FROM analytics.fact_venda_item
        GROUP BY cost_match_status ORDER BY linhas DESC
        """
    )
    total = int(resumo["linhas"].sum())
    for r in resumo.iter_rows(named=True):
        pct = 100 * r["linhas"] / total if total else 0
        logger.info(
            f"  as-of {r['status']}: {r['linhas']:,} ({pct:.2f}%) "
            f"idade media {r['idade_media']} d, maxima {r['idade_maxima']} d".replace(",", ".")
        )

    antigos = read_sql(
        "SELECT COUNT(*) AS n FROM analytics.fact_venda_item WHERE cost_age_days > :d",
        {"d": idade_alerta},
    )["n"][0]
    if antigos:
        logger.warning(
            f"{antigos:,} item(ns) com custo mais antigo que {idade_alerta} dias".replace(",", ".")
        )

    return {r["status"]: int(r["linhas"]) for r in resumo.iter_rows(named=True)}


def construir_custos() -> dict[str, int]:
    n = construir_fact_custo_pa()
    resumo = aplicar_asof_custos()
    return {"fact_custo_pa": n, **{f"asof_{k}": v for k, v in resumo.items()}}
