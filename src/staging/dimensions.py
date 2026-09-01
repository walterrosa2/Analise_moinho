"""
Construcao das dimensoes analiticas.

Le os Parquet da camada RAW (texto puro) e produz analytics.dim_*.
Nenhuma regra e inferida: classificacao de produto vem de
config/product_classification.yaml e papel de vendedor de config/seller_roles.yaml.
"""
from __future__ import annotations

from datetime import date

import polars as pl

from src.config import load_yaml
from src.db.engine import execute, insert_dataframe
from src.ingestion.loader import ler_parquet
from src.ingestion.readers import (
    hash_documento,
    limpar_texto,
    para_data,
    para_inteiro,
    separar_codigo_descricao,
)
from src.logging_setup import logger

# =====================================================================
# dim_data
# =====================================================================

NOMES_MES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def construir_dim_data(inicio: date = date(2020, 1, 1), fim: date = date(2027, 12, 31)) -> int:
    datas = pl.date_range(inicio, fim, interval="1d", eager=True).alias("data_id")
    df = pl.DataFrame({"data_id": datas}).with_columns(
        pl.col("data_id").dt.year().cast(pl.Int16).alias("ano"),
        pl.col("data_id").dt.month().cast(pl.Int16).alias("mes"),
        pl.col("data_id").dt.day().cast(pl.Int16).alias("dia"),
        pl.col("data_id").dt.strftime("%Y-%m").alias("ano_mes"),
        pl.col("data_id").dt.quarter().cast(pl.Int16).alias("trimestre"),
        ((pl.col("data_id").dt.month() - 1) // 6 + 1).cast(pl.Int16).alias("semestre"),
        pl.col("data_id").dt.weekday().cast(pl.Int16).alias("dia_semana"),
        pl.col("data_id").dt.month_start().alias("inicio_mes"),
        pl.col("data_id").dt.month_end().alias("fim_mes"),
        (pl.col("data_id").dt.weekday() >= 6).alias("is_fim_semana"),
    )
    df = df.with_columns(
        pl.col("mes").map_elements(lambda m: NOMES_MES[m - 1], return_dtype=pl.Utf8).alias("nome_mes")
    )
    execute("TRUNCATE analytics.dim_data CASCADE")
    n = insert_dataframe(
        df.select(
            "data_id", "ano", "mes", "dia", "ano_mes", "trimestre", "semestre",
            "dia_semana", "nome_mes", "inicio_mes", "fim_mes", "is_fim_semana",
        ),
        "dim_data",
        "analytics",
    )
    logger.info(f"dim_data: {n:,} dias".replace(",", "."))
    return n


# =====================================================================
# dim_produto
# =====================================================================


def _classificar_produtos(df: pl.DataFrame) -> pl.DataFrame:
    """
    Aplica config/product_classification.yaml.

    Ordem: excecao explicita > regra de prefixo (grupo MISTURAS) > regra de grupo.
    Cada produto guarda a ORIGEM da classificacao (rastreabilidade).
    """
    cfg = load_yaml("product_classification.yaml")
    versao = str(cfg.get("versao", "0"))
    por_grupo = {int(k): v for k, v in (cfg.get("regra_por_grupo") or {}).items()}
    prefixo_cfg = cfg.get("regra_por_prefixo_descricao") or {}
    grupo_prefixo = prefixo_cfg.get("aplica_ao_grupo")
    prefixos = {p["prefixo"]: p["classificacao"] for p in (prefixo_cfg.get("prefixos") or [])}
    padrao_prefixo = prefixo_cfg.get("padrao", "MISTURAS")
    excecoes = {int(k): v for k, v in (cfg.get("excecoes") or {}).items()}
    padrao = cfg.get("padrao_sem_correspondencia", "NAO_CLASSIFICADO")

    def classificar(codprod: int | None, grupo: int | None, desc: str | None) -> tuple[str, str]:
        if codprod is not None and codprod in excecoes:
            return excecoes[codprod], "EXCECAO_YAML"
        if grupo is not None and grupo_prefixo is not None and grupo == int(grupo_prefixo):
            d = (desc or "").upper().strip()
            for pref, classe in prefixos.items():
                if d.startswith(pref.upper()):
                    return classe, "REGRA_PREFIXO"
            return padrao_prefixo, "REGRA_PREFIXO_PADRAO"
        if grupo is not None and grupo in por_grupo:
            return por_grupo[grupo], "REGRA_GRUPO_ERP"
        return padrao, "NAO_CLASSIFICADO"

    resultados = [
        classificar(r["codprod"], r["codgrupoprod"], r["descrprod"])
        for r in df.iter_rows(named=True)
    ]
    return df.with_columns(
        pl.Series("classificacao", [r[0] for r in resultados]),
        pl.Series("classificacao_origem", [r[1] for r in resultados]),
        pl.lit(versao).alias("classificacao_versao"),
    )


def construir_dim_produto() -> int:
    custos = ler_parquet("custos_pa")
    vendas = ler_parquet("vendas_dev")

    # Cadastro base: tabela de custo (tem grupo e unidade)
    base = (
        custos.select(
            para_inteiro("CODPROD").alias("codprod"),
            limpar_texto("PRODUTO").alias("descrprod"),
            para_inteiro("CODGRUPOPROD").alias("codgrupoprod"),
            limpar_texto("GRUPO_PRODUTO").alias("grupo_produto"),
            limpar_texto("UNIDADE").alias("unidade"),
        )
        .drop_nulls("codprod")
        .unique(subset=["codprod"], keep="first")
    )

    # Produtos que aparecem apenas nas vendas nao podem ficar de fora
    so_vendas = (
        vendas.select(
            para_inteiro("CODPROD").alias("codprod"),
            limpar_texto("DESCRPROD").alias("descrprod"),
        )
        .drop_nulls("codprod")
        .unique(subset=["codprod"], keep="first")
        .join(base.select("codprod"), on="codprod", how="anti")
        .with_columns(
            pl.lit(None, dtype=pl.Int64).alias("codgrupoprod"),
            pl.lit(None, dtype=pl.Utf8).alias("grupo_produto"),
            pl.lit(None, dtype=pl.Utf8).alias("unidade"),
        )
    )
    if so_vendas.height:
        logger.warning(
            f"{so_vendas.height} produto(s) presentes nas vendas e ausentes na tabela de custo: "
            f"{so_vendas['codprod'].to_list()[:10]}"
        )

    df = pl.concat([base, so_vendas.select(base.columns)], how="vertical").sort("codprod")
    df = _classificar_produtos(df)

    execute("TRUNCATE analytics.dim_produto CASCADE")
    n = insert_dataframe(
        df.select(
            "codprod", "descrprod", "codgrupoprod", "grupo_produto", "unidade",
            "classificacao", "classificacao_origem", "classificacao_versao",
        ),
        "dim_produto",
        "analytics",
    )
    dist = df.group_by("classificacao").len().sort("len", descending=True)
    logger.info(f"dim_produto: {n} produtos | {dict(zip(dist['classificacao'], dist['len'], strict=False))}")
    return n


# =====================================================================
# dim_vendedor
# =====================================================================


def construir_dim_vendedor() -> int:
    cad = ler_parquet("vendedores")
    vendas = ler_parquet("vendas_dev")
    cfg = load_yaml("seller_roles.yaml")
    default_tipo = cfg.get("default_por_tipovend") or {}
    explicitos = {int(k): v for k, v in (cfg.get("codvend") or {}).items()}
    padrao_sem_cadastro = cfg.get("padrao_sem_cadastro", "NAO_CLASSIFICADO")

    base = cad.select(
        para_inteiro("CODVEND").alias("codvend"),
        limpar_texto("APELIDO_VENDEDOR").alias("apelido"),
        limpar_texto("TipoVend").alias("tipo_vend"),
        limpar_texto("VENDEDOR_ATIVO").alias("vendedor_ativo"),
        para_inteiro("CODPARC").alias("codparc"),
        limpar_texto("NOMEPARC").alias("nomeparc"),
        limpar_texto("CIDADE").alias("cidade"),
        limpar_texto("ESTADO").alias("estado"),
        para_inteiro("CODREGIAO").alias("codregiao"),
        limpar_texto("REGIAO").alias("regiao"),
    ).drop_nulls("codvend").unique(subset=["codvend"], keep="first")

    # Vendedores com movimento que nao estao no cadastro (ex.: CODVEND 0)
    movimento = (
        vendas.select(para_inteiro("CODVEND").alias("codvend"))
        .drop_nulls()
        .unique()
        .join(base.select("codvend"), on="codvend", how="anti")
    )
    if movimento.height:
        logger.warning(
            f"{movimento.height} codigo(s) de vendedor com movimento e sem cadastro: "
            f"{sorted(movimento['codvend'].to_list())}"
        )
        faltantes = movimento.with_columns(
            pl.lit("NAO_IDENTIFICADO").alias("apelido"),
            *[pl.lit(None, dtype=pl.Utf8).alias(c) for c in ("tipo_vend", "vendedor_ativo", "nomeparc", "cidade", "estado", "regiao")],
            *[pl.lit(None, dtype=pl.Int64).alias(c) for c in ("codparc", "codregiao")],
        )
        base = pl.concat([base, faltantes.select(base.columns)], how="vertical")

    def papel(codvend: int, tipo: str | None) -> tuple[str, str]:
        if codvend in explicitos:
            return explicitos[codvend].get("papel", padrao_sem_cadastro), "CONFIG_EXPLICITA"
        if tipo and tipo in default_tipo:
            return default_tipo[tipo], "DEFAULT_TIPOVEND"
        return padrao_sem_cadastro, "SEM_CADASTRO"

    papeis = [papel(r["codvend"], r["tipo_vend"]) for r in base.iter_rows(named=True)]
    grupos = [
        explicitos.get(r["codvend"], {}).get("grupo") for r in base.iter_rows(named=True)
    ]

    # Atividade observada nos fatos (nao no cadastro)
    atividade = (
        vendas.select(
            para_inteiro("CODVEND").alias("codvend"),
            para_data("DTFATUR").alias("dt"),
        )
        .drop_nulls("codvend")
        .group_by("codvend")
        .agg(
            pl.col("dt").min().alias("primeira_venda"),
            pl.col("dt").max().alias("ultima_venda"),
        )
    )

    df = (
        base.with_columns(
            pl.Series("papel_analitico", [p[0] for p in papeis]),
            pl.Series("papel_origem", [p[1] for p in papeis]),
            pl.Series("grupo_analitico", grupos, dtype=pl.Utf8),
            (pl.col("vendedor_ativo") == "S").alias("ativo"),
        )
        .join(atividade, on="codvend", how="left")
        .sort("codvend")
    )

    execute("TRUNCATE analytics.dim_vendedor CASCADE")
    n = insert_dataframe(
        df.select(
            "codvend", "apelido", "tipo_vend", "vendedor_ativo", "ativo", "codparc",
            "nomeparc", "cidade", "estado", "codregiao", "regiao", "papel_analitico",
            "grupo_analitico", "papel_origem", "primeira_venda", "ultima_venda",
        ),
        "dim_vendedor",
        "analytics",
    )
    com_mov = df.filter(pl.col("primeira_venda").is_not_null()).height
    logger.info(f"dim_vendedor: {n} cadastrados, {com_mov} com movimento")
    return n


# =====================================================================
# dim_cliente
# =====================================================================


def construir_dim_cliente() -> int:
    vendas = ler_parquet("vendas_dev")

    atributos = (
        vendas.select(
            para_inteiro("CODPARC").alias("codparc"),
            limpar_texto("PARCEIRO").alias("parceiro"),
            hash_documento("CGCCPF_PAR").alias("cgccpf_hash"),
            limpar_texto("CGCCPF_PAR").alias("_doc_bruto"),
            separar_codigo_descricao("NOMECIDPARC", "descricao").alias("cidade"),
            limpar_texto("UFPARC").alias("uf"),
            separar_codigo_descricao("RAMOATIVPARC", "descricao").alias("ramo_atividade"),
            separar_codigo_descricao("PERFILEMPPARC", "descricao").alias("perfil_empresa"),
            para_inteiro("CODREG").alias("codreg"),
            limpar_texto("NOMEREG").alias("nomereg"),
            para_data("DTFATUR").alias("_dt"),
        )
        .drop_nulls("codparc")
        .sort("_dt", descending=True)
        .unique(subset=["codparc"], keep="first")
    )

    # PJ tem 14 digitos; PF, 11. Classificacao pelo tamanho, nao pelo nome.
    atributos = atributos.with_columns(
        pl.when(pl.col("_doc_bruto").str.replace_all(r"\D", "").str.len_chars() == 14)
        .then(pl.lit("PJ"))
        .when(pl.col("_doc_bruto").str.replace_all(r"\D", "").str.len_chars() == 11)
        .then(pl.lit("PF"))
        .otherwise(pl.lit("DESCONHECIDO"))
        .alias("tipo_pessoa")
    ).drop("_doc_bruto", "_dt")

    # Primeira/ultima compra e meses ativos: observados no fato, nao no cadastro
    historico = (
        vendas.select(
            para_inteiro("CODPARC").alias("codparc"),
            para_data("DTFATUR").alias("dt"),
            limpar_texto("TIPMOV").alias("tipmov"),
        )
        .filter(pl.col("tipmov") == "V")
        .drop_nulls(["codparc", "dt"])
        .group_by("codparc")
        .agg(
            pl.col("dt").min().alias("primeira_compra"),
            pl.col("dt").max().alias("ultima_compra"),
            pl.col("dt").dt.strftime("%Y-%m").n_unique().alias("qtd_meses_ativos"),
        )
    )

    df = atributos.join(historico, on="codparc", how="left").sort("codparc")

    execute("TRUNCATE analytics.dim_cliente CASCADE")
    n = insert_dataframe(
        df.select(
            "codparc", "parceiro", "cgccpf_hash", "tipo_pessoa", "cidade", "uf",
            "ramo_atividade", "perfil_empresa", "codreg", "nomereg",
            "primeira_compra", "ultima_compra", "qtd_meses_ativos",
        ).with_columns(pl.lit(None, dtype=pl.Utf8).alias("razao_social")),
        "dim_cliente",
        "analytics",
        columns=[
            "codparc", "parceiro", "cgccpf_hash", "tipo_pessoa", "cidade", "uf",
            "ramo_atividade", "perfil_empresa", "codreg", "nomereg",
            "primeira_compra", "ultima_compra", "qtd_meses_ativos", "razao_social",
        ],
    )
    logger.info(f"dim_cliente: {n:,} clientes".replace(",", "."))
    return n


# =====================================================================
# dim_regiao e dim_transportador
# =====================================================================


def construir_dim_regiao() -> int:
    vendas = ler_parquet("vendas_dev")
    df = (
        vendas.select(
            para_inteiro("CODREG").alias("codreg"),
            limpar_texto("NOMEREG").alias("nomereg"),
        )
        .drop_nulls("codreg")
        .unique(subset=["codreg"], keep="first")
        .sort("codreg")
    )
    execute("TRUNCATE analytics.dim_regiao CASCADE")
    n = insert_dataframe(df, "dim_regiao", "analytics")
    logger.info(f"dim_regiao: {n} regioes comerciais")
    return n


def construir_dim_transportador() -> int:
    vendas = ler_parquet("vendas_dev")
    cte = ler_parquet("cte")

    das_vendas = (
        vendas.select(para_inteiro("CODPARCTRANSP").alias("codparc_transp"))
        .drop_nulls()
        .unique()
        .with_columns(pl.lit(None, dtype=pl.Utf8).alias("nome_transp"))
    )
    do_cte = (
        cte.select(
            para_inteiro("CODPARC").alias("codparc_transp"),
            limpar_texto("NOMEPARC").alias("nome_transp"),
        )
        .drop_nulls("codparc_transp")
        .unique(subset=["codparc_transp"], keep="first")
    )
    df = (
        pl.concat([do_cte, das_vendas.join(do_cte.select("codparc_transp"), on="codparc_transp", how="anti")])
        .unique(subset=["codparc_transp"], keep="first")
        .sort("codparc_transp")
    )
    execute("TRUNCATE analytics.dim_transportador CASCADE")
    n = insert_dataframe(df, "dim_transportador", "analytics")
    logger.info(f"dim_transportador: {n} transportadores")
    return n


def construir_todas() -> dict[str, int]:
    return {
        "dim_data": construir_dim_data(),
        "dim_produto": construir_dim_produto(),
        "dim_vendedor": construir_dim_vendedor(),
        "dim_cliente": construir_dim_cliente(),
        "dim_regiao": construir_dim_regiao(),
        "dim_transportador": construir_dim_transportador(),
    }
