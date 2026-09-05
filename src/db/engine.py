"""
Conexao com PostgreSQL (SQLAlchemy 2.x + psycopg 3).

Toda leitura analitica passa por aqui. Paginas Streamlit NUNCA importam
este modulo diretamente: elas falam com `src/repositories`.
"""
from __future__ import annotations

import functools
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import polars as pl
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from src.config import get_settings
from src.logging_setup import logger


@functools.lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Engine singleton com pool pre-ping (resiliente a container reiniciado)."""
    settings = get_settings()
    engine = create_engine(
        settings.db_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )
    logger.debug(f"Engine criado para {settings.db_url_safe}")
    return engine


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Conexao com commit automatico no sucesso e rollback no erro."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


def ping() -> bool:
    """Testa a conectividade. Usado pela pagina Admin/Diagnostico."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Banco indisponivel: {type(exc).__name__}: {exc}")
        return False


def read_sql(sql: str, params: dict[str, Any] | None = None) -> pl.DataFrame:
    """
    Executa SELECT e devolve polars.DataFrame.

    NUMERIC do PostgreSQL chega como decimal.Decimal e o polars o mapeia para
    o tipo Decimal, cuja aritmetica reescala em divisoes e agregacoes (um
    rateio virou 1e-6 do valor correto ate isto ser corrigido). Como todo o
    uso aqui e analitico, convertemos Decimal -> Float64 na fronteira, uma vez
    so, em vez de espalhar casts por cada consulta.
    """
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        rows = result.fetchall()
        cols = list(result.keys())
    if not rows:
        return pl.DataFrame({c: [] for c in cols})

    df = pl.DataFrame([dict(zip(cols, r, strict=False)) for r in rows], infer_schema_length=None)
    decimais = [c for c, dt in df.schema.items() if dt == pl.Decimal or str(dt).startswith("Decimal")]
    if decimais:
        df = df.with_columns([pl.col(c).cast(pl.Float64) for c in decimais])
    return df


def execute(sql: str, params: dict[str, Any] | None = None) -> None:
    """Executa DDL/DML."""
    with get_connection() as conn:
        conn.execute(text(sql), params or {})


def execute_script(sql: str) -> None:
    """Executa um script multi-statement (migrations)."""
    with get_connection() as conn:
        conn.exec_driver_sql(sql)


def insert_dataframe(
    df: pl.DataFrame,
    table: str,
    schema: str,
    columns: Sequence[str] | None = None,
    chunk_size: int = 10_000,
) -> int:
    """
    Insere um DataFrame polars via COPY binario do psycopg (rapido em lote).

    Devolve o numero de linhas inseridas.
    """
    if df.height == 0:
        return 0

    cols = list(columns) if columns else df.columns
    df = df.select(cols)

    engine = get_engine()
    col_list = ", ".join(f'"{c}"' for c in cols)
    copy_sql = f'COPY "{schema}"."{table}" ({col_list}) FROM STDIN'

    inserted = 0
    # engine.begin() garante o COMMIT ao sair do bloco; com engine.connect()
    # o COPY feito pelo cursor bruto era descartado no rollback implicito.
    with engine.begin() as sa_conn:
        raw = sa_conn.connection.dbapi_connection
        with raw.cursor() as cur, cur.copy(copy_sql) as copy:  # type: ignore[union-attr]
            for start in range(0, df.height, chunk_size):
                chunk = df.slice(start, chunk_size)
                for row in chunk.iter_rows():
                    copy.write_row(row)
                inserted += chunk.height

    logger.debug(f"{inserted} linhas inseridas em {schema}.{table}")
    return inserted


def table_exists(schema: str, table: str) -> bool:
    """
    Existe uma relacao com esse nome? Tabela, view, MATERIALIZED VIEW ou particao.

    Consulta pg_class, e nao information_schema.tables: o padrao SQL nao conhece
    materialized view, entao o information_schema nao lista nenhuma das 13 MVs do
    modelo analitico. Com a consulta anterior, `table_exists('analytics',
    'mv_sales_month')` respondia False com a MV carregada — e o auto_seed do
    deploy concluia que o banco estava vazio e reprocessava tudo a cada restart.

    relkind: r=tabela, p=particionada, v=view, m=materialized view, f=externa.
    """
    sql = """
        SELECT EXISTS (
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
              AND c.relname = :table
              AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
        ) AS existe
    """
    df = read_sql(sql, {"schema": schema, "table": table})
    return bool(df["existe"][0]) if df.height else False


def count_rows(schema: str, table: str) -> int:
    if not table_exists(schema, table):
        return 0
    df = read_sql(f'SELECT COUNT(*) AS n FROM "{schema}"."{table}"')
    return int(df["n"][0]) if df.height else 0
