"""
Consultas da camada geografica de mercado (Minas Gerais).

Tres camadas que a pagina sobrepoe:

    CAMADA 1  venda do Moinho por municipio
    CAMADA 2  territorio declarado dos RCAs
    CAMADA 3  mercado potencial (CEMPRE/IBGE + consumo observado)

A classificacao em quadrantes de White Space mora aqui, e nao no SQL, porque
depende de percentis que o usuario pode mover na tela. O SQL entrega numeros;
a leitura estrategica e aplicada em cima deles.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl

from src.config import load_yaml
from src.db.engine import read_sql
from src.ingestion.mercado_ibge import GEOJSON_LEVE, GEOJSON_NOME, geo_path


def config() -> dict[str, Any]:
    return load_yaml("mercado_mg.yaml")


def janela_padrao() -> int:
    return int(config()["modelo"]["janela_vendas_meses"])


def classificacoes_padrao() -> list[str]:
    return list(config()["classificacoes_no_escopo"])


# =====================================================================
# Camada 1 + 2 + 3 — a tabela municipal completa
# =====================================================================
def municipios(
    janela_meses: int | None = None,
    classificacoes: list[str] | None = None,
) -> pl.DataFrame:
    """
    Uma linha por municipio de MG (os 853), com as tres camadas sobrepostas.

    `janela_meses` recorta a venda considerada "presenca atual"; `classificacoes`
    define o que conta como farinha. Os defaults vem de config/mercado_mg.yaml e
    reproduzem exatamente a materialized view mv_mercado_municipio_mg.
    """
    janela = janela_meses or janela_padrao()
    classes = classificacoes or classificacoes_padrao()

    marcadores = ", ".join(f":cls{i}" for i in range(len(classes)))
    params: dict[str, Any] = {f"cls{i}": c for i, c in enumerate(classes)}
    params["janela"] = janela

    return read_sql(
        f"""
        WITH limite AS (
            SELECT MAX(ano_mes) AS fim,
                   to_char(to_date(MAX(ano_mes), 'YYYY-MM')
                           - make_interval(months => :janela), 'YYYY-MM') AS inicio
            FROM analytics.mv_vendas_municipio_mg
        ),
        venda AS (
            SELECT v.cod_ibge,
                   SUM(v.ton_liquida)                                       AS ton_total,
                   SUM(v.ton_liquida) FILTER (WHERE v.classificacao IN ({marcadores}))
                                                                            AS ton_farinha,
                   SUM(v.receita_liquida) FILTER (WHERE v.classificacao IN ({marcadores}))
                                                                            AS receita_farinha,
                   SUM(v.receita_liquida)                                   AS receita_total,
                   SUM(v.receita_para_pmv) FILTER (WHERE v.classificacao IN ({marcadores}))
                                                                            AS receita_pmv,
                   SUM(v.ton_para_pmv) FILTER (WHERE v.classificacao IN ({marcadores}))
                                                                            AS ton_pmv,
                   SUM(v.frete)                                             AS frete,
                   MAX(v.ano_mes)                                           AS ultimo_mes,
                   COUNT(DISTINCT v.ano_mes)                                AS meses_com_venda
            FROM analytics.mv_vendas_municipio_mg v
            CROSS JOIN limite l
            WHERE v.ano_mes > l.inicio
            GROUP BY v.cod_ibge
        ),
        clientes AS (
            SELECT m.cod_ibge,
                   COUNT(DISTINCT c.codparc)                                AS clientes_cadastrados,
                   COUNT(DISTINCT c.codparc) FILTER (
                       WHERE to_char(c.ultima_compra, 'YYYY-MM') > l.inicio) AS clientes_ativos
            FROM analytics.dim_cliente c
            JOIN analytics.map_cidade_ibge m
              ON m.origem = 'CLIENTE' AND m.cidade_texto = c.cidade
            CROSS JOIN limite l
            WHERE c.uf = 'MG' AND m.cod_ibge IS NOT NULL
            GROUP BY m.cod_ibge
        ),
        mercado AS (
            SELECT cod_ibge,
                   SUM(unidades_locais)                                     AS estabelecimentos,
                   SUM(unidades_locais) FILTER (WHERE segmento = 'panificacao')
                                                                            AS estab_panificacao,
                   SUM(unidades_locais) FILTER (
                       WHERE segmento IN ('biscoitos','massas','pratos_prontos'))
                                                                            AS estab_industria,
                   SUM(unidades_locais) FILTER (WHERE segmento = 'food_service')
                                                                            AS estab_food_service,
                   SUM(unidades_locais) FILTER (
                       WHERE segmento IN ('atacado_farinhas','atacado_alimentos'))
                                                                            AS estab_distribuidores
            FROM analytics.fact_mercado_cnae
            GROUP BY cod_ibge
        ),
        potencial AS (
            SELECT cod_ibge,
                   SUM(potencial_t_mes)                                     AS potencial_t_mes,
                   SUM(potencial_capturavel_t_mes)                          AS teto_t_mes,
                   SUM(potencial_capturavel_t_mes) FILTER (
                       WHERE segmento IN ('panificacao','biscoitos','massas','pratos_prontos'))
                                                                            AS teto_industria_t_mes,
                   SUM(potencial_capturavel_t_mes) FILTER (
                       WHERE segmento IN ('atacado_farinhas','atacado_alimentos'))
                                                                            AS teto_distribuidor_t_mes
            FROM analytics.fact_potencial_municipio
            GROUP BY cod_ibge
        ),
        territorio AS (
            SELECT cod_ibge,
                   STRING_AGG(DISTINCT representante, ' | ' ORDER BY representante)
                                                                            AS representantes,
                   STRING_AGG(DISTINCT regiao_comercial, ' | ' ORDER BY regiao_comercial)
                                                                            AS regioes_comerciais,
                   COUNT(DISTINCT representante)                            AS qtd_representantes
            FROM analytics.dim_territorio_rca
            GROUP BY cod_ibge
        )
        SELECT
            d.cod_ibge,
            d.municipio,
            d.regiao_intermediaria,
            d.regiao_imediata,
            d.mesorregiao,
            d.populacao,

            COALESCE(v.ton_farinha, 0)                                      AS ton_farinha,
            COALESCE(v.ton_total, 0)                                        AS ton_total,
            COALESCE(v.receita_farinha, 0)                                  AS receita_farinha,
            COALESCE(v.ton_farinha, 0) / :janela                            AS venda_t_mes,
            v.receita_pmv / NULLIF(v.ton_pmv, 0)                            AS pmv,
            CASE WHEN COALESCE(v.ton_total, 0) <> 0
                 THEN v.frete / NULLIF(ABS(v.ton_total), 0) END             AS frete_por_ton,
            COALESCE(v.meses_com_venda, 0)                                  AS meses_com_venda,
            v.ultimo_mes,
            COALESCE(c.clientes_ativos, 0)                                  AS clientes_ativos,
            COALESCE(c.clientes_cadastrados, 0)                             AS clientes_cadastrados,

            t.representantes,
            t.regioes_comerciais,
            COALESCE(t.qtd_representantes, 0)                               AS qtd_representantes,

            COALESCE(mk.estabelecimentos, 0)                                AS estabelecimentos,
            COALESCE(mk.estab_panificacao, 0)                               AS estab_panificacao,
            COALESCE(mk.estab_industria, 0)                                 AS estab_industria,
            COALESCE(mk.estab_food_service, 0)                              AS estab_food_service,
            COALESCE(mk.estab_distribuidores, 0)                            AS estab_distribuidores,
            COALESCE(p.potencial_t_mes, 0)                                  AS potencial_t_mes,
            COALESCE(p.teto_t_mes, 0)                                       AS teto_t_mes,
            COALESCE(p.teto_industria_t_mes, 0)                             AS teto_industria_t_mes,
            COALESCE(p.teto_distribuidor_t_mes, 0)                          AS teto_distribuidor_t_mes,

            CASE WHEN COALESCE(mk.estabelecimentos, 0) > 0
                 THEN 100.0 * COALESCE(c.clientes_ativos, 0) / mk.estabelecimentos END
                                                                            AS penetracao_pct,
            CASE WHEN COALESCE(p.teto_t_mes, 0) > 0
                 THEN 100.0 * (COALESCE(v.ton_farinha, 0) / :janela) / p.teto_t_mes END
                                                                            AS captura_pct,
            GREATEST(COALESCE(p.teto_t_mes, 0)
                     - COALESCE(v.ton_farinha, 0) / :janela, 0)             AS espaco_t_mes,
            (COALESCE(v.ton_total, 0) <> 0)                                 AS tem_venda,
            (COALESCE(t.qtd_representantes, 0) > 0)                         AS tem_territorio
        FROM analytics.dim_municipio_mg d
        LEFT JOIN venda      v  ON v.cod_ibge  = d.cod_ibge
        LEFT JOIN clientes   c  ON c.cod_ibge  = d.cod_ibge
        LEFT JOIN mercado    mk ON mk.cod_ibge = d.cod_ibge
        LEFT JOIN potencial  p  ON p.cod_ibge  = d.cod_ibge
        LEFT JOIN territorio t  ON t.cod_ibge  = d.cod_ibge
        ORDER BY d.municipio
        """,
        params,
    )


# =====================================================================
# Classificacao de White Space
# =====================================================================
def classificar(
    df: pl.DataFrame,
    percentil_potencial: float | None = None,
    percentil_venda: float | None = None,
) -> pl.DataFrame:
    """
    Aplica a matriz potencial x venda do relatorio de pesquisa.

    Os cortes sao PERCENTIS dentro do proprio estado, e nao valores absolutos:
    o que importa e a posicao relativa do municipio entre os 853, e essa leitura
    continua valida quando a serie cresce. Municipios sem nenhum estabelecimento
    consumidor ficam fora da classificacao (SEM_MERCADO) em vez de inflarem o
    quadrante de baixa prioridade.

    Cada percentil e calculado na populacao que lhe faz sentido: o de potencial
    entre os municipios COM mercado, e o de venda entre os municipios COM VENDA.
    Calcular o corte de venda sobre os 853 colocaria o percentil 70 em zero -
    733 municipios nao vendem nada - e todo municipio do estado seria promovido
    a "venda alta", esvaziando justamente o quadrante de White Space.
    """
    ws = config()["white_space"]
    p_pot = percentil_potencial if percentil_potencial is not None else ws["percentil_potencial_alto"]
    p_ven = percentil_venda if percentil_venda is not None else ws["percentil_venda_alta"]

    com_mercado = df.filter(pl.col("teto_t_mes") > 0)
    if com_mercado.height == 0:
        return df.with_columns(
            pl.lit("SEM_MERCADO").alias("quadrante"),
            pl.lit("Sem mercado mapeado").alias("quadrante_rotulo"),
            pl.lit("#94A3B8").alias("quadrante_cor"),
            pl.lit("").alias("quadrante_acao"),
        )

    com_venda = df.filter(pl.col("venda_t_mes") > 0)
    corte_pot = float(com_mercado["teto_t_mes"].quantile(p_pot) or 0)
    corte_ven = (
        float(com_venda["venda_t_mes"].quantile(p_ven) or 0) if com_venda.height else 0.0
    )

    classes = ws["classes"]
    rotulos = {k: v["rotulo"] for k, v in classes.items()}
    cores = {k: v["cor"] for k, v in classes.items()}
    acoes = {k: v["acao"] for k, v in classes.items()}
    rotulos["SEM_MERCADO"] = "Sem mercado mapeado"
    cores["SEM_MERCADO"] = "#CBD5E1"
    acoes["SEM_MERCADO"] = "Nenhum estabelecimento consumidor no CEMPRE"

    # Venda zero e sempre "venda baixa", independente de onde caia o percentil.
    venda_alta = (pl.col("venda_t_mes") > 0) & (pl.col("venda_t_mes") >= corte_ven)

    quadrante = (
        pl.when(pl.col("teto_t_mes") <= 0)
        .then(pl.lit("SEM_MERCADO"))
        .when((pl.col("teto_t_mes") >= corte_pot) & venda_alta)
        .then(pl.lit("ALTO_ALTA"))
        .when((pl.col("teto_t_mes") >= corte_pot) & ~venda_alta)
        .then(pl.lit("ALTO_BAIXA"))
        .when((pl.col("teto_t_mes") < corte_pot) & venda_alta)
        .then(pl.lit("BAIXO_ALTA"))
        .otherwise(pl.lit("BAIXO_BAIXA"))
        .alias("quadrante")
    )

    return df.with_columns(quadrante).with_columns(
        pl.col("quadrante").replace_strict(rotulos, default="—").alias("quadrante_rotulo"),
        pl.col("quadrante").replace_strict(cores, default="#94A3B8").alias("quadrante_cor"),
        pl.col("quadrante").replace_strict(acoes, default="").alias("quadrante_acao"),
        pl.lit(corte_pot).alias("_corte_potencial"),
        pl.lit(corte_ven).alias("_corte_venda"),
    )


# =====================================================================
# Resumos
# =====================================================================
def resumo_estado(df: pl.DataFrame) -> dict[str, float]:
    """Cartoes do topo da pagina, calculados sobre o recorte ja carregado."""
    total_mun = df.height
    com_venda = int(df.filter(pl.col("tem_venda")).height)
    com_territorio = int(df.filter(pl.col("tem_territorio")).height)
    enderecavel = float(df["potencial_t_mes"].sum() or 0)
    teto = float(df["teto_t_mes"].sum() or 0)
    venda = float(df["venda_t_mes"].sum() or 0)
    espaco = float(df["espaco_t_mes"].sum() or 0)
    return {
        "municipios": total_mun,
        "com_venda": com_venda,
        "sem_venda": total_mun - com_venda,
        "cobertura_pct": 100 * com_venda / total_mun if total_mun else 0,
        "com_territorio": com_territorio,
        "venda_sem_territorio": int(
            df.filter(pl.col("tem_venda") & ~pl.col("tem_territorio")).height
        ),
        "territorio_sem_venda": int(
            df.filter(~pl.col("tem_venda") & pl.col("tem_territorio")).height
        ),
        "enderecavel_t_mes": enderecavel,
        "teto_t_mes": teto,
        "venda_t_mes": venda,
        "espaco_t_mes": espaco,
        "share_enderecavel_pct": 100 * venda / enderecavel if enderecavel else 0,
        "crescimento_possivel_pct": 100 * espaco / venda if venda else 0,
        "clientes_ativos": int(df["clientes_ativos"].sum() or 0),
        "estabelecimentos": int(df["estabelecimentos"].sum() or 0),
        "populacao": int(df["populacao"].sum() or 0),
        "populacao_sem_venda": int(
            df.filter(~pl.col("tem_venda"))["populacao"].sum() or 0
        ),
    }


def por_regiao(df: pl.DataFrame, coluna: str = "regiao_intermediaria") -> pl.DataFrame:
    """Agrega a visao municipal em regioes oficiais do IBGE."""
    return (
        df.group_by(coluna)
        .agg(
            pl.len().alias("municipios"),
            pl.col("tem_venda").sum().alias("municipios_com_venda"),
            pl.col("tem_territorio").sum().alias("municipios_com_territorio"),
            pl.col("populacao").sum().alias("populacao"),
            pl.col("estabelecimentos").sum().alias("estabelecimentos"),
            pl.col("clientes_ativos").sum().alias("clientes_ativos"),
            pl.col("venda_t_mes").sum().alias("venda_t_mes"),
            pl.col("ton_farinha").sum().alias("ton_farinha"),
            pl.col("receita_farinha").sum().alias("receita_farinha"),
            pl.col("potencial_t_mes").sum().alias("enderecavel_t_mes"),
            pl.col("teto_t_mes").sum().alias("teto_t_mes"),
            pl.col("espaco_t_mes").sum().alias("espaco_t_mes"),
            pl.col("qtd_representantes").max().alias("max_representantes"),
        )
        .with_columns(
            (100 * pl.col("municipios_com_venda") / pl.col("municipios")).alias("cobertura_pct"),
            (100 * pl.col("venda_t_mes") / pl.col("teto_t_mes").replace(0, None))
            .alias("captura_pct"),
            (100 * pl.col("clientes_ativos") / pl.col("estabelecimentos").replace(0, None))
            .alias("penetracao_pct"),
        )
        .sort("espaco_t_mes", descending=True)
    )


# =====================================================================
# Camada 2 — territorio
# =====================================================================
def cobertura_por_representante() -> pl.DataFrame:
    """
    Territorio DECLARADO x resultado OBSERVADO, por representante.

    Responde a pergunta do relatorio: "um RCA com 150 toneladas performa melhor
    que outro com 300, considerando o territorio que cada um recebeu?".
    """
    return read_sql(
        """
        WITH territorio AS (
            SELECT representante,
                   COUNT(DISTINCT cod_ibge)                     AS cidades_atribuidas,
                   STRING_AGG(DISTINCT fonte, '+' ORDER BY fonte) AS fontes
            FROM analytics.dim_territorio_rca
            GROUP BY representante
        ),
        mercado_do_territorio AS (
            SELECT t.representante,
                   SUM(p.teto)                                  AS teto_t_mes,
                   SUM(m.populacao)                             AS populacao,
                   SUM(COALESCE(e.estabelecimentos, 0))         AS estabelecimentos
            FROM (SELECT DISTINCT representante, cod_ibge FROM analytics.dim_territorio_rca) t
            JOIN analytics.dim_municipio_mg m ON m.cod_ibge = t.cod_ibge
            LEFT JOIN (
                SELECT cod_ibge, SUM(potencial_capturavel_t_mes) AS teto
                FROM analytics.fact_potencial_municipio GROUP BY cod_ibge
            ) p ON p.cod_ibge = t.cod_ibge
            LEFT JOIN (
                SELECT cod_ibge, SUM(unidades_locais) AS estabelecimentos
                FROM analytics.fact_mercado_cnae GROUP BY cod_ibge
            ) e ON e.cod_ibge = t.cod_ibge
            GROUP BY t.representante
        ),
        vendido AS (
            SELECT t.representante,
                   COUNT(DISTINCT v.cod_ibge) FILTER (WHERE v.ton_liquida <> 0)
                                                                AS cidades_com_venda,
                   SUM(v.ton_liquida)                           AS ton_12m
            FROM (SELECT DISTINCT representante, cod_ibge FROM analytics.dim_territorio_rca) t
            LEFT JOIN analytics.mv_vendas_municipio_mg v ON v.cod_ibge = t.cod_ibge
            CROSS JOIN (SELECT MAX(ano_mes) fim FROM analytics.mv_vendas_municipio_mg) l
            WHERE v.ano_mes > to_char(to_date(l.fim, 'YYYY-MM') - INTERVAL '12 months', 'YYYY-MM')
            GROUP BY t.representante
        )
        SELECT t.representante,
               t.cidades_atribuidas,
               t.fontes,
               COALESCE(v.cidades_com_venda, 0)                 AS cidades_com_venda,
               COALESCE(v.ton_12m, 0) / 12.0                    AS venda_t_mes,
               COALESCE(mk.teto_t_mes, 0)                       AS teto_t_mes,
               COALESCE(mk.populacao, 0)                        AS populacao,
               COALESCE(mk.estabelecimentos, 0)                 AS estabelecimentos,
               CASE WHEN t.cidades_atribuidas > 0
                    THEN 100.0 * COALESCE(v.cidades_com_venda, 0) / t.cidades_atribuidas END
                                                                AS ativacao_pct,
               CASE WHEN COALESCE(mk.teto_t_mes, 0) > 0
                    THEN 100.0 * (COALESCE(v.ton_12m, 0) / 12.0) / mk.teto_t_mes END
                                                                AS captura_pct
        FROM territorio t
        LEFT JOIN vendido v               ON v.representante  = t.representante
        LEFT JOIN mercado_do_territorio mk ON mk.representante = t.representante
        ORDER BY teto_t_mes DESC
        """
    )


def lacunas_territoriais(df: pl.DataFrame) -> dict[str, pl.DataFrame]:
    """
    Onde a atribuicao de territorio e a realidade de venda nao conversam.

    Tres lacunas distintas, cada uma com uma acao diferente:
      orfaos      mercado relevante, sem venda e sem RCA responsavel
      sem_dono    venda acontecendo em cidade que nenhum RCA declara atender
      inativos    RCA declara a cidade, ha mercado, e nao ha venda
    """
    return {
        "orfaos": (
            df.filter(~pl.col("tem_venda") & ~pl.col("tem_territorio") & (pl.col("teto_t_mes") > 0))
            .sort("teto_t_mes", descending=True)
        ),
        "sem_dono": (
            df.filter(pl.col("tem_venda") & ~pl.col("tem_territorio"))
            .sort("venda_t_mes", descending=True)
        ),
        "inativos": (
            df.filter(pl.col("tem_territorio") & ~pl.col("tem_venda") & (pl.col("teto_t_mes") > 0))
            .sort("teto_t_mes", descending=True)
        ),
    }


# =====================================================================
# Camada 3 — mercado e calibragem
# =====================================================================
def segmentos_mercado() -> pl.DataFrame:
    """Universo de estabelecimentos e potencial por segmento, no estado inteiro."""
    df = read_sql(
        """
        SELECT p.segmento,
               MAX(m.cnae)                          AS cnae,
               SUM(p.unidades_locais)               AS estabelecimentos,
               MAX(p.consumo_medio_t_mes)           AS consumo_t_mes,
               MAX(p.origem_consumo)                AS origem_consumo,
               MAX(p.clientes_amostra)              AS clientes_amostra,
               MAX(p.prob_captura)                  AS prob_captura,
               SUM(p.potencial_t_mes)               AS enderecavel_t_mes,
               SUM(p.potencial_capturavel_t_mes)    AS teto_t_mes,
               COUNT(DISTINCT p.cod_ibge)           AS municipios_presentes
        FROM analytics.fact_potencial_municipio p
        JOIN analytics.fact_mercado_cnae m
          ON m.cod_ibge = p.cod_ibge AND m.segmento = p.segmento
        GROUP BY p.segmento
        ORDER BY teto_t_mes DESC
        """
    )
    cfg = config()["segmentos"]
    return df.with_columns(
        pl.col("segmento")
        .replace_strict({k: v["rotulo"] for k, v in cfg.items()}, default=None)
        .alias("rotulo"),
        pl.col("segmento")
        .replace_strict({k: v["canal"] for k, v in cfg.items()}, default=None)
        .alias("canal"),
        pl.col("segmento")
        .replace_strict({k: v["papel"] for k, v in cfg.items()}, default=None)
        .alias("papel"),
    )


def qualidade_pareamento() -> pl.DataFrame:
    """Como cada grafia de cidade foi ligada ao IBGE — a transparencia do metodo."""
    return read_sql(
        """
        SELECT m.origem, m.metodo, COUNT(*) AS grafias,
               STRING_AGG(m.cidade_texto, ', ' ORDER BY m.cidade_texto)
                   FILTER (WHERE m.metodo IN ('APROXIMADO','AMBIGUO','NAO_ENCONTRADO'))
                   AS exemplos
        FROM analytics.map_cidade_ibge m
        GROUP BY m.origem, m.metodo
        ORDER BY m.origem, m.metodo
        """
    )


# =====================================================================
# Malha geografica
# =====================================================================
@lru_cache(maxsize=2)
def geojson_municipios(resolucao: str = "detalhe") -> dict[str, Any] | None:
    """
    Malha municipal de MG (IBGE), lida do disco.

    `resolucao='leve'` devolve a versao reduzida, para os mini-mapas do painel:
    o Plotly embute o GeoJSON inteiro em cada figura, entao a resolucao precisa
    acompanhar o tamanho em que o mapa sera exibido.

    Devolve None se o arquivo ainda nao foi baixado — a pagina cai para o
    ranking em barras, que mostra exatamente os mesmos numeros.
    """
    nome = GEOJSON_LEVE if resolucao == "leve" else GEOJSON_NOME
    caminho: Path = geo_path() / nome
    if not caminho.exists():
        # A malha leve e opcional: sem ela, o mini-mapa usa a de detalhe.
        if resolucao == "leve":
            return geojson_municipios("detalhe")
        return None
    with caminho.open("r", encoding="utf-8") as fh:
        return json.load(fh)
