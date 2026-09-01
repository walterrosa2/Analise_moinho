"""
Consultas de venda. Unica camada que escreve SQL para as paginas comerciais.

Todas as funcoes recebem `Filtros` e devolvem polars.DataFrame.
Nenhuma pagina Streamlit monta SQL.
"""
from __future__ import annotations

import polars as pl

from src.db.engine import read_sql
from src.repositories.filters import (
    COLUNAS_VENDA_ITEM,
    Filtros,
)

# Expressoes reutilizadas (PMV sempre exclui operacao sem receita — RN-04)
_PMV = "SUM(receita_para_pmv) / NULLIF(SUM(ton_para_pmv), 0)"


def kpis_gerais(f: Filtros, base_custo: str = "cusger") -> dict[str, float]:
    """Cartoes da Visao Geral, num unico round-trip."""
    where, params = f.where(COLUNAS_VENDA_ITEM)
    df = read_sql(
        f"""
        SELECT
            COALESCE(SUM(vlrtot), 0)                                     AS receita_liquida,
            COALESCE(SUM(vlrtot) FILTER (WHERE NOT is_devolucao), 0)     AS vendas_brutas,
            COALESCE(SUM(vlrtot) FILTER (WHERE is_devolucao), 0)         AS devolucoes,
            COALESCE(SUM(tonliq), 0)                                     AS ton_liquida,
            COALESCE(SUM(vlrtot) FILTER (WHERE NOT is_sem_receita), 0)   AS receita_pmv,
            COALESCE(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0)   AS ton_pmv,
            COUNT(DISTINCT codparc)                                      AS clientes,
            COUNT(DISTINCT nunota)                                       AS documentos,
            COUNT(DISTINCT codprod)                                      AS produtos,
            COUNT(DISTINCT codvend)                                      AS vendedores,
            COALESCE(SUM(vlrdesc), 0)                                    AS desconto,
            COALESCE(SUM(vlrcom), 0)                                     AS comissao,
            COALESCE(SUM(vlrfrete_alocado), 0)                           AS frete,
            COALESCE(SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier), 0) AS custo,
            COALESCE(SUM(vlrtot) FILTER (WHERE NOT custo_outlier), 0)    AS receita_com_custo,
            COUNT(*) FILTER (WHERE custo_outlier)                        AS linhas_custo_outlier,
            COUNT(*)                                                     AS linhas,
            COUNT(*) FILTER (WHERE cost_match_status IN ('SEM_CUSTO','SEM_DATA')) AS itens_sem_custo
        FROM analytics.v_venda_item
        WHERE {where}
        """,
        params,
    )
    r = df.to_dicts()[0] if df.height else {}
    receita = float(r.get("receita_liquida") or 0)
    ton_pmv = float(r.get("ton_pmv") or 0)
    custo = float(r.get("custo") or 0)
    # Margem compara receita e custo da MESMA populacao de linhas (Q-15)
    receita_cc = float(r.get("receita_com_custo") or 0)
    return {
        **{k: float(v or 0) for k, v in r.items()},
        "pmv": (float(r.get("receita_pmv") or 0) / ton_pmv) if ton_pmv else 0.0,
        "margem_proxy": receita_cc - custo,
        "margem_proxy_pct": (100 * (receita_cc - custo) / receita_cc) if receita_cc else 0.0,
        "frete_sobre_receita": (100 * float(r.get("frete") or 0) / receita) if receita else 0.0,
    }


def serie_mensal(f: Filtros, base_custo: str = "cusger") -> pl.DataFrame:
    where, params = f.where(COLUNAS_VENDA_ITEM)
    return read_sql(
        f"""
        SELECT ano_mes, ano, mes,
               SUM(vlrtot)                                    AS receita_liquida,
               SUM(vlrtot) FILTER (WHERE NOT is_devolucao)    AS vendas_brutas,
               SUM(vlrtot) FILTER (WHERE is_devolucao)        AS devolucoes,
               SUM(tonliq)                                    AS ton_liquida,
               SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
               COUNT(DISTINCT codparc)                        AS clientes,
               COUNT(DISTINCT nunota)                         AS documentos,
               SUM(vlrdesc)                                   AS desconto,
               SUM(vlrfrete_alocado)                          AS frete,
               SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier)      AS custo,
               SUM(vlrtot) FILTER (WHERE NOT custo_outlier)                 AS receita_com_custo,
               SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                 - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier) AS margem_proxy
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY ano_mes, ano, mes
        ORDER BY ano_mes
        """,
        params,
    )


def por_dimensao(
    f: Filtros,
    dimensao: str,
    base_custo: str = "cusger",
    limite: int | None = None,
    ordenar_por: str = "receita_liquida",
) -> pl.DataFrame:
    """
    Agrega por qualquer dimensao suportada. Usado no drill-down e no Explorador.
    """
    colunas = {
        "classificacao": ("classificacao", "classificacao"),
        "produto": ("codprod", "descrprod"),
        "cliente": ("codparc", "parceiro"),
        "vendedor": ("codvend", "vendedor"),
        "papel": ("papel_analitico", "papel_analitico"),
        "regiao": ("codreg", "regiao_comercial"),
        "uf": ("uf_cliente", "uf_cliente"),
        "cidade": ("cidade_cliente", "cidade_cliente"),
        "ramo": ("ramo_atividade", "ramo_atividade"),
        "perfil": ("perfil_empresa", "perfil_empresa"),
        "cif_fob": ("cif_fob", "cif_fob"),
        "empresa": ("codemp", "codemp"),
        "ano": ("ano", "ano"),
        "ano_mes": ("ano_mes", "ano_mes"),
        "operacao": ("codtipoper", "descroper"),
        "grupo_produto": ("grupo_produto", "grupo_produto"),
    }
    if dimensao not in colunas:
        raise KeyError(f"Dimensão '{dimensao}' não suportada. Opções: {', '.join(colunas)}")

    chave, rotulo = colunas[dimensao]
    where, params = f.where(COLUNAS_VENDA_ITEM)
    limit_sql = f"LIMIT {int(limite)}" if limite else ""
    group = f"{chave}" if chave == rotulo else f"{chave}, {rotulo}"

    return read_sql(
        f"""
        SELECT {chave} AS chave, {rotulo}::text AS rotulo,
               SUM(vlrtot)                                    AS receita_liquida,
               SUM(vlrtot) FILTER (WHERE NOT is_devolucao)    AS vendas_brutas,
               SUM(vlrtot) FILTER (WHERE is_devolucao)        AS devolucoes,
               SUM(tonliq)                                    AS ton_liquida,
               SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
               COUNT(DISTINCT codparc)                        AS clientes,
               COUNT(DISTINCT nunota)                         AS documentos,
               COUNT(DISTINCT codprod)                        AS produtos,
               SUM(vlrdesc)                                   AS desconto,
               SUM(vlrcom)                                    AS comissao,
               SUM(vlrfrete_alocado)                          AS frete,
               SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier)      AS custo,
               SUM(vlrtot) FILTER (WHERE NOT custo_outlier)                 AS receita_com_custo,
               SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                 - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier) AS margem_proxy,
               COUNT(*) FILTER (WHERE custo_outlier)                        AS linhas_custo_outlier,
               CASE WHEN SUM(vlrtot) FILTER (WHERE NOT custo_outlier) <> 0
                    THEN 100 * (SUM(vlrtot) FILTER (WHERE NOT custo_outlier)
                              - SUM(qtd * {base_custo}) FILTER (WHERE NOT custo_outlier))
                       / SUM(vlrtot) FILTER (WHERE NOT custo_outlier) END AS margem_proxy_pct,
               CASE WHEN SUM(ABS(tonliq)) > 0
                    THEN SUM(vlrfrete_alocado) / SUM(ABS(tonliq)) END AS frete_por_ton
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY {group}
        ORDER BY {ordenar_por} DESC NULLS LAST
        {limit_sql}
        """,
        params,
    )


def serie_por_dimensao(
    f: Filtros, dimensao: str, top_n: int = 10, metrica: str = "receita_liquida"
) -> pl.DataFrame:
    """Serie mensal das N maiores categorias de uma dimensao (para graficos de linha/area)."""
    topo = por_dimensao(f, dimensao, limite=top_n, ordenar_por=metrica)
    if topo.height == 0:
        return pl.DataFrame()
    chaves = topo["chave"].to_list()

    colunas = {
        "classificacao": ("classificacao", "classificacao"),
        "produto": ("codprod", "descrprod"),
        "cliente": ("codparc", "parceiro"),
        "vendedor": ("codvend", "vendedor"),
        "papel": ("papel_analitico", "papel_analitico"),
        "regiao": ("codreg", "regiao_comercial"),
        "uf": ("uf_cliente", "uf_cliente"),
        "ramo": ("ramo_atividade", "ramo_atividade"),
        "grupo_produto": ("grupo_produto", "grupo_produto"),
        "cif_fob": ("cif_fob", "cif_fob"),
    }
    chave, rotulo = colunas.get(dimensao, ("classificacao", "classificacao"))
    where, params = f.where(COLUNAS_VENDA_ITEM)

    marcadores = []
    for i, k in enumerate(chaves):
        p = f"topo{i}"
        params[p] = k
        marcadores.append(f":{p}")

    return read_sql(
        f"""
        SELECT ano_mes, {rotulo}::text AS rotulo,
               SUM(vlrtot)  AS receita_liquida,
               SUM(tonliq)  AS ton_liquida,
               SUM(vlrtot) FILTER (WHERE NOT is_sem_receita)
                 / NULLIF(SUM(tonliq) FILTER (WHERE NOT is_sem_receita), 0) AS pmv,
               COUNT(DISTINCT codparc) AS clientes
        FROM analytics.v_venda_item
        WHERE {where} AND {chave} IN ({', '.join(marcadores)})
        GROUP BY ano_mes, {rotulo}
        ORDER BY ano_mes
        """,
        params,
    )


def comparar_periodos(
    f: Filtros,
    dimensao: str,
    periodo_a: tuple[str, str],
    periodo_b: tuple[str, str],
    metrica: str = "receita_liquida",
    base_custo: str = "cusger",
) -> pl.DataFrame:
    """
    Compara a mesma dimensao em dois periodos e decompoe a variacao.

    Devolve valor A, valor B, variacao absoluta, variacao % e a contribuicao
    de cada categoria para a variacao total (base do waterfall e dos insights).
    """
    fa = Filtros(**{**f.__dict__, "periodo_inicio": periodo_a[0], "periodo_fim": periodo_a[1]})
    fb = Filtros(**{**f.__dict__, "periodo_inicio": periodo_b[0], "periodo_fim": periodo_b[1]})

    # A chave e normalizada para texto: um periodo sem uma categoria pode
    # devolver a coluna com outro tipo, e o join falharia por schema.
    a = por_dimensao(fa, dimensao, base_custo=base_custo).select(
        pl.col("chave").cast(pl.Utf8), pl.col("rotulo").cast(pl.Utf8),
        pl.col(metrica).cast(pl.Float64).alias("valor_a"),
        pl.col("ton_liquida").cast(pl.Float64).alias("ton_a"),
        pl.col("pmv").cast(pl.Float64).alias("pmv_a"),
    )
    b = por_dimensao(fb, dimensao, base_custo=base_custo).select(
        pl.col("chave").cast(pl.Utf8), pl.col("rotulo").cast(pl.Utf8),
        pl.col(metrica).cast(pl.Float64).alias("valor_b"),
        pl.col("ton_liquida").cast(pl.Float64).alias("ton_b"),
        pl.col("pmv").cast(pl.Float64).alias("pmv_b"),
    )

    df = a.join(b, on=["chave", "rotulo"], how="full", coalesce=True).with_columns(
        pl.col("valor_a").fill_null(0.0), pl.col("valor_b").fill_null(0.0),
        pl.col("ton_a").fill_null(0.0), pl.col("ton_b").fill_null(0.0),
    )
    total_var = float((df["valor_b"] - df["valor_a"]).sum())
    df = df.with_columns(
        (pl.col("valor_b") - pl.col("valor_a")).alias("variacao"),
    ).with_columns(
        pl.when(pl.col("valor_a") != 0)
        .then(100 * pl.col("variacao") / pl.col("valor_a").abs())
        .otherwise(None)
        .alias("variacao_pct"),
        (100 * pl.col("variacao") / total_var if total_var else pl.lit(None))
        .alias("contribuicao_pct"),
        # Decomposicao volume x preco (efeito preco = ton_b * (pmv_b - pmv_a))
        ((pl.col("ton_b") - pl.col("ton_a")) * pl.col("pmv_a").fill_null(0)).alias("efeito_volume"),
        (pl.col("ton_b") * (pl.col("pmv_b").fill_null(0) - pl.col("pmv_a").fill_null(0))).alias("efeito_preco"),
    )
    return df.sort("variacao", descending=True)


def detalhe_documentos(f: Filtros, limite: int = 500) -> pl.DataFrame:
    """Nivel de documento no drill-down."""
    where, params = f.where(COLUNAS_VENDA_ITEM)
    return read_sql(
        f"""
        SELECT nunota, numnota, MAX(data_referencia) AS data, MAX(parceiro) AS cliente,
               MAX(vendedor) AS vendedor, MAX(uf_cliente) AS uf, MAX(cif_fob) AS cif_fob,
               COUNT(*) AS itens,
               SUM(vlrtot) AS receita, SUM(tonliq) AS toneladas,
               SUM(vlrfrete_alocado) AS frete,
               MAX(documento_vlrnota) AS valor_documento,
               bool_or(is_devolucao) AS tem_devolucao
        FROM analytics.v_venda_item
        WHERE {where}
        GROUP BY nunota, numnota
        ORDER BY MAX(data_referencia) DESC, ABS(SUM(vlrtot)) DESC
        LIMIT {int(limite)}
        """,
        params,
    )


def itens_do_documento(nunota: int) -> pl.DataFrame:
    """Ultimo nivel do drill-down: a transacao original."""
    return read_sql(
        """
        SELECT sequencia, codprod, descrprod, classificacao, codvol, qtd, tonliq,
               vlrunit, vlrtot, vlrdesc, perccom, vlrcom, vlricms, vlrsubst,
               vlrfrete_alocado, cost_match_status, cost_match_date, cost_age_days,
               cusmed, cusmedicm, cussemicm, cusrep, cusger, cusvariavel,
               tipmov, is_devolucao, controle
        FROM analytics.v_venda_item
        WHERE nunota = :n
        ORDER BY sequencia
        """,
        {"n": nunota},
    )


def cabecalho_documento(nunota: int) -> dict:
    df = read_sql(
        """
        SELECT d.*, c.parceiro, c.uf AS uf_cliente, c.cidade AS cidade_cliente,
               v.apelido AS vendedor, t.nome_transp
        FROM analytics.fact_venda_documento d
        LEFT JOIN analytics.dim_cliente c       ON c.codparc = d.codparc
        LEFT JOIN analytics.dim_vendedor v      ON v.codvend = d.codvend
        LEFT JOIN analytics.dim_transportador t ON t.codparc_transp = d.codparctransp
        WHERE d.nunota = :n
        """,
        {"n": nunota},
    )
    return df.to_dicts()[0] if df.height else {}


def opcoes_filtro() -> dict[str, pl.DataFrame]:
    """Valores disponiveis para os seletores da barra lateral."""
    return {
        "periodos": read_sql(
            "SELECT DISTINCT ano_mes FROM analytics.mv_sales_month ORDER BY ano_mes"
        ),
        "classificacoes": read_sql(
            "SELECT DISTINCT classificacao FROM analytics.dim_produto "
            "WHERE classificacao IS NOT NULL ORDER BY 1"
        ),
        "produtos": read_sql(
            "SELECT codprod, descrprod, classificacao FROM analytics.dim_produto ORDER BY descrprod"
        ),
        "ufs": read_sql(
            "SELECT DISTINCT uf FROM analytics.dim_cliente WHERE uf IS NOT NULL ORDER BY 1"
        ),
        "regioes": read_sql(
            "SELECT codreg, nomereg FROM analytics.dim_regiao WHERE nomereg IS NOT NULL ORDER BY nomereg"
        ),
        "vendedores": read_sql(
            """
            SELECT v.codvend, v.apelido, v.papel_analitico
            FROM analytics.dim_vendedor v
            WHERE EXISTS (SELECT 1 FROM analytics.fact_venda_item i WHERE i.codvend = v.codvend)
            ORDER BY v.apelido
            """
        ),
        "papeis": read_sql(
            "SELECT DISTINCT papel_analitico FROM analytics.dim_vendedor ORDER BY 1"
        ),
        "ramos": read_sql(
            "SELECT DISTINCT ramo_atividade FROM analytics.dim_cliente "
            "WHERE ramo_atividade IS NOT NULL ORDER BY 1"
        ),
        "empresas": read_sql(
            "SELECT DISTINCT codemp FROM analytics.fact_venda_item WHERE codemp IS NOT NULL ORDER BY 1"
        ),
        "cif_fob": read_sql(
            "SELECT DISTINCT cif_fob FROM analytics.fact_venda_item WHERE cif_fob IS NOT NULL ORDER BY 1"
        ),
    }
