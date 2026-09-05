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
GEOJSON_NOME = "mg_municipios.geojson"


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
def baixar_malha(forcar: bool = False) -> Path:
    """GeoJSON dos municipios de MG. Fica em data/geo/, fora do banco."""
    cfg = config()
    destino = geo_path() / GEOJSON_NOME
    if destino.exists() and not forcar:
        logger.info(f"Malha ja em cache: {destino.name}")
        return destino

    malha = cfg["fontes_ibge"]["malha"]
    url = (
        malha["url"].format(uf=cfg["codigo_uf_ibge"])
        + "?formato=application/vnd.geo+json"
        + "&intrarregiao=municipio"
        + f"&qualidade={malha['qualidade']}"
    )
    bruto = _get(url)
    destino.write_bytes(bruto)
    n = len(json.loads(bruto).get("features", []))
    logger.info(f"Malha municipal MG: {n} feicoes, {len(bruto) / 1024:.0f} KB")
    return destino


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
