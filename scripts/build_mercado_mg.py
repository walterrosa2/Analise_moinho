"""
Constroi a base externa de mercado de Minas Gerais.

    py scripts/build_mercado_mg.py              # usa o cache se ja existir
    py scripts/build_mercado_mg.py --forcar     # rebaixa tudo do IBGE
    py scripts/build_mercado_mg.py --so-download  # nao toca no banco

Baixa do IBGE (localidades, Censo 2022, CEMPRE e malha municipal), grava os
parquets e reconstroi a camada geografica no banco: municipios, pareamento de
cidades, mercado por CNAE, territorio dos RCAs e potencial por municipio.

Separado de run_pipeline.py porque e a unica parte da plataforma que depende
de internet - e porque refazer so o mercado nao exige reprocessar 269 mil
linhas de nota fiscal.
"""
from __future__ import annotations

import argparse
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.db.engine import execute, ping
from src.ingestion.mercado_ibge import sincronizar
from src.logging_setup import log_audit, logger, setup_logging
from src.staging.geografia import construir_todas

VIEWS = ["mv_vendas_municipio_mg", "mv_mercado_municipio_mg"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Base de mercado de MG (IBGE)")
    parser.add_argument("--forcar", action="store_true",
                        help="rebaixa do IBGE mesmo com cache local")
    parser.add_argument("--so-download", action="store_true",
                        help="apenas baixa os parquets, sem escrever no banco")
    args = parser.parse_args()

    setup_logging()
    inicio = time.perf_counter()

    logger.info("=== Fontes publicas do IBGE ===")
    externo = sincronizar(forcar=args.forcar)
    logger.info(f"    {externo}")

    if args.so_download:
        print(f"\nDownload concluido em {time.perf_counter() - inicio:.1f}s")
        return 0

    if not ping():
        logger.error("PostgreSQL indisponivel. Suba o banco: docker compose up -d postgres")
        return 2

    logger.info("=== Camada geografica no banco ===")
    resultado = construir_todas()

    logger.info("=== Materialized views ===")
    for mv in VIEWS:
        t0 = time.perf_counter()
        execute(f"REFRESH MATERIALIZED VIEW analytics.{mv}")
        logger.info(f"    {mv} em {(time.perf_counter() - t0) * 1000:.0f} ms")

    pareamento = resultado.get("pareamento", {})
    potencial = resultado.get("potencial", {})

    print("\n" + "=" * 68)
    print("BASE DE MERCADO — MINAS GERAIS")
    print("=" * 68)
    print(f"    municipios                   {resultado['municipios']}")
    for origem, info in pareamento.items():
        if isinstance(info, dict):
            print(f"    cidades [{origem:<24}] {info['pareados']}/{info['nomes']} pareadas")
    print(f"    grafias sem municipio        {pareamento.get('nao_encontrados')}")
    print(f"    linhas mercado x segmento    {resultado['mercado_cnae']}")
    print(f"    atribuicoes de territorio    {resultado['territorio']}")
    print(f"    potencial capturavel         {potencial.get('potencial_capturavel_t_mes')} t/mes")
    print("=" * 68)
    print(f"Tempo total: {time.perf_counter() - inicio:.1f}s")

    log_audit(
        "mercado_mg_construido",
        data={"externo": externo.get("status"),
              "potencial_t_mes": potencial.get("potencial_capturavel_t_mes")},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
