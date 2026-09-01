"""
fact_cte, bridge_cte_nfe e rateio do frete por tonelagem.

Regras materializadas aqui (RN-08):
  - CHAVECTE e unica quando existe, mas falta em 1.134 CT-e (3,46%);
    NUNOTA repete 4x -> PK e o surrogate frete_id.
  - Um CT-e cobre N notas: CHAVES_NFE_VENDA e lista separada por ';'.
  - ORDEMCARGA e invalida em 55,89% dos CT-e -> nunca e chave unica.
  - Frete rateado por tonelagem (TON_WEIGHT); sem tonelagem, EQUAL_SPLIT.
  - O que nao casa fica SEM_VINCULO e aparece no indicador de % nao alocado.
    Nada e escondido.
"""
from __future__ import annotations

import polars as pl

from src.config import load_yaml
from src.db.engine import execute, insert_dataframe, read_sql
from src.ingestion.loader import ler_parquet
from src.ingestion.readers import limpar_texto, para_data, para_decimal, para_inteiro
from src.logging_setup import logger


def construir_fact_cte() -> pl.DataFrame:
    cte = ler_parquet("cte")
    cfg = load_yaml("settings.yaml").get("operacoes") or {}
    nao_frete_venda = set(cfg.get("cte_nao_frete_venda") or [])
    anulado = set(cfg.get("cte_anulado") or [])

    df = (
        cte.select(
            para_inteiro("CODEMP").alias("codemp"),
            para_inteiro("NUNOTA").alias("nunota"),
            para_inteiro("NUMNOTA").alias("numnota"),
            limpar_texto("SERIENOTA").alias("serienota"),
            para_data("DTNEG").alias("dtneg"),
            para_data("DTENTSAI").alias("dtentsai"),
            para_data("DTFATUR").alias("dtfatur"),
            para_inteiro("CODTIPOPER").alias("codtipoper"),
            limpar_texto("DESCROPER").alias("descroper"),
            limpar_texto("CHAVECTE").alias("chavecte"),
            para_inteiro("ORDEMCARGA").alias("ordemcarga"),
            para_inteiro("CODPARC").alias("codparc"),
            limpar_texto("NOMEPARC").alias("nomeparc"),
            para_decimal("VLRNOTA").alias("vlrnota"),
            limpar_texto("NOTAS_VENDA").alias("notas_venda"),
            limpar_texto("CHAVES_NFE_VENDA").alias("chaves_nfe_venda"),
        )
        .with_columns(
            pl.coalesce(pl.col("dtfatur"), pl.col("dtneg"), pl.col("dtentsai")).alias("data_referencia")
        )
        .with_columns(
            pl.col("data_referencia").dt.year().cast(pl.Int16).alias("ano"),
            pl.col("data_referencia").dt.month().cast(pl.Int16).alias("mes"),
            pl.col("data_referencia").dt.strftime("%Y-%m").alias("ano_mes"),
        )
        .with_row_index("frete_id", offset=1)
        .with_columns(pl.col("frete_id").cast(pl.Int64))
    )

    n_nao_venda = df.filter(pl.col("codtipoper").is_in(list(nao_frete_venda))).height
    n_anulado = df.filter(pl.col("codtipoper").is_in(list(anulado))).height
    if n_nao_venda:
        logger.warning(f"fact_cte: {n_nao_venda} CT-e que nao sao frete de venda (Q-09)")
    if n_anulado:
        logger.warning(f"fact_cte: {n_anulado} CT-e anulado(s)")

    # qtd_nfe_vinculadas e recalculado depois da explosao
    grav = df.select(
        "frete_id", "codemp", "nunota", "numnota", "serienota", "dtneg", "dtentsai",
        "dtfatur", "data_referencia", "ano", "mes", "ano_mes", "codtipoper",
        "descroper", "chavecte", "ordemcarga", "codparc", "nomeparc", "vlrnota",
    ).with_columns(pl.lit(0, dtype=pl.Int32).alias("qtd_nfe_vinculadas"))

    execute("TRUNCATE analytics.fact_cte CASCADE")
    n = insert_dataframe(grav, "fact_cte", "analytics")
    logger.info(f"fact_cte: {n:,} conhecimentos de transporte".replace(",", "."))
    return df


def construir_bridge(cte: pl.DataFrame) -> int:
    """
    Explode CHAVES_NFE_VENDA, resolve o vinculo com a venda e rateia o frete.

    Ordem de resolucao do vinculo:
      1. chave NF-e -> fact_venda_documento.chavenfe   (NFE_OK)
      2. numero da nota -> numnota                     (NOTA_OK)
      3. sem correspondencia                           (SEM_VINCULO)
    """
    # 1) Explosao das listas
    com_chave = (
        cte.filter(pl.col("chaves_nfe_venda").is_not_null())
        .with_columns(
            pl.col("chaves_nfe_venda").str.split(";").alias("_chaves"),
            pl.col("notas_venda").fill_null("").str.split(";").alias("_notas"),
        )
        .explode("_chaves")
        .with_columns(pl.col("_chaves").str.strip_chars().alias("chave_nfe"))
        .filter(pl.col("chave_nfe").str.len_chars() > 0)
        .select("frete_id", "chavecte", "chave_nfe", "vlrnota", "ordemcarga")
    )

    # Numero da nota citado, quando existe (lista paralela)
    notas = (
        cte.filter(pl.col("notas_venda").is_not_null())
        .with_columns(pl.col("notas_venda").str.split(";").alias("_n"))
        .explode("_n")
        .with_columns(pl.col("_n").str.strip_chars().alias("numero_nota_venda"))
        .filter(pl.col("numero_nota_venda").str.len_chars() > 0)
        .select("frete_id", "numero_nota_venda")
        .group_by("frete_id")
        .agg(pl.col("numero_nota_venda").first())
    )

    sem_chave = cte.filter(pl.col("chaves_nfe_venda").is_null()).select(
        "frete_id", "chavecte", "vlrnota", "ordemcarga"
    ).with_columns(pl.lit(None, dtype=pl.Utf8).alias("chave_nfe"))

    bridge = pl.concat(
        [com_chave, sem_chave.select(com_chave.columns)], how="vertical"
    ).join(notas, on="frete_id", how="left")

    # 2) Resolucao contra a venda
    docs = read_sql(
        """
        SELECT d.nunota AS nunota_venda, d.chavenfe, d.numnota,
               COALESCE(t.ton, 0) AS ton_nfe
        FROM analytics.fact_venda_documento d
        LEFT JOIN (
            SELECT nunota, SUM(tonliq) AS ton
            FROM analytics.fact_venda_item GROUP BY nunota
        ) t ON t.nunota = d.nunota
        """
    )
    por_chave = docs.filter(pl.col("chavenfe").is_not_null()).select(
        pl.col("chavenfe").alias("chave_nfe"),
        pl.col("nunota_venda").alias("_nunota_por_chave"),
        pl.col("ton_nfe").alias("_ton_por_chave"),
    ).unique(subset=["chave_nfe"], keep="first")

    bridge = bridge.join(por_chave, on="chave_nfe", how="left")

    por_numero = (
        docs.filter(pl.col("numnota").is_not_null())
        .select(
            pl.col("numnota").cast(pl.Utf8).alias("numero_nota_venda"),
            pl.col("nunota_venda").alias("_nunota_por_numero"),
            pl.col("ton_nfe").alias("_ton_por_numero"),
        )
        .unique(subset=["numero_nota_venda"], keep="first")
    )
    bridge = bridge.with_columns(
        # '000233885' -> '233885'
        pl.col("numero_nota_venda").str.strip_chars().str.strip_chars_start("0").alias("_num_limpo")
    ).join(
        por_numero.rename({"numero_nota_venda": "_num_limpo"}), on="_num_limpo", how="left"
    )

    bridge = bridge.with_columns(
        pl.coalesce("_nunota_por_chave", "_nunota_por_numero").alias("nunota_venda"),
        pl.coalesce("_ton_por_chave", "_ton_por_numero").alias("ton_nfe"),
    ).with_columns(
        pl.when(pl.col("_nunota_por_chave").is_not_null())
        .then(pl.lit("NFE_OK"))
        .when(pl.col("_nunota_por_numero").is_not_null())
        .then(pl.lit("NOTA_OK"))
        .otherwise(pl.lit("SEM_VINCULO"))
        .alias("match_status")
    )

    # 3) Rateio por tonelagem dentro de cada CT-e
    cfg = load_yaml("settings.yaml").get("logistica") or {}
    metodo = cfg.get("metodo_rateio_padrao", "TON_WEIGHT")
    fallback = cfg.get("metodo_rateio_fallback", "EQUAL_SPLIT")

    validos = pl.col("match_status") != "SEM_VINCULO"
    bridge = bridge.with_columns(
        pl.when(validos).then(pl.col("ton_nfe").abs()).otherwise(0.0).alias("_peso")
    )
    bridge = bridge.with_columns(
        pl.col("_peso").sum().over("frete_id").alias("_peso_total"),
        validos.sum().over("frete_id").alias("_qtd_validas"),
    )
    bridge = bridge.with_columns(
        pl.when(~validos)
        .then(0.0)
        .when(pl.col("_peso_total") > 0)
        .then(pl.col("_peso") / pl.col("_peso_total"))
        .when(pl.col("_qtd_validas") > 0)
        .then(1.0 / pl.col("_qtd_validas"))
        .otherwise(0.0)
        .alias("allocation_weight"),
        pl.when(~validos)
        .then(pl.lit("SEM_VINCULO"))
        .when(pl.col("_peso_total") > 0)
        .then(pl.lit(metodo))
        .otherwise(pl.lit(fallback))
        .alias("allocation_method"),
    ).with_columns(
        (pl.col("vlrnota") * pl.col("allocation_weight")).alias("vlrfrete_alocado")
    )

    grav = bridge.select(
        "frete_id", "chavecte", "chave_nfe", "numero_nota_venda", "nunota_venda",
        "match_status", "ton_nfe", "allocation_weight", "allocation_method",
        "vlrfrete_alocado",
    )

    execute("TRUNCATE analytics.bridge_cte_nfe CASCADE")
    n = insert_dataframe(grav, "bridge_cte_nfe", "analytics")

    # Atualiza a contagem de NF-e vinculadas por CT-e
    execute(
        """
        UPDATE analytics.fact_cte c
        SET qtd_nfe_vinculadas = k.n
        FROM (
            SELECT frete_id, COUNT(*) FILTER (WHERE match_status <> 'SEM_VINCULO') AS n
            FROM analytics.bridge_cte_nfe GROUP BY frete_id
        ) k
        WHERE k.frete_id = c.frete_id
        """
    )

    resumo = grav.group_by("match_status").agg(
        pl.len().alias("linhas"), pl.col("vlrfrete_alocado").sum().alias("frete")
    ).sort("linhas", descending=True)
    for r in resumo.iter_rows(named=True):
        pct = 100 * r["linhas"] / grav.height
        logger.info(
            f"  bridge {r['match_status']}: {r['linhas']:,} ({pct:.2f}%) "
            f"R$ {r['frete'] or 0:,.2f}".replace(",", ".")
        )
    logger.info(f"bridge_cte_nfe: {n:,} vinculos".replace(",", "."))
    return n


def propagar_frete_para_itens() -> int:
    """
    Distribui o frete alocado da nota entre os itens, na proporcao da tonelagem.

    O item guarda o valor rateado apenas para analises de R$/t por produto.
    O total de frete confiavel continua sendo lido de fact_cte / bridge.
    """
    sql = """
        WITH frete_nota AS (
            SELECT nunota_venda AS nunota, SUM(vlrfrete_alocado) AS frete
            FROM analytics.bridge_cte_nfe
            WHERE match_status <> 'SEM_VINCULO' AND nunota_venda IS NOT NULL
            GROUP BY nunota_venda
        ),
        ton_nota AS (
            SELECT nunota, SUM(ABS(tonliq)) AS ton FROM analytics.fact_venda_item GROUP BY nunota
        )
        UPDATE analytics.fact_venda_item i
        SET vlrfrete_alocado = CASE
                WHEN t.ton > 0 THEN f.frete * ABS(i.tonliq) / t.ton
                ELSE 0
            END,
            frete_alocado_metodo = CASE WHEN t.ton > 0 THEN 'TON_WEIGHT' ELSE 'SEM_TONELAGEM' END
        FROM frete_nota f
        JOIN ton_nota t ON t.nunota = f.nunota
        WHERE i.nunota = f.nunota
    """
    execute(sql)
    n = read_sql(
        "SELECT COUNT(*) AS n FROM analytics.fact_venda_item WHERE vlrfrete_alocado IS NOT NULL"
    )["n"][0]
    logger.info(f"Frete propagado para {n:,} itens".replace(",", "."))
    return int(n)


def indicadores_cobertura() -> dict[str, float]:
    """Metricas de honestidade exibidas na pagina de Logistica."""
    df = read_sql(
        """
        SELECT
            (SELECT COUNT(*) FROM analytics.fact_cte)                                  AS cte_total,
            (SELECT COUNT(*) FROM analytics.fact_cte WHERE qtd_nfe_vinculadas = 0)     AS cte_sem_nfe,
            (SELECT COALESCE(SUM(vlrnota), 0) FROM analytics.fact_cte)                 AS frete_total,
            (SELECT COALESCE(SUM(vlrfrete_alocado), 0) FROM analytics.bridge_cte_nfe
              WHERE match_status <> 'SEM_VINCULO')                                     AS frete_alocado,
            (SELECT COUNT(*) FROM analytics.bridge_cte_nfe WHERE match_status = 'SEM_VINCULO') AS vinculos_sem_match
        """
    )
    r = df.to_dicts()[0]
    total = float(r["frete_total"] or 0)
    alocado = float(r["frete_alocado"] or 0)
    out = {
        "cte_total": int(r["cte_total"]),
        "cte_sem_nfe": int(r["cte_sem_nfe"]),
        "pct_cte_sem_nfe": 100 * r["cte_sem_nfe"] / r["cte_total"] if r["cte_total"] else 0.0,
        "frete_total": total,
        "frete_alocado": alocado,
        "frete_nao_alocado": total - alocado,
        "pct_frete_nao_alocado": 100 * (total - alocado) / total if total else 0.0,
    }
    logger.info(
        f"Cobertura logistica: {out['pct_frete_nao_alocado']:.2f}% do frete nao alocado, "
        f"{out['pct_cte_sem_nfe']:.2f}% dos CT-e sem NF-e"
    )
    return out


def construir_frete() -> dict[str, object]:
    cte = construir_fact_cte()
    n_bridge = construir_bridge(cte)
    n_itens = propagar_frete_para_itens()
    return {
        "fact_cte": cte.height,
        "bridge_cte_nfe": n_bridge,
        "itens_com_frete": n_itens,
        **indicadores_cobertura(),
    }
