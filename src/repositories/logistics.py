"""
Consultas de logistica (CT-e, frete, rotas).

Toda metrica aqui cobre APENAS o frete alocado a notas de venda. O percentual
nao alocado acompanha as consultas para que a interface nunca apresente o
custo logistico como se fosse completo (RN-08).
"""
from __future__ import annotations

import polars as pl

from src.db.engine import read_sql
from src.repositories.filters import Filtros


def _where_documento(f: Filtros) -> tuple[str, dict]:
    colunas = {
        "periodo": "d.ano_mes",
        "empresa": "d.codemp",
        "uf": "c.uf",
        "regiao": "d.codreg",
        "vendedor": "d.codvend",
        "cliente": "d.codparc",
        "cif_fob": "d.cif_fob",
        "is_devolucao": "d.is_devolucao",
    }
    return f.where(colunas)


def cobertura(f: Filtros | None = None) -> dict[str, float]:
    """Indicadores de honestidade: quanto do frete NAO esta alocado."""
    df = read_sql(
        """
        SELECT
            (SELECT COUNT(*) FROM analytics.fact_cte)                              AS cte_total,
            (SELECT COUNT(*) FROM analytics.fact_cte WHERE qtd_nfe_vinculadas = 0) AS cte_sem_nfe,
            (SELECT COALESCE(SUM(vlrnota), 0) FROM analytics.fact_cte)             AS frete_total,
            (SELECT COALESCE(SUM(vlrfrete_alocado), 0) FROM analytics.bridge_cte_nfe
              WHERE match_status <> 'SEM_VINCULO')                                 AS frete_alocado,
            (SELECT COUNT(*) FROM analytics.bridge_cte_nfe
              WHERE match_status = 'SEM_VINCULO')                                  AS vinculos_sem_match,
            (SELECT COUNT(*) FROM analytics.fact_cte
              WHERE ordemcarga IS NULL OR ordemcarga = 0)                          AS cte_sem_ordem
        """
    )
    r = df.to_dicts()[0]
    total = float(r["frete_total"] or 0)
    alocado = float(r["frete_alocado"] or 0)
    return {
        **{k: float(v or 0) for k, v in r.items()},
        "frete_nao_alocado": total - alocado,
        "pct_frete_nao_alocado": (100 * (total - alocado) / total) if total else 0.0,
        "pct_cte_sem_nfe": (100 * r["cte_sem_nfe"] / r["cte_total"]) if r["cte_total"] else 0.0,
        "pct_cte_sem_ordem": (100 * r["cte_sem_ordem"] / r["cte_total"]) if r["cte_total"] else 0.0,
    }


def serie_mensal(f: Filtros) -> pl.DataFrame:
    where, params = _where_documento(f)
    return read_sql(
        f"""
        SELECT d.ano_mes,
               SUM(b.vlrfrete_alocado)                       AS frete,
               SUM(ABS(t.ton))                               AS ton,
               CASE WHEN SUM(ABS(t.ton)) > 0
                    THEN SUM(b.vlrfrete_alocado) / SUM(ABS(t.ton)) END AS frete_por_ton,
               SUM(t.receita)                                AS receita,
               CASE WHEN SUM(t.receita) <> 0
                    THEN 100 * SUM(b.vlrfrete_alocado) / SUM(t.receita) END AS frete_sobre_receita,
               COUNT(DISTINCT b.frete_id)                    AS ctes,
               COUNT(DISTINCT d.nunota)                      AS notas
        FROM analytics.bridge_cte_nfe b
        JOIN analytics.fact_venda_documento d ON d.nunota = b.nunota_venda
        LEFT JOIN analytics.dim_cliente c     ON c.codparc = d.codparc
        LEFT JOIN (
            SELECT nunota, SUM(tonliq) AS ton, SUM(vlrtot) AS receita
            FROM analytics.fact_venda_item GROUP BY nunota
        ) t ON t.nunota = d.nunota
        WHERE b.match_status <> 'SEM_VINCULO' AND {where}
        GROUP BY d.ano_mes ORDER BY d.ano_mes
        """,
        params,
    )


def rotas(f: Filtros, limite: int = 200) -> pl.DataFrame:
    where, params = _where_documento(f)
    return read_sql(
        f"""
        SELECT COALESCE(d.cidorigem, '—') || ' → ' || COALESCE(d.ciddestino, '—') AS rota,
               d.uforigem, d.ufdestino, d.cidorigem, d.ciddestino, d.cif_fob,
               COUNT(DISTINCT b.frete_id)  AS ctes,
               COUNT(DISTINCT d.nunota)    AS notas,
               SUM(b.vlrfrete_alocado)     AS frete,
               SUM(ABS(t.ton))             AS ton,
               CASE WHEN SUM(ABS(t.ton)) > 0
                    THEN SUM(b.vlrfrete_alocado) / SUM(ABS(t.ton)) END AS frete_por_ton,
               CASE WHEN COUNT(DISTINCT d.nunota) > 0
                    THEN SUM(ABS(t.ton)) / COUNT(DISTINCT d.nunota) END AS carga_media_ton
        FROM analytics.bridge_cte_nfe b
        JOIN analytics.fact_venda_documento d ON d.nunota = b.nunota_venda
        LEFT JOIN analytics.dim_cliente c     ON c.codparc = d.codparc
        LEFT JOIN (
            SELECT nunota, SUM(tonliq) AS ton FROM analytics.fact_venda_item GROUP BY nunota
        ) t ON t.nunota = d.nunota
        WHERE b.match_status <> 'SEM_VINCULO' AND {where}
        GROUP BY 1, 2, 3, 4, 5, 6
        HAVING SUM(ABS(t.ton)) > 0
        ORDER BY frete DESC NULLS LAST
        LIMIT {int(limite)}
        """,
        params,
    )


def por_dimensao_logistica(f: Filtros, dimensao: str, limite: int = 50) -> pl.DataFrame:
    colunas = {
        "transportador": "COALESCE(tr.nome_transp, ct.nomeparc, d.codparctransp::text)",
        "uf_destino": "d.ufdestino",
        "cidade_destino": "d.ciddestino",
        "uf_origem": "d.uforigem",
        "cliente": "c.parceiro",
        "vendedor": "v.apelido",
        "cif_fob": "d.cif_fob",
    }
    if dimensao not in colunas:
        raise KeyError(f"Dimensão logística '{dimensao}' não suportada.")
    col = colunas[dimensao]
    where, params = _where_documento(f)

    return read_sql(
        f"""
        SELECT {col} AS rotulo,
               COUNT(DISTINCT b.frete_id) AS ctes,
               COUNT(DISTINCT d.nunota)   AS notas,
               SUM(b.vlrfrete_alocado)    AS frete,
               SUM(ABS(t.ton))            AS ton,
               CASE WHEN SUM(ABS(t.ton)) > 0
                    THEN SUM(b.vlrfrete_alocado) / SUM(ABS(t.ton)) END AS frete_por_ton,
               SUM(t.receita)             AS receita,
               CASE WHEN SUM(t.receita) <> 0
                    THEN 100 * SUM(b.vlrfrete_alocado) / SUM(t.receita) END AS frete_sobre_receita
        FROM analytics.bridge_cte_nfe b
        JOIN analytics.fact_venda_documento d ON d.nunota = b.nunota_venda
        LEFT JOIN analytics.dim_cliente c       ON c.codparc = d.codparc
        LEFT JOIN analytics.dim_vendedor v      ON v.codvend = d.codvend
        LEFT JOIN analytics.dim_transportador tr ON tr.codparc_transp = d.codparctransp
        LEFT JOIN analytics.fact_cte ct         ON ct.frete_id = b.frete_id
        LEFT JOIN (
            SELECT nunota, SUM(tonliq) AS ton, SUM(vlrtot) AS receita
            FROM analytics.fact_venda_item GROUP BY nunota
        ) t ON t.nunota = d.nunota
        WHERE b.match_status <> 'SEM_VINCULO' AND {where}
        GROUP BY 1
        HAVING SUM(ABS(t.ton)) > 0
        ORDER BY frete DESC NULLS LAST
        LIMIT {int(limite)}
        """,
        params,
    )


def dispersao_carga(f: Filtros, limite: int = 3000) -> pl.DataFrame:
    """Tonelagem x R$/t por nota — mostra se carga pequena custa mais."""
    where, params = _where_documento(f)
    return read_sql(
        f"""
        SELECT d.nunota, d.ano_mes,
               COALESCE(d.cidorigem, '—') || ' → ' || COALESCE(d.ciddestino, '—') AS rota,
               d.ufdestino, d.cif_fob,
               SUM(b.vlrfrete_alocado) AS frete,
               ABS(MAX(t.ton))         AS ton,
               CASE WHEN ABS(MAX(t.ton)) > 0
                    THEN SUM(b.vlrfrete_alocado) / ABS(MAX(t.ton)) END AS frete_por_ton
        FROM analytics.bridge_cte_nfe b
        JOIN analytics.fact_venda_documento d ON d.nunota = b.nunota_venda
        LEFT JOIN analytics.dim_cliente c     ON c.codparc = d.codparc
        LEFT JOIN (
            SELECT nunota, SUM(tonliq) AS ton FROM analytics.fact_venda_item GROUP BY nunota
        ) t ON t.nunota = d.nunota
        WHERE b.match_status <> 'SEM_VINCULO' AND {where}
        GROUP BY d.nunota, d.ano_mes, 3, d.ufdestino, d.cif_fob
        HAVING ABS(MAX(t.ton)) > 0
        ORDER BY frete DESC
        LIMIT {int(limite)}
        """,
        params,
    )


def ctes_do_documento(nunota: int) -> pl.DataFrame:
    """Último nível do drill logístico: os CT-e que cobrem uma nota."""
    return read_sql(
        """
        SELECT c.chavecte, c.numnota, c.dtneg, c.descroper, c.nomeparc AS transportador,
               c.vlrnota AS valor_cte, c.qtd_nfe_vinculadas,
               b.allocation_weight, b.allocation_method, b.vlrfrete_alocado, b.match_status
        FROM analytics.bridge_cte_nfe b
        JOIN analytics.fact_cte c ON c.frete_id = b.frete_id
        WHERE b.nunota_venda = :n
        ORDER BY b.vlrfrete_alocado DESC
        """,
        {"n": nunota},
    )
