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

    # Verifica se ha dados nas tabelas principais
    tem_vendas = table_exists("staging", "fat_vendas") and count_rows("staging", "fat_vendas") > 0
    tem_views = table_exists("analytics", "mv_sales_month")

    if not tem_vendas or not tem_views:
        logger.info("Banco vazio ou incompleto detectado. Executando pipeline inicial de carga...")
        from scripts import run_pipeline

        # Executa sem argumentos (forcar=False, etapa=None)
        sys.argv = ["run_pipeline.py"]
        codigo = run_pipeline.main()
        if codigo != 0 and codigo != 3:
            logger.error(f"Pipeline inicial falhou com codigo {codigo}")
            return False
        logger.info("Pipeline inicial concluido com sucesso. Banco semeado!")
    else:
        logger.info("Banco ja contem dados consolidados. Pulando pipeline inicial.")

    return True


if __name__ == "__main__":
    if not ensure_db_initialized():
        sys.exit(1)
