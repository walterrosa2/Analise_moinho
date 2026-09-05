"""
Ingestao das fontes publicas do IBGE que sustentam a camada de POTENCIAL.

Tres fontes, todas oficiais e reprodutiveis:

  1. Localidades   -> os 853 municipios de MG com meso/micro/imediata/intermediaria
  2. Censo 2022    -> populacao residente por municipio (agregado 4714, variavel 93)
  3. CEMPRE 9528   -> unidades locais e pessoal ocupado por municipio e classe CNAE
  4. Malha         -> GeoJSON municipal para o mapa (nao vai para o banco)

Nenhuma URL vive no codigo: todas saem de `config/mercado_mg.yaml`.

O download e idempotente e cacheado em parquet. A aplicacao nunca chama a
internet em tempo de execucao — le o parquet. Sem rede, o pipeline segue
com o cache existente e registra o aviso.
"""
from __future__ import annotations

import gzip
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import polars as pl
from loguru import logger

from src.config import get_settings, load_yaml

TIMEOUT_S = 120
TENTATIVAS = 3
BACKOFF_S = 3

ARQ_MUNICIPIOS = "mercado_mg_municipios"
ARQ_CNAE = "mercado_mg_cnae"

# Duas resolucoes da mesma malha, porque um mini-mapa de 330 px e um mapa de
# 700 px nao precisam do mesmo numero de vertices. O Plotly serializa o GeoJSON
# INTEIRO dentro de cada figura, e o Streamlit renderiza todas as abas de uma
# vez: sem isso, uma unica carga da pagina empurra a malha sete vezes para o
# navegador. Ver `simplificar_malha`.
GEOJSON_NOME = "mg_municipios.geojson"
GEOJSON_LEVE = "mg_municipios_leve.geojson"


def config() -> dict[str, Any]:
    """Parametros de negocio da analise de mercado."""
    return load_yaml("mercado_mg.yaml")


def geo_path() -> Path:
    """Diretorio dos artefatos geograficos (fora do controle de versao)."""
    p = get_settings().root / "data" / "geo"
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------
def _get(url: str) -> bytes:
    """GET com gzip, timeout e retry com backoff. Levanta a ultima excecao."""
    ultimo: Exception | None = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "moinho-analytics/1.0 (+plataforma analitica interna)",
                    "Accept-Encoding": "gzip",
                },
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                bruto = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    bruto = gzip.decompress(bruto)
                return bruto
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            ultimo = exc
            logger.warning(f"IBGE tentativa {tentativa}/{TENTATIVAS} falhou: {exc}")
            if tentativa < TENTATIVAS:
                time.sleep(BACKOFF_S * tentativa)
    raise RuntimeError(f"IBGE indisponivel apos {TENTATIVAS} tentativas: {ultimo}")


def _get_json(url: str) -> Any:
    return json.loads(_get(url))


# ---------------------------------------------------------------------
# 1. Municipios
# ---------------------------------------------------------------------
def baixar_municipios() -> pl.DataFrame:
    """853 municipios de MG com a hierarquia regional oficial do IBGE."""
    cfg = config()
    url = cfg["fontes_ibge"]["municipios"].format(uf=cfg["codigo_uf_ibge"])
    dados = _get_json(url)

    linhas = []
    for m in dados:
        micro = m.get("microrregiao") or {}
        meso = (micro.get("mesorregiao") or {})
        imediata = m.get("regiao-imediata") or {}
        intermediaria = imediata.get("regiao-intermediaria") or {}
        linhas.append(
            {
                "cod_ibge": int(m["id"]),
                "municipio": m["nome"],
                "microrregiao": micro.get("nome"),
                "mesorregiao": meso.get("nome"),
                "regiao_imediata": imediata.get("nome"),
                "regiao_intermediaria": intermediaria.get("nome"),
            }
        )
    df = pl.DataFrame(linhas)
    logger.info(f"IBGE localidades: {df.height} municipios de MG")
    return df


# ---------------------------------------------------------------------
# 2. Populacao
# ---------------------------------------------------------------------
def baixar_populacao() -> pl.DataFrame:
    """Populacao residente por municipio (Censo 2022)."""
    cfg = config()["fontes_ibge"]["populacao"]
    uf = config()["codigo_uf_ibge"]
    url = (
        f"https://servicodados.ibge.gov.br/api/v3/agregados/{cfg['agregado']}"
        f"/periodos/{cfg['periodo']}/variaveis/{cfg['variavel']}"
        f"?localidades=N6[N3[{uf}]]"
    )
    dados = _get_json(url)
    series = dados[0]["resultados"][0]["series"]

    linhas = [
        {
            "cod_ibge": int(s["localidade"]["id"]),
            "populacao": _para_int(next(iter(s["serie"].values()))),
        }
        for s in series
    ]
    df = pl.DataFrame(linhas)
    total = df["populacao"].sum()
    logger.info(f"IBGE populacao: {df.height} municipios, {total:,} habitantes".replace(",", "."))
    return df


# ---------------------------------------------------------------------
# 3. CEMPRE — empresas por municipio e CNAE
# ---------------------------------------------------------------------
def baixar_empresas_cnae() -> pl.DataFrame:
    """
    Unidades locais e pessoal ocupado por municipio, para cada segmento
    declarado em `config/mercado_mg.yaml`.

    O CEMPRE marca com 'X' o dado protegido por sigilo estatistico e com '-'
    a ausencia de unidades. Ambos viram null aqui; a distincao entre "nao
    existe" e "existe mas e sigiloso" e resolvida no staging (um municipio
    com unidades > 0 e pessoal sigiloso recebe o porte mediano estadual).
    """
    cfg = config()
    emp = cfg["fontes_ibge"]["empresas"]
    uf = cfg["codigo_uf_ibge"]
    segmentos = cfg["segmentos"]

    quadros: list[pl.DataFrame] = []
    for chave, seg in segmentos.items():
        url = (
            f"https://servicodados.ibge.gov.br/api/v3/agregados/{emp['agregado']}"
            f"/periodos/{emp['periodo']}"
            f"/variaveis/{emp['variavel_unidades']}|{emp['variavel_pessoal']}"
            f"?localidades=N6[N3[{uf}]]"
            f"&classificacao={emp['classificacao']}[{seg['cnae_id']}]"
        )
        dados = _get_json(url)

        por_variavel: dict[int, dict[int, int | None]] = {}
        periodo_ref = None
        for var in dados:
            vid = int(var["id"])
            mapa: dict[int, int | None] = {}
            for s in var["resultados"][0]["series"]:
                cod = int(s["localidade"]["id"])
                periodo_ref, valor = next(iter(s["serie"].items()))
                mapa[cod] = _para_int(valor)
            por_variavel[vid] = mapa

        unidades = por_variavel.get(int(emp["variavel_unidades"]), {})
        pessoal = por_variavel.get(int(emp["variavel_pessoal"]), {})

        quadros.append(
            pl.DataFrame(
                {
                    "cod_ibge": list(unidades.keys()),
                    "segmento": [chave] * len(unidades),
                    "cnae": [seg["cnae"]] * len(unidades),
                    "unidades_locais": list(unidades.values()),
                    "pessoal_ocupado": [pessoal.get(c) for c in unidades],
                    "periodo_ref": [periodo_ref] * len(unidades),
                },
                schema_overrides={
                    "unidades_locais": pl.Int64,
                    "pessoal_ocupado": pl.Int64,
                },
            )
        )
        total = sum(v for v in unidades.values() if v)
        logger.info(f"CEMPRE {seg['cnae']} ({chave}): {total} unidades locais em MG")

    df = pl.concat(quadros)
    logger.info(f"CEMPRE: {df.height} linhas municipio x segmento")
    return df


# ---------------------------------------------------------------------
# 4. Malha municipal (GeoJSON)
# ---------------------------------------------------------------------
def _douglas_peucker(pontos: list[tuple[float, float]], tolerancia: float) -> list:
    """
    Descarta vertices que nao mudam a forma percebida da fronteira.

    Tolerancia em graus: 0,01 grau ~ 1,1 km. Num mapa que mostra Minas inteira
    em 700 px, 1 km vale menos de um pixel - o vertice nao existe para o leitor,
    mas custa bytes em toda carga da pagina.
    """
    if len(pontos) < 3:
        return list(pontos)

    def distancia(p, a, b) -> float:
        (x, y), (x1, y1), (x2, y2) = p, a, b
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        return ((x - (x1 + t * dx)) ** 2 + (y - (y1 + t * dy)) ** 2) ** 0.5

    pilha = [(0, len(pontos) - 1)]
    manter = {0, len(pontos) - 1}
    while pilha:
        inicio, fim = pilha.pop()
        maior, indice = 0.0, inicio
        for i in range(inicio + 1, fim):
            d = distancia(pontos[i], pontos[inicio], pontos[fim])
            if d > maior:
                maior, indice = d, i
        if maior > tolerancia:
            manter.add(indice)
            pilha.append((inicio, indice))
            pilha.append((indice, fim))
    return [pontos[i] for i in sorted(manter)]


def _area_com_sinal(anel: list) -> float:
    """Formula do cadarco. Positiva = anel anti-horario."""
    total = 0.0
    for i in range(len(anel) - 1):
        x1, y1 = anel[i]
        x2, y2 = anel[i + 1]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _orientar(anel: list, anti_horario: bool) -> list:
    """
    Forca a orientacao do anel (RFC 7946: exterior anti-horario, buraco horario).

    O motor de mapas do Plotly e o d3-geo, que interpreta orientacao na ESFERA e
    adota a convencao INVERSA a do RFC 7946: para o d3, o anel externo e o
    HORARIO. Um exterior anti-horario deixa de significar "este municipio" e
    passa a significar "todo o resto do planeta menos este municipio" - na tela,
    um retangulo solido cobrindo o painel, com o municipio recortado dentro.

    A malha do IBGE segue o RFC 7946 (exterior anti-horario), que e o correto
    como GeoJSON e o errado para o d3. Por isso a inversao aqui.
    """
    if (_area_com_sinal(anel) > 0) != anti_horario:
        return anel[::-1]
    return anel


def simplificar_malha(malha: dict, tolerancia: float, casas: int) -> dict:
    """
    Reduz a malha preservando o que o mapa precisa: o codigo do municipio e um
    poligono fechado, com a orientacao que o d3-geo espera. Um anel que ficaria
    degenerado (menos de 4 pontos) mantem a forma original - simplificar nunca
    pode fazer um municipio sumir.
    """
    def anel(coordenadas: list) -> list:
        pontos = [(float(c[0]), float(c[1])) for c in coordenadas]
        simples = _douglas_peucker(pontos, tolerancia) if tolerancia else pontos
        arredondado = [[round(x, casas), round(y, casas)] for x, y in simples]
        sem_repetidos: list = [arredondado[0]]
        for p in arredondado[1:]:
            if p != sem_repetidos[-1]:
                sem_repetidos.append(p)
        if len(sem_repetidos) < 4:
            sem_repetidos = [[round(x, casas), round(y, casas)] for x, y in pontos]
        if sem_repetidos[0] != sem_repetidos[-1]:
            sem_repetidos.append(sem_repetidos[0])
        return sem_repetidos

    def poligono(aneis: list) -> list:
        # Primeiro anel e o contorno externo (horario, para o d3); o resto, buraco.
        return [
            _orientar(anel(r), anti_horario=(i != 0)) for i, r in enumerate(aneis)
        ]

    feicoes = []
    for f in malha.get("features", []):
        geometria = f["geometry"]
        if geometria["type"] == "Polygon":
            coords = poligono(geometria["coordinates"])
        else:
            coords = [poligono(p) for p in geometria["coordinates"]]
        feicoes.append({
            "type": "Feature",
            # So o codigo do municipio sobrevive: e a unica propriedade que o
            # mapa usa para casar com o dado (featureidkey).
            "properties": {"codarea": str(f["properties"]["codarea"])},
            "geometry": {"type": geometria["type"], "coordinates": coords},
        })
    return {"type": "FeatureCollection", "features": feicoes}


def baixar_malha(forcar: bool = False) -> dict[str, Path]:
    """
    GeoJSON dos municipios de MG em duas resolucoes. Fica em data/geo/, nunca
    no banco. Devolve {'detalhe': Path, 'leve': Path}.
    """
    cfg = config()
    malha_cfg = cfg["fontes_ibge"]["malha"]
    destinos = {"detalhe": geo_path() / GEOJSON_NOME, "leve": geo_path() / GEOJSON_LEVE}

    if all(p.exists() for p in destinos.values()) and not forcar:
        logger.info("Malha ja em cache (detalhe + leve)")
        return destinos

    url = (
        malha_cfg["url"].format(uf=cfg["codigo_uf_ibge"])
        + "?formato=application/vnd.geo+json"
        + "&intrarregiao=municipio"
        + f"&qualidade={malha_cfg['qualidade']}"
    )
    bruta = json.loads(_get(url))
    n = len(bruta.get("features", []))

    for chave, destino in destinos.items():
        params = malha_cfg["simplificacao"][chave]
        simples = simplificar_malha(bruta, float(params["tolerancia"]), int(params["casas"]))
        texto = json.dumps(simples, separators=(",", ":"))
        destino.write_text(texto, encoding="utf-8")
        logger.info(
            f"Malha '{chave}': {len(simples['features'])} feicoes, "
            f"{len(texto) / 1024:.0f} KB"
        )

    if len(bruta.get("features", [])) != n:
        logger.warning("Contagem de feicoes mudou apos simplificacao")
    return destinos


# ---------------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------------
def sincronizar(forcar: bool = False) -> dict[str, Any]:
    """
    Baixa (ou reaproveita) as fontes externas e grava os parquets.

    Sem rede: mantem o cache e devolve `status='CACHE'`. O pipeline nao quebra
    por causa de uma indisponibilidade do IBGE.
    """
    destino = get_settings().parquet_path
    destino.mkdir(parents=True, exist_ok=True)
    arq_mun = destino / f"{ARQ_MUNICIPIOS}.parquet"
    arq_cnae = destino / f"{ARQ_CNAE}.parquet"

    if arq_mun.exists() and arq_cnae.exists() and not forcar:
        logger.info("Mercado externo: parquets ja existem (use forcar=True para rebaixar)")
        return {
            "status": "CACHE",
            "municipios": pl.read_parquet(arq_mun).height,
            "linhas_cnae": pl.read_parquet(arq_cnae).height,
        }

    try:
        municipios = baixar_municipios().join(baixar_populacao(), on="cod_ibge", how="left")
        cnae = baixar_empresas_cnae()
        baixar_malha(forcar=forcar)
    except Exception as exc:  # noqa: BLE001 — indisponibilidade externa nao derruba o pipeline
        if arq_mun.exists() and arq_cnae.exists():
            logger.warning(f"IBGE indisponivel ({exc}). Mantendo cache anterior.")
            return {"status": "CACHE_APOS_FALHA", "erro": str(exc)}
        raise

    municipios.write_parquet(arq_mun)
    cnae.write_parquet(arq_cnae)
    logger.info(f"Mercado externo gravado: {arq_mun.name}, {arq_cnae.name}")
    return {
        "status": "BAIXADO",
        "municipios": municipios.height,
        "linhas_cnae": cnae.height,
        "periodo_cempre": cnae["periodo_ref"].drop_nulls().max(),
    }


def _para_int(valor: Any) -> int | None:
    """'-' (sem unidades) e 'X' (sigilo) viram null; numeros viram int."""
    texto = str(valor).strip()
    if texto in {"-", "X", "..", "...", ""}:
        return None
    try:
        return int(float(texto))
    except ValueError:
        return None
