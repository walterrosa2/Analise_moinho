"""
Staging da camada geografica de mercado (Minas Gerais).

Constroi, nesta ordem:

    dim_municipio_mg        853 municipios, o denominador de tudo
    map_cidade_ibge         pareamento auditavel entre grafias e codigo IBGE
    fact_mercado_cnae       estabelecimentos por municipio e segmento (CEMPRE)
    dim_territorio_rca      territorio declarado dos representantes
    fact_potencial_municipio potencial estimado em t/mes

O unico julgamento embutido no codigo e o algoritmo de pareamento de nomes.
Todo o resto - quais CNAEs contam, quanto cada segmento consome, que fracao
e capturavel - vem de config/mercado_mg.yaml.
"""
from __future__ import annotations

import difflib
import unicodedata
from typing import Any

import polars as pl
from loguru import logger

from src.config import get_settings, load_yaml
from src.db.engine import execute, insert_dataframe, read_sql
from src.ingestion.loader import ler_parquet
from src.ingestion.mercado_ibge import ARQ_CNAE, ARQ_MUNICIPIOS

# Similaridade minima para aceitar um pareamento aproximado. Abaixo disso a
# cidade fica como NAO_ENCONTRADO: e preferivel uma lacuna visivel a um
# municipio errado no mapa.
LIMIAR_APROXIMADO = 0.90

# Distancia minima entre o melhor e o segundo melhor candidato. Se dois
# municipios disputam a mesma grafia com scores parecidos, o pareamento e
# AMBIGUO e nao se decide sozinho. Foi o que evitou 'IRAI' virar 'Mirai'
# quando 'Irai de Minas' tambem existe.
MARGEM_DESEMPATE = 0.04

# Conectivos que o cadastro do ERP costuma suprimir:
# 'SAO DOMINGOS PRATA' e 'Sao Domingos do Prata' sao o mesmo municipio.
CONECTIVOS = {"DE", "DA", "DO", "DAS", "DOS", "D", "E", "DEL"}

# Abreviacoes correntes em cadastro brasileiro de cidade.
ABREVIACOES = {
    "S": "SAO", "STA": "SANTA", "STO": "SANTO", "STS": "SANTOS",
    "N": "NOSSA", "SRA": "SENHORA", "PRES": "PRESIDENTE", "GOV": "GOVERNADOR",
    "CEL": "CORONEL", "GAL": "GENERAL", "ENG": "ENGENHEIRO", "PE": "PADRE",
    "CONS": "CONSELHEIRO", "DR": "DOUTOR",
}


# =====================================================================
# Normalizacao de nomes
# =====================================================================
def normalizar_cidade(texto: str | None, sufixos: list[str] | None = None) -> str:
    """
    'Campo Azul, Minas Gerais' -> 'CAMPO AZUL'
    '5357-UBERLANDIA'          -> 'UBERLANDIA'   (o codigo ja saiu no staging de cliente)
    'Sao Goncalo do Para'      -> 'SAO GONCALO DO PARA'

    Remove acento, pontuacao e sufixos de UF; colapsa espacos; devolve maiusculo.
    """
    if texto is None:
        return ""
    valor = str(texto).strip()
    for sufixo in sufixos or []:
        if valor.upper().endswith(sufixo.strip().upper()):
            valor = valor[: -len(sufixo.strip())]
    # tira acento
    valor = "".join(
        c for c in unicodedata.normalize("NFD", valor) if unicodedata.category(c) != "Mn"
    )
    valor = valor.upper()
    # tira o prefixo de codigo, se sobrou
    if "-" in valor and valor.split("-", 1)[0].strip().isdigit():
        valor = valor.split("-", 1)[1]
    for ruido in (".", ",", "'", "`", "/", "-"):
        valor = valor.replace(ruido, " ")
    return " ".join(valor.split())


def _radical(nome_norm: str) -> str:
    """
    Reduz a grafia ao que identifica o municipio: expande abreviacoes e
    descarta conectivos. 'S SEBASTIAO PARAISO' e 'SAO SEBASTIAO DO PARAISO'
    convergem para o mesmo radical, e o pareamento deixa de ser um palpite.
    """
    tokens = []
    for token in nome_norm.split():
        token = ABREVIACOES.get(token, token)
        if token not in CONECTIVOS:
            tokens.append(token)
    return " ".join(tokens)


def _config() -> dict[str, Any]:
    return load_yaml("mercado_mg.yaml")


def _parquet(nome: str) -> pl.DataFrame:
    caminho = get_settings().parquet_path / f"{nome}.parquet"
    if not caminho.exists():
        raise FileNotFoundError(
            f"{caminho.name} nao existe. Rode: py scripts/build_mercado_mg.py"
        )
    return pl.read_parquet(caminho)


# =====================================================================
# 1. dim_municipio_mg
# =====================================================================
def construir_dim_municipio_mg() -> int:
    df = _parquet(ARQ_MUNICIPIOS)
    sufixos = _config()["territorio"]["sufixos_ruido"]

    df = df.with_columns(
        pl.col("municipio")
        .map_elements(lambda v: normalizar_cidade(v, sufixos), return_dtype=pl.Utf8)
        .alias("municipio_norm"),
        pl.lit("MG").alias("uf"),
    )

    execute("TRUNCATE analytics.dim_municipio_mg CASCADE")
    n = insert_dataframe(
        df.select(
            "cod_ibge", "municipio", "municipio_norm", "uf", "microrregiao",
            "mesorregiao", "regiao_imediata", "regiao_intermediaria", "populacao",
        ),
        "dim_municipio_mg",
        "analytics",
    )
    logger.info(f"dim_municipio_mg: {n} municipios de MG")
    return n


# =====================================================================
# 2. map_cidade_ibge
# =====================================================================
def _parear(
    nomes: list[str], catalogo: dict[str, int], sufixos: list[str]
) -> list[dict[str, Any]]:
    """
    Casa cada grafia com um municipio do IBGE em quatro passos, do mais seguro
    ao menos:

      EXATO           grafias identicas apos normalizacao
      SEM_CONECTIVOS  identicas apos expandir abreviacao e tirar 'de/do/da'
      APROXIMADO      similaridade alta, primeiro token igual e sem empate
      NAO_ENCONTRADO  nada disso — a lacuna fica visivel em vez de inventada

    A exigencia de primeiro token igual e o que separa 'CAMPOS ALTO' ->
    'Campos Altos' (legitimo) de 'ANAPOLIS' -> 'Canapolis' (cidade de Goias
    que o arquivo de territorio contem e que nao deve entrar no mapa de MG).
    """
    chaves = list(catalogo)
    por_radical: dict[str, list[int]] = {}
    for nome, cod in catalogo.items():
        por_radical.setdefault(_radical(nome), []).append(cod)

    resultado: list[dict[str, Any]] = []

    for bruto in nomes:
        norm = normalizar_cidade(bruto, sufixos)
        if not norm:
            resultado.append(_sem_match(bruto, ""))
            continue

        if norm in catalogo:
            resultado.append({
                "cidade_texto": bruto, "cidade_norm": norm, "cod_ibge": catalogo[norm],
                "metodo": "EXATO", "similaridade": 1.0,
            })
            continue

        radical = _radical(norm)
        codigos = por_radical.get(radical, [])
        if len(codigos) == 1:
            resultado.append({
                "cidade_texto": bruto, "cidade_norm": norm, "cod_ibge": codigos[0],
                "metodo": "SEM_CONECTIVOS", "similaridade": 1.0,
            })
            continue
        if len(codigos) > 1:
            resultado.append(_sem_match(bruto, norm, metodo="AMBIGUO"))
            continue

        candidatos = difflib.get_close_matches(norm, chaves, n=2, cutoff=LIMIAR_APROXIMADO)
        if not candidatos:
            resultado.append(_sem_match(bruto, norm))
            continue

        alvo = candidatos[0]
        score = difflib.SequenceMatcher(None, norm, alvo).ratio()

        # Empate tecnico entre dois municipios: nao se escolhe no palpite.
        if len(candidatos) > 1:
            segundo = difflib.SequenceMatcher(None, norm, candidatos[1]).ratio()
            if score - segundo < MARGEM_DESEMPATE:
                resultado.append(_sem_match(bruto, norm, metodo="AMBIGUO"))
                continue

        # Primeiro token precisa ser o mesmo: e ele que carrega a identidade.
        if norm.split()[0] != alvo.split()[0]:
            resultado.append(_sem_match(bruto, norm))
            continue

        resultado.append({
            "cidade_texto": bruto, "cidade_norm": norm, "cod_ibge": catalogo[alvo],
            "metodo": "APROXIMADO", "similaridade": round(score, 4),
        })
    return resultado


def _sem_match(bruto: str, norm: str, metodo: str = "NAO_ENCONTRADO") -> dict[str, Any]:
    return {"cidade_texto": bruto, "cidade_norm": norm, "cod_ibge": None,
            "metodo": metodo, "similaridade": None}


def construir_map_cidade_ibge() -> dict[str, Any]:
    """Pareia as tres origens de nome de cidade com o codigo IBGE."""
    cfg = _config()
    sufixos = cfg["territorio"]["sufixos_ruido"]

    municipios = read_sql(
        "SELECT cod_ibge, municipio_norm FROM analytics.dim_municipio_mg"
    )
    catalogo = dict(zip(municipios["municipio_norm"], municipios["cod_ibge"], strict=True))

    origens: dict[str, list[str]] = {}

    # a) cidades dos clientes (so MG)
    clientes = read_sql(
        "SELECT DISTINCT cidade FROM analytics.dim_cliente WHERE uf = 'MG' AND cidade IS NOT NULL"
    )
    origens["CLIENTE"] = clientes["cidade"].to_list()

    # b) aba REGIAO COMERCIAL
    rc = _parquet_fonte(cfg["territorio"]["fonte_regiao_comercial"])
    origens["TERRITORIO_REGIAO"] = (
        rc.select(pl.col("CIDADE")).drop_nulls().unique()["CIDADE"].to_list()
    )

    # c) aba REGIAO POR REPRESENTANTE (so linhas de MG)
    rr = _parquet_fonte(cfg["territorio"]["fonte_regiao_representante"])
    rr_mg = rr.filter(pl.col("ESTADO").is_not_null() & pl.col("ESTADO").str.contains("(?i)minas"))
    origens["TERRITORIO_REPRESENTANTE"] = (
        rr_mg.select(pl.col("CIDADE")).drop_nulls().unique()["CIDADE"].to_list()
    )

    linhas: list[dict[str, Any]] = []
    resumo: dict[str, Any] = {}
    for origem, nomes in origens.items():
        pareado = _parear(nomes, catalogo, sufixos)
        for p in pareado:
            linhas.append({"origem": origem, **p})
        achados = sum(1 for p in pareado if p["cod_ibge"] is not None)
        aprox = sum(1 for p in pareado if p["metodo"] == "APROXIMADO")
        resumo[origem] = {"nomes": len(nomes), "pareados": achados, "aproximados": aprox}
        logger.info(
            f"map_cidade_ibge [{origem}]: {achados}/{len(nomes)} pareados "
            f"({aprox} por similaridade)"
        )

    df = pl.DataFrame(
        linhas,
        schema={
            "origem": pl.Utf8, "cidade_texto": pl.Utf8, "cidade_norm": pl.Utf8,
            "cod_ibge": pl.Int64, "metodo": pl.Utf8, "similaridade": pl.Float64,
        },
    ).unique(subset=["origem", "cidade_texto"], keep="first")

    execute("TRUNCATE analytics.map_cidade_ibge")
    insert_dataframe(df, "map_cidade_ibge", "analytics")

    nao_encontrados = df.filter(pl.col("cod_ibge").is_null())
    if nao_encontrados.height:
        exemplos = nao_encontrados["cidade_texto"].to_list()[:8]
        logger.warning(
            f"map_cidade_ibge: {nao_encontrados.height} grafias sem municipio "
            f"(ex.: {', '.join(map(str, exemplos))})"
        )
    resumo["nao_encontrados"] = nao_encontrados.height
    return resumo


def _parquet_fonte(source_id: str) -> pl.DataFrame:
    """Le um parquet ja produzido pela ingestao normal (nao o de mercado)."""
    return ler_parquet(source_id)


# =====================================================================
# 3. fact_mercado_cnae
# =====================================================================
def construir_fact_mercado_cnae() -> int:
    """
    Carrega o CEMPRE e resolve o sigilo estatistico.

    Quando o IBGE publica 'X' em pessoal ocupado (poucos informantes), o
    municipio recebe o porte medio ESTADUAL daquele segmento multiplicado
    pelas suas unidades. A coluna pessoal_ocupado continua NULL: o dado
    estimado nunca se disfarca de dado publicado.
    """
    df = _parquet(ARQ_CNAE).filter(pl.col("unidades_locais").is_not_null())

    # Porte medio estadual por segmento, so com municipios sem sigilo
    porte_estadual = (
        df.filter(pl.col("pessoal_ocupado").is_not_null())
        .group_by("segmento")
        .agg(
            (pl.col("pessoal_ocupado").sum() / pl.col("unidades_locais").sum())
            .alias("porte_estadual")
        )
    )

    df = (
        df.join(porte_estadual, on="segmento", how="left")
        .with_columns(
            pl.when(pl.col("pessoal_ocupado").is_not_null())
            .then(pl.col("pessoal_ocupado").cast(pl.Float64))
            .otherwise(pl.col("unidades_locais") * pl.col("porte_estadual"))
            .alias("pessoal_estimado")
        )
        .with_columns(
            (pl.col("pessoal_estimado") / pl.col("unidades_locais")).alias("porte_medio")
        )
    )

    # So municipios de MG que existem na dimensao
    validos = read_sql("SELECT cod_ibge FROM analytics.dim_municipio_mg")["cod_ibge"].to_list()
    df = df.filter(pl.col("cod_ibge").is_in(validos))

    execute("TRUNCATE analytics.fact_mercado_cnae")
    n = insert_dataframe(
        df.select(
            "cod_ibge", "segmento", "cnae", "unidades_locais", "pessoal_ocupado",
            "pessoal_estimado", "porte_medio", "periodo_ref",
        ),
        "fact_mercado_cnae",
        "analytics",
    )
    sigilo = df.filter(pl.col("pessoal_ocupado").is_null()).height
    logger.info(
        f"fact_mercado_cnae: {n} linhas municipio x segmento "
        f"({sigilo} com pessoal sob sigilo, porte estimado)"
    )
    return n


# =====================================================================
# 4. dim_territorio_rca
# =====================================================================
def construir_dim_territorio_rca() -> int:
    """
    Une as duas abas do arquivo de regiao comercial, cada uma preservada com
    sua propria origem. Elas discordam entre si (cidades e representantes
    diferentes) - resolver a discordancia e decisao de negocio, nao de ETL.
    """
    cfg = _config()["territorio"]
    mapa = read_sql(
        "SELECT origem, cidade_texto, cod_ibge FROM analytics.map_cidade_ibge "
        "WHERE cod_ibge IS NOT NULL"
    )

    def resolver(origem: str) -> dict[str, int]:
        sub = mapa.filter(pl.col("origem") == origem)
        return dict(zip(sub["cidade_texto"], sub["cod_ibge"], strict=True))

    linhas: list[dict[str, Any]] = []

    # a) CIDADE | REGIAO COMERCIAL | REPRESENTANTE
    rc = _parquet_fonte(cfg["fonte_regiao_comercial"])
    de_para = resolver("TERRITORIO_REGIAO")
    col_regiao = next((c for c in rc.columns if "REGI" in c.upper() and "COMERC" in c.upper()), None)
    for row in rc.iter_rows(named=True):
        cod = de_para.get(row.get("CIDADE"))
        rep = (row.get("REPRESENTANTE") or "").strip()
        if cod and rep:
            linhas.append({
                "cod_ibge": cod,
                "fonte": "REGIAO_COMERCIAL",
                "regiao_comercial": (row.get(col_regiao) or None) if col_regiao else None,
                "representante": rep,
                "codvend": None,
            })

    # b) CIDADE | ESTADO | CODIGO-REPRESENTANTE | REPRESENTANTE
    rr = _parquet_fonte(cfg["fonte_regiao_representante"])
    de_para = resolver("TERRITORIO_REPRESENTANTE")
    col_cod = next((c for c in rr.columns if "CODIGO" in _sem_acento(c).upper()), None)
    for row in rr.iter_rows(named=True):
        cod = de_para.get(row.get("CIDADE"))
        rep = (row.get("REPRESENTANTE") or "").strip()
        if cod and rep:
            codvend = row.get(col_cod) if col_cod else None
            linhas.append({
                "cod_ibge": cod,
                "fonte": "REGIAO_REPRESENTANTE",
                "regiao_comercial": None,
                "representante": rep,
                "codvend": int(codvend) if str(codvend or "").strip().isdigit() else None,
            })

    df = pl.DataFrame(
        linhas,
        schema={
            "cod_ibge": pl.Int64, "fonte": pl.Utf8, "regiao_comercial": pl.Utf8,
            "representante": pl.Utf8, "codvend": pl.Int64,
        },
    ).unique(subset=["cod_ibge", "fonte", "representante"], keep="first")

    execute("TRUNCATE analytics.dim_territorio_rca")
    n = insert_dataframe(df, "dim_territorio_rca", "analytics")
    cidades = df["cod_ibge"].n_unique()
    logger.info(
        f"dim_territorio_rca: {n} atribuicoes cobrindo {cidades} municipios de MG"
    )
    return n


def _sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


# =====================================================================
# 5. Potencial
# =====================================================================
def consumo_observado_por_segmento() -> pl.DataFrame:
    """
    Mediana de toneladas/mes de farinha por CLIENTE REAL do Moinho, por segmento.

    Este e o metodo recomendado pelo relatorio de pesquisa: em vez de perguntar
    a internet quanto uma padaria consome, mede-se quanto as padarias que ja
    compram do Moinho efetivamente compram. O numero resultante e conservador
    por construcao - e o consumo CAPTADO, nao o consumo TOTAL do cliente.
    """
    cfg = _config()
    escopo = cfg["classificacoes_no_escopo"]
    janela = int(cfg["modelo"]["janela_vendas_meses"])

    perfil_para_segmento: dict[str, str] = {}
    for chave, seg in cfg["segmentos"].items():
        for perfil in seg.get("perfis_moinho") or []:
            perfil_para_segmento[perfil.strip().upper()] = chave

    marcadores = ", ".join(f":cls{i}" for i in range(len(escopo)))
    params: dict[str, Any] = {f"cls{i}": c for i, c in enumerate(escopo)}
    params["janela"] = janela

    por_cliente = read_sql(
        f"""
        WITH limite AS (
            SELECT to_char(to_date(MAX(ano_mes), 'YYYY-MM')
                           - make_interval(months => :janela), 'YYYY-MM') AS inicio
            FROM analytics.v_venda_item
        )
        SELECT c.perfil_empresa,
               i.codparc,
               SUM(i.tonliq) AS ton
        FROM analytics.v_venda_item i
        JOIN analytics.dim_cliente c ON c.codparc = i.codparc
        CROSS JOIN limite l
        WHERE i.uf_cliente = 'MG'
          AND i.classificacao IN ({marcadores})
          AND i.ano_mes > l.inicio
          AND NOT i.is_devolucao
        GROUP BY c.perfil_empresa, i.codparc
        HAVING SUM(i.tonliq) > 0
        """,
        params,
    )

    if por_cliente.height == 0:
        return pl.DataFrame(
            schema={"segmento": pl.Utf8, "consumo_medio_t_mes": pl.Float64,
                    "clientes_amostra": pl.Int64}
        )

    return (
        por_cliente.with_columns(
            pl.col("perfil_empresa")
            .fill_null("")
            .str.to_uppercase()
            .str.strip_chars()
            .replace_strict(perfil_para_segmento, default=None)
            .alias("segmento"),
            (pl.col("ton").cast(pl.Float64) / janela).alias("ton_mes"),
        )
        .drop_nulls("segmento")
        .group_by("segmento")
        .agg(
            pl.col("ton_mes").median().alias("consumo_medio_t_mes"),
            pl.len().alias("clientes_amostra"),
        )
    )


def calcular_potencial() -> dict[str, Any]:
    """Preenche analytics.fact_potencial_municipio a partir do CEMPRE + consumo observado."""
    cfg = _config()
    modelo = cfg["modelo"]
    ajuste = modelo["ajuste_porte"]
    minimo = int(modelo["minimo_clientes_amostra"])
    fallback_base = float(modelo["consumo_fallback_por_intensidade_t_mes"])

    observado = consumo_observado_por_segmento()
    obs = {
        r["segmento"]: (r["consumo_medio_t_mes"], r["clientes_amostra"])
        for r in observado.iter_rows(named=True)
    }

    mercado = read_sql(
        """
        SELECT cod_ibge, segmento, unidades_locais, porte_medio
        FROM analytics.fact_mercado_cnae
        WHERE unidades_locais > 0
        """
    )
    porte_estadual = read_sql(
        """
        SELECT segmento,
               SUM(COALESCE(pessoal_estimado, pessoal_ocupado)) / NULLIF(SUM(unidades_locais), 0)
                   AS porte_estadual
        FROM analytics.fact_mercado_cnae
        GROUP BY segmento
        """
    )
    porte_ref = dict(
        zip(porte_estadual["segmento"], porte_estadual["porte_estadual"], strict=True)
    )

    linhas: list[dict[str, Any]] = []
    calibragem: dict[str, Any] = {}

    for chave, seg in cfg["segmentos"].items():
        intensidade = float(seg["intensidade"])
        prob = float(seg["prob_captura"])
        consumo_obs, amostra = obs.get(chave, (None, 0))

        if modelo["origem_consumo"] == "OBSERVADO" and amostra >= minimo and consumo_obs:
            consumo = float(consumo_obs)
            origem = "OBSERVADO"
        else:
            consumo = intensidade * fallback_base
            origem = "FALLBACK"
        calibragem[chave] = {
            "consumo_t_mes": round(consumo, 4),
            "origem": origem,
            "amostra": int(amostra or 0),
        }

        sub = mercado.filter(pl.col("segmento") == chave)
        if sub.height == 0:
            continue
        referencia = float(porte_ref.get(chave) or 0) or None

        for row in sub.iter_rows(named=True):
            unidades = int(row["unidades_locais"] or 0)
            if unidades <= 0:
                continue
            fator = 1.0
            if ajuste["ativo"] and referencia and row["porte_medio"]:
                fator = float(row["porte_medio"]) / referencia
                fator = max(float(ajuste["fator_minimo"]),
                            min(float(ajuste["fator_maximo"]), fator))
            potencial = unidades * consumo * fator
            linhas.append({
                "cod_ibge": int(row["cod_ibge"]),
                "segmento": chave,
                "unidades_locais": unidades,
                "consumo_medio_t_mes": round(consumo, 4),
                "origem_consumo": origem,
                "clientes_amostra": int(amostra or 0),
                "fator_porte": round(fator, 4),
                "prob_captura": prob,
                "potencial_t_mes": round(potencial, 4),
                "potencial_capturavel_t_mes": round(potencial * prob, 4),
            })

    df = pl.DataFrame(linhas)
    execute("TRUNCATE analytics.fact_potencial_municipio")
    n = insert_dataframe(df, "fact_potencial_municipio", "analytics")

    total = float(df["potencial_capturavel_t_mes"].sum() or 0)
    logger.info(
        f"fact_potencial_municipio: {n} linhas | potencial capturavel MG "
        f"{total:,.0f} t/mes".replace(",", ".")
    )
    for chave, info in calibragem.items():
        logger.info(
            f"  {chave:<20} {info['consumo_t_mes']:>8.3f} t/mes por estabelecimento "
            f"({info['origem']}, n={info['amostra']})"
        )
    return {"linhas": n, "potencial_capturavel_t_mes": round(total, 1),
            "calibragem": calibragem}


# =====================================================================
# Orquestracao
# =====================================================================
def construir_todas() -> dict[str, Any]:
    """Executa a camada geografica inteira, na ordem de dependencia."""
    resultado: dict[str, Any] = {}
    resultado["municipios"] = construir_dim_municipio_mg()
    resultado["pareamento"] = construir_map_cidade_ibge()
    resultado["mercado_cnae"] = construir_fact_mercado_cnae()
    resultado["territorio"] = construir_dim_territorio_rca()
    resultado["potencial"] = calcular_potencial()
    return resultado
