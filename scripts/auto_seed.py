"""
Verifica se o banco está inicializado e popula automaticamente se estiver vazio.
Usado pelo entrypoint de deploy (Railway / Docker).
"""
from __future__ import annotations

import sys
import time

from src.config import get_settings
from src.db import migrate
from src.db.engine import count_rows, ping, table_exists
from src.logging_setup import logger, setup_logging


def ensure_db_initialized() -> bool:
    setup_logging()
    settings = get_settings()
    logger.info(f"Conectando ao banco de dados: {settings.db_url_safe}")

    # Aguarda o banco ficar acessivel (ate 45s)
    tentativas = 0
    while not ping() and tentativas < 15:
        tentativas += 1
        logger.info(f"Aguardando PostgreSQL ficar pronto ({tentativas}/15)...")
        time.sleep(3)

    if not ping():
        logger.error("Nao foi possivel conectar ao PostgreSQL no tempo limite.")
        return False

    logger.info("Executando migrations pendentes...")
    migrate.run(verbose=True)

    # O grao de venda vive em analytics.fact_venda_item — nao existe schema
    # 'staging' neste modelo. Apontar para uma tabela inexistente fazia o seed
    # concluir "banco vazio" mesmo cheio e reprocessar 269 mil linhas em todo
    # restart do container, estourando o healthcheck do Railway.
    tem_vendas = count_rows("analytics", "fact_venda_item") > 0
    tem_views = table_exists("analytics", "mv_sales_month")

    if not tem_vendas or not tem_views:
        logger.info("Banco vazio ou incompleto detectado. Executando pipeline inicial de carga...")
        if not _rodar_pipeline():
            return False
        logger.info("Pipeline inicial concluido com sucesso. Banco semeado!")
        return True

    logger.info("Banco ja contem dados consolidados. Pulando pipeline inicial.")

    # A camada geografica de mercado chegou depois: um banco carregado antes
    # dela existe, esta valido e nao precisa de recarga completa — so das
    # etapas novas, que custam segundos em vez de minutos.
    if count_rows("analytics", "dim_municipio_mg") == 0:
        logger.info("Camada de mercado (MG) ausente. Executando apenas as etapas novas...")
        for etapa in ("mercado", "geografia", "views"):
            if not _rodar_pipeline(etapa):
                logger.warning(f"Etapa '{etapa}' nao completou. A aplicacao sobe sem o mapa.")
                break

    return True


def _rodar_pipeline(etapa: str | None = None) -> bool:
    """Executa o pipeline (inteiro ou uma etapa) e traduz o codigo de saida."""
    from scripts import run_pipeline

    sys.argv = ["run_pipeline.py"] + (["--etapa", etapa] if etapa else [])
    codigo = run_pipeline.main()
    # 3 = verificacoes de qualidade com falha: o dado carregou, a plataforma
    # mostra o problema na tela de Qualidade em vez de recusar a subir.
    if codigo not in (0, 3):
        logger.error(f"Pipeline falhou com codigo {codigo} (etapa={etapa or 'completo'})")
        return False
    return True


if __name__ == "__main__":
    if not ensure_db_initialized():
        sys.exit(1)
