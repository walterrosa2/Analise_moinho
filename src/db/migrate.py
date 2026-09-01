"""
Runner de migrations SQL.

Aplica migrations/*.sql em ordem lexicografica, uma vez cada, registrando
version + checksum em app.schema_migrations.

Por que SQL versionado e nao autogeracao Alembic (ADR-002): este e um data
warehouse com quatro schemas, materialized views e comentarios de coluna que
documentam regra de negocio. SQL explicito e legivel e auditavel pelo consultor;
DDL autogerado por diff de ORM nao e.

Se o conteudo de uma migration ja aplicada mudar, o runner AVISA (checksum
divergente) em vez de reaplicar silenciosamente.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from sqlalchemy import text

from src.db.engine import get_engine
from src.logging_setup import log_audit, logger, setup_logging

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
VERSION_RE = re.compile(r"^(\d+)")


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]


def _bootstrap_control_table() -> None:
    """Cria schema app + tabela de controle antes da primeira migration."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS app"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app.schema_migrations (
                    version     TEXT PRIMARY KEY,
                    filename    TEXT        NOT NULL,
                    checksum    TEXT        NOT NULL,
                    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    duration_ms INTEGER
                )
                """
            )
        )


def applied_versions() -> dict[str, str]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT version, checksum FROM app.schema_migrations")
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def pending() -> list[Path]:
    done = applied_versions()
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    return [f for f in files if _version_of(f) not in done]


def _version_of(path: Path) -> str:
    m = VERSION_RE.match(path.name)
    return m.group(1) if m else path.stem


def run(verbose: bool = True) -> int:
    """Aplica as migrations pendentes. Devolve quantas foram aplicadas."""
    setup_logging()
    _bootstrap_control_table()

    done = applied_versions()
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.warning(f"Nenhuma migration encontrada em {MIGRATIONS_DIR}")
        return 0

    engine = get_engine()
    aplicadas = 0

    for path in files:
        version = _version_of(path)
        sql = path.read_text(encoding="utf-8")
        chk = _checksum(sql)

        if version in done:
            if done[version] != chk:
                logger.warning(
                    f"Migration {version} ({path.name}) mudou depois de aplicada "
                    f"(checksum {done[version]} -> {chk}). "
                    "Crie uma NOVA migration em vez de editar a antiga."
                )
            elif verbose:
                logger.debug(f"{version} ja aplicada")
            continue

        t0 = time.perf_counter()
        try:
            with engine.begin() as conn:
                # Cursor bruto: o SQL contem '%' em comentarios de coluna
                # (ex.: "% nao alocado"), que o psycopg trataria como placeholder.
                raw = conn.connection.dbapi_connection
                with raw.cursor() as cur:  # type: ignore[union-attr]
                    cur.execute(sql)
                dur = int((time.perf_counter() - t0) * 1000)
                conn.execute(
                    text(
                        """
                        INSERT INTO app.schema_migrations
                            (version, filename, checksum, duration_ms)
                        VALUES (:v, :f, :c, :d)
                        """
                    ),
                    {"v": version, "f": path.name, "c": chk, "d": dur},
                )
        except Exception as exc:
            logger.error(f"FALHA na migration {path.name}: {exc}")
            log_audit(
                "migration_failed",
                target=path.name,
                outcome="error",
                data={"erro": str(exc)[:500]},
            )
            raise

        logger.info(f"Migration {version} aplicada ({path.name}) em {dur} ms")
        log_audit("migration_applied", target=path.name, data={"version": version, "ms": dur})
        aplicadas += 1

    if verbose:
        if aplicadas:
            logger.info(f"{aplicadas} migration(s) aplicada(s)")
        else:
            logger.info("Banco ja esta atualizado")
    return aplicadas


def status() -> list[dict]:
    """Estado das migrations, para a pagina Admin/Diagnostico."""
    _bootstrap_control_table()
    done = applied_versions()
    out = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        v = _version_of(path)
        out.append(
            {
                "version": v,
                "arquivo": path.name,
                "aplicada": v in done,
                "checksum_ok": done.get(v) == _checksum(path.read_text(encoding="utf-8"))
                if v in done
                else None,
            }
        )
    return out


if __name__ == "__main__":
    run()
