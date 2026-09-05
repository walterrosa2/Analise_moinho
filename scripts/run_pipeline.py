"""
Orquestrador do pipeline completo.

    py scripts/run_pipeline.py              # carga incremental (pula hash ja carregado)
    py scripts/run_pipeline.py --forcar     # recarrega tudo
    py scripts/run_pipeline.py --etapa raw  # so uma etapa

Etapas: migrate -> raw -> dimensoes -> vendas -> custos -> frete -> gerenciais
        -> views -> qualidade -> reconciliacao
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.db import migrate
from src.db.engine import execute, ping
from src.ingestion.loader import carregar_todas
from src.ingestion.mercado_ibge import sincronizar as sincronizar_mercado
from src.logging_setup import log_audit, logger, setup_logging
from src.reconciliation.quality import executar_verificacoes
from src.reconciliation.reconcile import executar_reconciliacao
from src.staging.costs import construir_custos
from src.staging.dimensions import construir_todas as construir_dimensoes
from src.staging.freight import construir_frete
from src.staging.geografia import construir_todas as construir_geografia
from src.staging.managerial import construir_gerenciais
from src.staging.sales import construir_vendas

MATERIALIZED_VIEWS = [
    # A mediana de custo por produto alimenta a flag custo_outlier: vem primeiro
    "mv_custo_mediana_produto",
    "mv_sales_month",
    "mv_sales_product_month",
    "mv_sales_region_month",
    "mv_sales_seller_month",
    "mv_sales_customer_month",
    "mv_freight_route_month",
    "mv_freight_carrier_month",
    "mv_cost_product_month",
    "mv_positivados_cohort",
    "mv_trigo_cost_month",
    # Camada geografica de mercado (MG): a de vendas alimenta a de sobreposicao
    "mv_vendas_municipio_mg",
    "mv_mercado_municipio_mg",
]


def atualizar_views() -> int:
    """REFRESH das materialized views (especificacao secao 37)."""
    for mv in MATERIALIZED_VIEWS:
        t0 = time.perf_counter()
        execute(f"REFRESH MATERIALIZED VIEW analytics.{mv}")
        logger.info(f"  {mv} atualizada em {(time.perf_counter() - t0) * 1000:.0f} ms")
    return len(MATERIALIZED_VIEWS)


ETAPAS = {
    "migrate": ("Migrations", lambda a: {"aplicadas": migrate.run(verbose=False)}),
    "raw": ("Carga RAW", lambda a: _resumo_raw(carregar_todas(forcar=a.forcar))),
    "dimensoes": ("Dimensoes", lambda a: construir_dimensoes()),
    "vendas": ("Fatos de venda", lambda a: construir_vendas()),
    "custos": ("Custos + as-of join", lambda a: construir_custos()),
    "frete": ("CT-e + rateio de frete", lambda a: construir_frete()),
    "gerenciais": ("Fatos gerenciais", lambda a: construir_gerenciais()),
    "mercado": ("Mercado externo (IBGE)", lambda a: _etapa_mercado(a)),
    "geografia": ("Camada geografica MG", lambda a: _etapa_geografia()),
    "views": ("Materialized views", lambda a: {"views": atualizar_views()}),
    "qualidade": ("Testes de qualidade", lambda a: _resumo_qualidade(executar_verificacoes())),
    "reconciliacao": ("Reconciliacao", lambda a: executar_reconciliacao()),
}


def _resumo_raw(res: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "fontes": len(res),
        "sucesso": sum(1 for r in res if r["status"] == "SUCCESS"),
        "skipped": sum(1 for r in res if r["status"] == "SKIPPED"),
        "falhas": sum(1 for r in res if r["status"] == "FAILED"),
        "linhas": sum(r.get("linhas", 0) for r in res),
    }


def _etapa_mercado(args: Any) -> dict[str, Any]:
    """
    Fontes publicas do IBGE. E a unica etapa que depende da internet, entao ela
    nao pode derrubar o pipeline: sem rede e sem cache, o diagnostico comercial
    inteiro continua valido - so a camada de potencial fica indisponivel.
    """
    try:
        return sincronizar_mercado(forcar=args.forcar)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Mercado externo indisponivel: {exc}")
        return {"status": "INDISPONIVEL", "erro": str(exc)[:200]}


def _etapa_geografia() -> dict[str, Any]:
    """Camada geografica de MG. Pulada quando a base externa nao foi baixada."""
    try:
        return _resumo_geografia(construir_geografia())
    except FileNotFoundError as exc:
        logger.warning(f"Camada geografica pulada: {exc}")
        return {"status": "PULADA", "motivo": str(exc)[:200]}


def _resumo_geografia(res: dict[str, Any]) -> dict[str, Any]:
    pareamento = res.get("pareamento", {})
    return {
        "municipios": res.get("municipios"),
        "cidades_pareadas": sum(
            v["pareados"] for v in pareamento.values() if isinstance(v, dict)
        ),
        "cidades_sem_municipio": pareamento.get("nao_encontrados"),
        "linhas_mercado_cnae": res.get("mercado_cnae"),
        "atribuicoes_territorio": res.get("territorio"),
        "potencial_capturavel_t_mes": (res.get("potencial") or {}).get(
            "potencial_capturavel_t_mes"
        ),
    }


def _resumo_qualidade(res: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "verificacoes": len(res),
        "pass": sum(1 for r in res if r["status"] == "PASS"),
        "warn": sum(1 for r in res if r["status"] == "WARN"),
        "fail": sum(1 for r in res if r["status"] == "FAIL"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline da plataforma analitica do Moinho")
    parser.add_argument("--forcar", action="store_true", help="recarrega mesmo se o hash ja foi carregado")
    parser.add_argument("--etapa", choices=list(ETAPAS), help="executa apenas uma etapa")
    args = parser.parse_args()

    setup_logging()
    inicio = time.perf_counter()

    if not ping():
        logger.error(
            "PostgreSQL indisponivel. Suba o banco com: docker compose up -d postgres"
        )
        return 2

    etapas = [args.etapa] if args.etapa else list(ETAPAS)
    log_audit("pipeline_iniciado", data={"etapas": etapas, "forcar": args.forcar})

    resultados: dict[str, Any] = {}
    for nome in etapas:
        titulo, fn = ETAPAS[nome]
        logger.info(f"=== {titulo} ===")
        t0 = time.perf_counter()
        try:
            resultados[nome] = fn(args)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Etapa '{nome}' falhou")
            log_audit("pipeline_falhou", target=nome, outcome="error", data={"erro": str(exc)[:500]})
            return 1
        logger.info(f"    concluida em {time.perf_counter() - t0:.1f}s")

    total = time.perf_counter() - inicio
    print("\n" + "=" * 68)
    print("RESUMO DO PIPELINE")
    print("=" * 68)
    for etapa, res in resultados.items():
        print(f"\n{ETAPAS[etapa][0]}:")
        for k, v in (res or {}).items():
            valor = f"{v:,.2f}".replace(",", ".") if isinstance(v, float) else f"{v:,}".replace(",", ".") if isinstance(v, int) else v
            print(f"    {k:<32} {valor}")
    print("\n" + "=" * 68)
    print(f"Tempo total: {total:.1f}s")
    print("=" * 68)

    log_audit("pipeline_concluido", data={"segundos": round(total, 1)})

    qualidade = resultados.get("qualidade") or {}
    if qualidade.get("fail"):
        logger.error(f"{qualidade['fail']} verificacao(oes) CRITICA(s) falharam")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
