"""
Fatos gerenciais e de apoio:
  - fact_positivado / fact_positivado_mes (explosao da lista de clientes)
  - fact_gestao_diaria (161)
  - fact_despesa_mensal (161 OUTROS)
  - fact_trigo_compra_mensal / fact_trigo_estoque_mensal (parser posicional)
  - app.data_source_catalog (sem credenciais)
"""
from __future__ import annotations

import polars as pl

from src.config import load_yaml
from src.db.engine import execute, insert_dataframe, read_sql
from src.ingestion.loader import ler_parquet
from src.ingestion.readers import limpar_texto, para_decimal, para_inteiro
from src.logging_setup import logger

# =====================================================================
# Positivados
# =====================================================================


def construir_positivados() -> dict[str, int]:
    pos = ler_parquet("positivados_mensal")
    cfg = load_yaml("settings.yaml").get("positivados") or {}
    meses_implantacao = set(cfg.get("implantacao_erp") or [])

    base = pos.select(
        para_inteiro("ANO").alias("ano"),
        para_inteiro("MES").alias("mes"),
        para_inteiro("QTD_POSITIVADOS").alias("qtd_positivados_fonte"),
        para_decimal("VLRTOT_POSITIVADOS").alias("vlrtot_positivados"),
        para_decimal("VLRTOT_GERAL").alias("vlrtot_geral"),
        para_decimal("PERC_PROSITIVADOS_X_GERAL_MES").alias("perc_positivados_geral"),
        limpar_texto("PARC_POSITIVADOS").alias("lista"),
    ).with_columns(
        (
            pl.col("ano").cast(pl.Utf8)
            + "-"
            + pl.col("mes").cast(pl.Utf8).str.zfill(2)
        ).alias("ano_mes")
    ).with_columns(
        pl.col("ano_mes").is_in(list(meses_implantacao)).alias("periodo_implantacao_erp")
    )

    # Explosao da lista "2654, 2941, 3305, ..."
    explodido = (
        base.filter(pl.col("lista").is_not_null())
        .with_columns(pl.col("lista").str.split(",").alias("_cods"))
        .explode("_cods")
        .with_columns(pl.col("_cods").str.strip_chars().alias("_c"))
        .filter(pl.col("_c").str.len_chars() > 0)
        .with_columns(pl.col("_c").cast(pl.Int64, strict=False).alias("codparc"))
        .drop_nulls("codparc")
        .select("ano", "mes", "ano_mes", "codparc", "periodo_implantacao_erp")
        .unique(subset=["ano", "mes", "codparc"])
    )

    # Validacao obrigatoria: explosao x QTD declarado (AC-07)
    conferencia = (
        explodido.group_by(["ano", "mes"])
        .agg(pl.len().alias("qtd_explodido"))
        .join(base.select("ano", "mes", "qtd_positivados_fonte"), on=["ano", "mes"], how="full", coalesce=True)
        .with_columns(
            (pl.col("qtd_explodido").fill_null(0) - pl.col("qtd_positivados_fonte").fill_null(0)).alias("dif")
        )
    )
    divergentes = conferencia.filter(pl.col("dif") != 0)
    if divergentes.height:
        logger.warning(
            f"Positivados: {divergentes.height} mes(es) com divergencia entre a lista "
            f"explodida e QTD_POSITIVADOS: "
            f"{divergentes.select('ano', 'mes', 'dif').to_dicts()}"
        )
    else:
        logger.info("Positivados: explosao confere com QTD_POSITIVADOS em todos os meses")

    # Cliente existe na dimensao?
    clientes = read_sql("SELECT codparc FROM analytics.dim_cliente")
    existentes = set(clientes["codparc"].to_list()) if clientes.height else set()
    explodido = explodido.with_columns(
        pl.col("codparc").is_in(list(existentes)).alias("cliente_existe_dim")
    )
    sem_dim = explodido.filter(~pl.col("cliente_existe_dim")).height
    if sem_dim:
        logger.info(
            f"Positivados: {sem_dim:,} registro(s) de cliente sem venda na base 2023+ "
            "(esperado: positivados cobrem 2021+)".replace(",", ".")
        )

    execute("TRUNCATE analytics.fact_positivado CASCADE")
    n1 = insert_dataframe(
        explodido.select("ano", "mes", "ano_mes", "codparc", "cliente_existe_dim", "periodo_implantacao_erp"),
        "fact_positivado",
        "analytics",
    )

    mensal = base.join(
        conferencia.select("ano", "mes", "qtd_explodido"), on=["ano", "mes"], how="left"
    ).select(
        "ano", "mes", "ano_mes", "qtd_positivados_fonte", "qtd_explodido",
        "vlrtot_positivados", "vlrtot_geral", "perc_positivados_geral",
        "periodo_implantacao_erp",
    ).rename({"qtd_explodido": "qtd_positivados_explodido"})

    execute("TRUNCATE analytics.fact_positivado_mes CASCADE")
    n2 = insert_dataframe(mensal, "fact_positivado_mes", "analytics")

    logger.info(f"fact_positivado: {n1:,} vinculos cliente-mes | {n2} meses".replace(",", "."))
    return {"fact_positivado": n1, "fact_positivado_mes": n2}


# =====================================================================
# 161 Gestao Diaria
# =====================================================================


def construir_gestao_diaria() -> int:
    g = ler_parquet("gestao_diaria_161")
    df = (
        g.select(
            para_inteiro("ANO").alias("ano"),
            para_inteiro("MES").alias("mes"),
            limpar_texto("TIPO").alias("tipo"),
            limpar_texto("COD_CLA").alias("cod_cla"),
            limpar_texto("DESC_CLA").alias("desc_cla"),
            para_decimal("VALOR").alias("valor"),
            para_decimal("PERC_ATING_VLR").alias("perc_ating_vlr"),
            para_decimal("TONELADA").alias("tonelada"),
            para_decimal("PERC_ATING_TON").alias("perc_ating_ton"),
            para_decimal("MARKUP").alias("markup"),
            para_decimal("PC_MEDIO").alias("pc_medio"),
        )
        .drop_nulls(["ano", "mes", "tipo"])
        .with_columns(
            (pl.col("ano").cast(pl.Utf8) + "-" + pl.col("mes").cast(pl.Utf8).str.zfill(2)).alias("ano_mes")
        )
        .unique(subset=["ano", "mes", "tipo", "cod_cla"], keep="last")
    )
    execute("TRUNCATE analytics.fact_gestao_diaria CASCADE")
    n = insert_dataframe(
        df.select(
            "ano", "mes", "ano_mes", "tipo", "cod_cla", "desc_cla", "valor",
            "perc_ating_vlr", "tonelada", "perc_ating_ton", "markup", "pc_medio",
        ),
        "fact_gestao_diaria",
        "analytics",
    )
    logger.info(f"fact_gestao_diaria: {n:,} linhas".replace(",", "."))
    return n


def construir_despesas() -> int:
    o = ler_parquet("gestao_diaria_outros")
    df = (
        o.select(
            para_inteiro("ANO").alias("ano"),
            para_inteiro("MES").alias("mes"),
            limpar_texto("DESCRICAO").alias("descricao"),
            para_decimal("ORC/ANT").alias("orc_ant"),
            para_decimal("ATUAL").alias("atual"),
            para_decimal("%VAR").alias("perc_var"),
        )
        .drop_nulls(["ano", "mes", "descricao"])
        .with_columns(
            (pl.col("ano").cast(pl.Utf8) + "-" + pl.col("mes").cast(pl.Utf8).str.zfill(2)).alias("ano_mes")
        )
        .unique(subset=["ano", "mes", "descricao"], keep="last")
    )
    execute("TRUNCATE analytics.fact_despesa_mensal CASCADE")
    n = insert_dataframe(
        df.select("ano", "mes", "ano_mes", "descricao", "orc_ant", "atual", "perc_var"),
        "fact_despesa_mensal",
        "analytics",
    )
    logger.info(f"fact_despesa_mensal: {n} linhas (ORC/ANT pendente de validacao — Q-03)")
    return n


# =====================================================================
# Trigo (planilha com cabecalho de duas linhas e celulas mescladas)
# =====================================================================


def _linhas_trigo(df: pl.DataFrame) -> pl.DataFrame:
    """
    Mantem apenas as linhas cuja primeira coluna e uma data.

    A planilha tem titulo na linha 1, sub-cabecalho na 2 e linhas de
    totalizacao ao final. Filtrar por data e mais robusto que contar linhas.
    """
    col0 = df.columns[0]
    return df.filter(
        pl.col(col0).cast(pl.Utf8).str.strip_chars().str.contains(r"^\d{4}-\d{2}-\d{2}")
    )


def construir_trigo_compra() -> int:
    t = ler_parquet("trigo_compra")
    linhas = _linhas_trigo(t)
    c = linhas.columns

    # Posicoes confirmadas na Fase 0:
    # 0=Mes/Ano 1=Ton trigo 2=Ton triticale 3=Ton soma 4=(vazia)
    # 5=Vlr trigo 6=Vlr triticale 7=Vlr soma 8=Preco medio
    df = linhas.select(
        pl.col(c[0]).str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("_dt"),
        para_decimal(c[1]).alias("ton_trigo"),
        para_decimal(c[2]).alias("ton_triticale"),
        para_decimal(c[3]).alias("ton_total"),
        para_decimal(c[5]).alias("vlr_trigo"),
        para_decimal(c[6]).alias("vlr_triticale"),
        para_decimal(c[7]).alias("vlr_total"),
        para_decimal(c[8]).alias("preco_medio"),
    ).drop_nulls("_dt")

    df = df.with_columns(
        pl.col("_dt").dt.year().cast(pl.Int16).alias("ano"),
        pl.col("_dt").dt.month().cast(pl.Int16).alias("mes"),
        pl.col("_dt").dt.strftime("%Y-%m").alias("ano_mes"),
    ).drop("_dt").unique(subset=["ano", "mes"], keep="last").sort(["ano", "mes"])

    execute("TRUNCATE analytics.fact_trigo_compra_mensal CASCADE")
    n = insert_dataframe(
        df.select(
            "ano", "mes", "ano_mes", "ton_trigo", "ton_triticale", "ton_total",
            "vlr_trigo", "vlr_triticale", "vlr_total", "preco_medio",
        ),
        "fact_trigo_compra_mensal",
        "analytics",
    )
    periodo = f"{df['ano_mes'].min()} a {df['ano_mes'].max()}" if df.height else "vazio"
    logger.info(f"fact_trigo_compra_mensal: {n} meses ({periodo})")
    return n


def construir_trigo_estoque() -> int:
    t = ler_parquet("trigo_estoque")
    linhas = _linhas_trigo(t)
    c = linhas.columns

    df = linhas.select(
        pl.col(c[0]).str.slice(0, 10).str.to_date("%Y-%m-%d", strict=False).alias("_dt"),
        para_decimal(c[1]).alias("ton_estoque"),
        para_decimal(c[2]).alias("preco_medio"),
    ).drop_nulls("_dt")

    df = df.with_columns(
        pl.col("_dt").dt.year().cast(pl.Int16).alias("ano"),
        pl.col("_dt").dt.month().cast(pl.Int16).alias("mes"),
        pl.col("_dt").dt.strftime("%Y-%m").alias("ano_mes"),
    ).drop("_dt").unique(subset=["ano", "mes"], keep="last").sort(["ano", "mes"])

    execute("TRUNCATE analytics.fact_trigo_estoque_mensal CASCADE")
    n = insert_dataframe(
        df.select("ano", "mes", "ano_mes", "ton_estoque", "preco_medio"),
        "fact_trigo_estoque_mensal",
        "analytics",
    )
    periodo = f"{df['ano_mes'].min()} a {df['ano_mes'].max()}" if df.height else "vazio"
    logger.info(f"fact_trigo_estoque_mensal: {n} meses ({periodo})")
    return n


# =====================================================================
# Catalogo de fontes (SEM credenciais)
# =====================================================================


def construir_catalogo() -> int:
    partes = []
    for source_id, origem in (("catalogo_fontes", "SANKHYA"), ("catalogo_fontes_externas", "EXTERNA")):
        try:
            df = ler_parquet(source_id)
        except FileNotFoundError:
            continue
        cols = {c.upper(): c for c in df.columns}
        # A coluna de credenciais nem chega aqui: e bloqueada na ingestao (ADR-005)
        partes.append(
            df.select(
                limpar_texto(cols.get("FONTE", df.columns[0])).alias("origem"),
                limpar_texto(cols.get("LOCALIZAÇÃO", df.columns[1])).alias("relatorio"),
                limpar_texto(cols.get("DADOS", df.columns[-1])).alias("descricao"),
            ).with_columns(
                pl.lit(origem).alias("status"),
                pl.lit(source_id).alias("_source_file"),
                pl.lit(None, dtype=pl.Utf8).alias("periodicidade"),
                pl.lit(None, dtype=pl.Utf8).alias("responsavel"),
                pl.lit(None, dtype=pl.Utf8).alias("observacoes"),
            )
        )

    if not partes:
        return 0
    df = pl.concat(partes, how="vertical")
    execute("TRUNCATE app.data_source_catalog")
    n = insert_dataframe(
        df.select(
            "origem", "relatorio", "descricao", "periodicidade",
            "responsavel", "status", "observacoes", "_source_file",
        ),
        "data_source_catalog",
        "app",
    )
    logger.info(f"data_source_catalog: {n} fontes catalogadas (credenciais nunca importadas)")
    return n


def construir_gerenciais() -> dict[str, int]:
    out: dict[str, int] = {}
    out.update(construir_positivados())
    out["fact_gestao_diaria"] = construir_gestao_diaria()
    out["fact_despesa_mensal"] = construir_despesas()
    out["fact_trigo_compra_mensal"] = construir_trigo_compra()
    out["fact_trigo_estoque_mensal"] = construir_trigo_estoque()
    out["data_source_catalog"] = construir_catalogo()
    return out
