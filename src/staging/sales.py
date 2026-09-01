"""
Fatos de venda: documento (NUNOTA) e item (NUNOTA + SEQUENCIA).

Regra de seguranca analitica que este modulo materializa (RN-02):
  VLRNOTA e VLRFRETE_ORDEMCARGA sao medidas de DOCUMENTO. Elas existem apenas
  em fact_venda_documento. Soma-las no grao de item infla receita em 321,7%
  e frete em 1.788,3% (medido na Fase 0).
"""
from __future__ import annotations

import polars as pl

from src.config import get_settings, load_yaml
from src.db.engine import execute, insert_dataframe
from src.ingestion.loader import ler_parquet
from src.ingestion.readers import (
    limpar_texto,
    normalizar_cif_fob,
    para_data,
    para_decimal,
    para_inteiro,
)
from src.logging_setup import logger


def _campo_data_referencia() -> str:
    """Data usada como referencia analitica (configuravel — Q-05)."""
    return get_settings().cost_reference_date_field.upper()


def _preparar(vendas: pl.DataFrame) -> pl.DataFrame:
    """Tipagem e normalizacao comuns ao documento e ao item."""
    cfg = load_yaml("settings.yaml")
    ops = cfg.get("operacoes") or {}
    tipmov_dev = ops.get("tipmov_devolucao", "D")
    campo_ref = _campo_data_referencia()

    df = vendas.select(
        para_inteiro("NUNOTA").alias("nunota"),
        para_inteiro("SEQUENCIA").alias("sequencia"),
        para_inteiro("CODEMP").alias("codemp"),
        para_inteiro("NUMNOTA").alias("numnota"),
        limpar_texto("CHAVENFE").alias("chavenfe"),
        para_data("DTNEG").alias("dtneg"),
        para_data("DTFATUR").alias("dtfatur"),
        para_data("DTENTSAI").alias("dtentsai"),
        para_inteiro("CODTIPOPER").alias("codtipoper"),
        limpar_texto("DESCROPER").alias("descroper"),
        limpar_texto("TIPMOV").alias("tipmov"),
        normalizar_cif_fob("CIF_FOB").alias("cif_fob"),
        limpar_texto("CIF_FOB").alias("cif_fob_bruto"),
        limpar_texto("CIDORIGEM").alias("cidorigem"),
        limpar_texto("CIDDESTINO").alias("ciddestino"),
        limpar_texto("UFORIGEM").alias("uforigem"),
        limpar_texto("UFDESTINO").alias("ufdestino"),
        para_decimal("VLRFRETE_RATEADO_NOTA").alias("vlrfrete_rateado_nota"),
        para_inteiro("CODPROD").alias("codprod"),
        limpar_texto("CONTROLE").alias("controle"),
        para_inteiro("CODCFO").alias("codcfo"),
        para_inteiro("CODLOCALORIG").alias("codlocalorig"),
        limpar_texto("CODTRIB").alias("codtrib"),
        para_decimal("PERCCOM").alias("perccom"),
        para_decimal("VLRCOM").alias("vlrcom"),
        limpar_texto("CODVOL").alias("codvol"),
        para_decimal("QTD").alias("qtd"),
        para_decimal("PESOLIQ").alias("pesoliq"),
        para_decimal("TONLIQ").alias("tonliq"),
        para_decimal("PESOBRUTO").alias("pesobruto"),
        para_decimal("TONBRUTO").alias("tonbruto"),
        para_decimal("VLRNOTA").alias("vlrnota"),
        para_decimal("VLRUNIT").alias("vlrunit"),
        para_decimal("VLRTOT").alias("vlrtot"),
        para_decimal("VLRDESC").alias("vlrdesc"),
        para_decimal("VLRREPRED").alias("vlrrepred"),
        para_decimal("VLRICMS").alias("vlricms"),
        para_decimal("VLRSUBST").alias("vlrsubst"),
        para_inteiro("ORDEMCARGA").alias("ordemcarga"),
        limpar_texto("CIF_FOB_ORDEMCARGA").alias("cif_fob_ordemcarga"),
        para_inteiro("CODPARCTRANSP").alias("codparctransp"),
        para_decimal("VLRFRETE_ORDEMCARGA").alias("vlrfrete_ordemcarga"),
        para_inteiro("CODREG").alias("codreg"),
        limpar_texto("NOMEREG").alias("nomereg"),
        para_inteiro("CODVEND").alias("codvend"),
        para_inteiro("CODSUPERVISOR").alias("codsupervisor"),
        para_inteiro("CODPARC").alias("codparc"),
        limpar_texto("ACORDO").alias("acordo"),
        limpar_texto("OBSERVACAONOTA").alias("observacaonota"),
    )

    # Data de referencia configuravel, com fallback em cascata
    ref = {"DTFATUR": "dtfatur", "DTNEG": "dtneg", "DTENTSAI": "dtentsai"}.get(campo_ref, "dtfatur")
    df = df.with_columns(
        pl.coalesce(pl.col(ref), pl.col("dtfatur"), pl.col("dtneg"), pl.col("dtentsai"))
        .alias("data_referencia")
    ).with_columns(
        pl.col("data_referencia").dt.year().cast(pl.Int16).alias("ano"),
        pl.col("data_referencia").dt.month().cast(pl.Int16).alias("mes"),
        pl.col("data_referencia").dt.strftime("%Y-%m").alias("ano_mes"),
        (pl.col("tipmov") == tipmov_dev).alias("is_devolucao"),
    )
    return df


def construir_fact_venda_documento(df: pl.DataFrame) -> int:
    """
    Grao NUNOTA. Guarda as medidas de documento (VLRNOTA, frete da carga)
    e os atributos que nao variam entre os itens.
    """
    doc = (
        df.sort(["nunota", "sequencia"])
        .group_by("nunota")
        .agg(
            pl.col("codemp").first(),
            pl.col("numnota").first(),
            pl.col("chavenfe").first(),
            pl.col("dtneg").first(),
            pl.col("dtfatur").first(),
            pl.col("dtentsai").first(),
            pl.col("data_referencia").first(),
            pl.col("ano").first(),
            pl.col("mes").first(),
            pl.col("ano_mes").first(),
            pl.col("codtipoper").first(),
            pl.col("descroper").first(),
            pl.col("tipmov").first(),
            pl.col("is_devolucao").first(),
            pl.col("cif_fob").first(),
            pl.col("cidorigem").first(),
            pl.col("ciddestino").first(),
            pl.col("uforigem").first(),
            pl.col("ufdestino").first(),
            # Frete rateado JA vem por nota na origem: primeiro valor, nao soma
            pl.col("vlrfrete_rateado_nota").first(),
            pl.col("ordemcarga").first(),
            pl.col("cif_fob_ordemcarga").first(),
            pl.col("codparctransp").first(),
            pl.col("vlrfrete_ordemcarga").first(),
            pl.col("codparc").first(),
            pl.col("codvend").first(),
            pl.col("codsupervisor").first(),
            pl.col("codreg").first(),
            pl.col("nomereg").first(),
            pl.col("vlrnota").first(),
            pl.col("acordo").first(),
            pl.col("observacaonota").first(),
        )
        .sort("nunota")
    )

    execute("TRUNCATE analytics.fact_venda_documento CASCADE")
    n = insert_dataframe(doc, "fact_venda_documento", "analytics")
    logger.info(f"fact_venda_documento: {n:,} documentos".replace(",", "."))
    return n


def construir_fact_venda_item(df: pl.DataFrame) -> int:
    """Grao NUNOTA + SEQUENCIA. Sem medidas de documento (RN-02)."""
    item = df.select(
        "nunota", "sequencia", "codemp", "data_referencia", "ano", "mes", "ano_mes",
        "codprod", "codparc", "codvend", "codsupervisor", "codreg", "codlocalorig",
        "codtrib", "controle", "codcfo", "tipmov", "is_devolucao", "cif_fob",
        "codvol", "qtd", "pesoliq", "tonliq", "pesobruto", "tonbruto",
        "vlrunit", "vlrtot", "vlrdesc", "vlrrepred",
        "perccom", "vlrcom", "vlricms", "vlrsubst",
    ).sort(["nunota", "sequencia"])

    # Guarda de regressao: as medidas de documento nao podem estar aqui
    proibidas = {"vlrnota", "vlrfrete_ordemcarga"} & set(item.columns)
    if proibidas:
        raise RuntimeError(
            f"Medidas de documento no grao de item: {proibidas}. Viola RN-02."
        )

    execute("TRUNCATE analytics.fact_venda_item CASCADE")
    n = insert_dataframe(item, "fact_venda_item", "analytics", columns=list(item.columns))
    logger.info(f"fact_venda_item: {n:,} itens".replace(",", "."))
    return n


def construir_vendas() -> dict[str, int]:
    vendas = ler_parquet("vendas_dev")
    df = _preparar(vendas)

    # Verificacao de grao antes de gravar (AC-04)
    total, distintas = df.height, df.select(["nunota", "sequencia"]).unique().height
    if total != distintas:
        raise RuntimeError(
            f"NUNOTA+SEQUENCIA nao e unico: {total} linhas, {distintas} distintas "
            f"({total - distintas} duplicadas). Verifique a fonte."
        )
    logger.info(f"Grao NUNOTA+SEQUENCIA verificado: {total:,} linhas unicas".replace(",", "."))

    return {
        "fact_venda_documento": construir_fact_venda_documento(df),
        "fact_venda_item": construir_fact_venda_item(df),
    }
