"""
Carga da camada RAW, idempotente por hash de arquivo.

Fluxo (especificacao secao 33):
  1. descobrir arquivo -> 2. hash -> 3. ja carregado? skip -> 4. ler aba
  5. validar cabecalho -> 6. RAW -> 7. Parquet -> registrar batch

O DDL da tabela RAW e GERADO a partir do cabecalho real (todas as colunas
TEXT). Assim, mudanca de layout no Excel nao quebra a carga em silencio:
a divergencia aparece na validacao do contrato.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import polars as pl
from sqlalchemy import text

from src.config import get_settings, list_source_contracts
from src.db.engine import get_connection, get_engine, insert_dataframe
from src.ingestion.readers import (
    adicionar_metadados_raw,
    file_sha256,
    read_sheet_raw_text,
    validar_contrato,
)
from src.logging_setup import log_audit, logger

METADADOS_RAW = [
    ("_source_file", "TEXT"),
    ("_source_sheet", "TEXT"),
    ("_source_row", "BIGINT"),
    ("_ingestion_batch_id", "BIGINT"),
    ("_ingested_at", "TIMESTAMP"),
    ("_source_file_hash", "TEXT"),
]


class ContratoVioladoError(RuntimeError):
    """Coluna obrigatoria ausente: a carga para, ruidosamente."""


def _quote(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def criar_tabela_raw(tabela: str, colunas: list[str]) -> None:
    """CREATE TABLE raw.<tabela> com todas as colunas TEXT + metadados."""
    cols_sql = ",\n    ".join(f"{_quote(c)} TEXT" for c in colunas)
    meta_sql = ",\n    ".join(f"{_quote(n)} {t}" for n, t in METADADOS_RAW)
    ddl = f"""
        CREATE TABLE IF NOT EXISTS raw.{_quote(tabela)} (
            {cols_sql},
            {meta_sql}
        )
    """
    with get_connection() as conn:
        conn.execute(text(ddl))


def _colunas_existentes(tabela: str) -> list[str]:
    sql = """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = :t
        ORDER BY ordinal_position
    """
    with get_engine().connect() as conn:
        return [r[0] for r in conn.execute(text(sql), {"t": tabela}).fetchall()]


def _sincronizar_colunas(tabela: str, colunas: list[str]) -> list[str]:
    """
    Adiciona colunas novas que apareceram no arquivo.

    Coluna que sumiu NAO e removida (o historico permanece): ela e apenas
    reportada e preenchida com NULL na carga nova.
    """
    existentes = set(_colunas_existentes(tabela))
    novas = [c for c in colunas if c not in existentes]
    if novas:
        logger.warning(f"raw.{tabela}: colunas novas no arquivo: {novas}")
        with get_connection() as conn:
            for c in novas:
                conn.execute(
                    text(f"ALTER TABLE raw.{_quote(tabela)} ADD COLUMN IF NOT EXISTS {_quote(c)} TEXT")
                )
    sumidas = [c for c in existentes if c not in colunas and not c.startswith("_")]
    if sumidas:
        logger.warning(f"raw.{tabela}: colunas ausentes nesta carga (mantidas no schema): {sumidas}")
    return novas


def batch_ja_carregado(source_id: str, file_hash: str, sheet: str) -> int | None:
    """Devolve o batch_id de uma carga SUCCESS anterior com o mesmo hash."""
    sql = """
        SELECT batch_id FROM app.ingestion_batch
        WHERE source_id = :s AND source_file_hash = :h
          AND COALESCE(source_sheet, '') = COALESCE(:sh, '')
          AND status = 'SUCCESS'
        ORDER BY batch_id DESC LIMIT 1
    """
    with get_engine().connect() as conn:
        row = conn.execute(text(sql), {"s": source_id, "h": file_hash, "sh": sheet}).fetchone()
    return int(row[0]) if row else None


def _marcar_superseded(source_id: str, sheet: str) -> None:
    """
    Recarga forcada: as cargas SUCCESS anteriores desta fonte/aba passam a
    SUPERSEDED, liberando o indice unico e preservando o historico do batch.
    """
    sql = """
        UPDATE app.ingestion_batch
        SET status = 'SUPERSEDED',
            error_message = COALESCE(error_message, '') || ' [substituido por recarga forcada]'
        WHERE source_id = :s
          AND COALESCE(source_sheet, '') = COALESCE(:sh, '')
          AND status = 'SUCCESS'
    """
    with get_connection() as conn:
        conn.execute(text(sql), {"s": source_id, "sh": sheet})


def abrir_batch(
    source_id: str, arquivo: Path, sheet: str, file_hash: str
) -> int:
    sql = """
        INSERT INTO app.ingestion_batch
            (source_id, source_file, source_sheet, source_file_hash,
             file_size_bytes, file_modified_at, status)
        VALUES (:s, :f, :sh, :h, :sz, to_timestamp(:mt), 'RUNNING')
        RETURNING batch_id
    """
    stat = arquivo.stat()
    with get_connection() as conn:
        row = conn.execute(
            text(sql),
            {
                "s": source_id,
                "f": arquivo.name,
                "sh": sheet,
                "h": file_hash,
                "sz": stat.st_size,
                "mt": stat.st_mtime,
            },
        ).fetchone()
    return int(row[0])


def fechar_batch(
    batch_id: int,
    status: str,
    *,
    rows_read: int = 0,
    rows_loaded: int = 0,
    duration_ms: int = 0,
    erro: str | None = None,
) -> None:
    sql = """
        UPDATE app.ingestion_batch
        SET status = :st, rows_read = :rr, rows_loaded = :rl,
            duration_ms = :d, error_message = :e, finished_at = now()
        WHERE batch_id = :b
    """
    with get_connection() as conn:
        conn.execute(
            text(sql),
            {
                "st": status,
                "rr": rows_read,
                "rl": rows_loaded,
                "d": duration_ms,
                "e": (erro or "")[:2000] or None,
                "b": batch_id,
            },
        )


def carregar_fonte(contrato: dict[str, Any], forcar: bool = False) -> dict[str, Any]:
    """Carrega uma fonte para raw.* e grava o Parquet correspondente."""
    settings = get_settings()
    source_id = contrato["source_id"]
    sheet = contrato["sheet"]
    tabela = contrato["raw_table"]
    arquivo = settings.input_path / contrato["filename"]

    resultado: dict[str, Any] = {
        "source_id": source_id,
        "arquivo": contrato["filename"],
        "aba": sheet,
        "status": "PENDENTE",
        "linhas": 0,
    }

    if not arquivo.exists():
        resultado["status"] = "ARQUIVO_AUSENTE"
        logger.error(f"{source_id}: arquivo nao encontrado: {arquivo}")
        return resultado

    t0 = time.perf_counter()
    file_hash = file_sha256(arquivo)

    if not forcar:
        anterior = batch_ja_carregado(source_id, file_hash, sheet)
        if anterior is not None:
            resultado["status"] = "SKIPPED"
            resultado["batch_id"] = anterior
            logger.info(f"{source_id}: hash ja carregado (batch {anterior}) — skip")
            log_audit("ingestion_skipped", target=source_id, data={"batch_id": anterior})
            return resultado

    if forcar:
        _marcar_superseded(source_id, sheet)

    batch_id = abrir_batch(source_id, arquivo, sheet, file_hash)
    resultado["batch_id"] = batch_id

    try:
        df = read_sheet_raw_text(
            arquivo, sheet, colunas_proibidas=contrato.get("colunas_proibidas")
        )
        faltantes = validar_contrato(df, contrato)
        if faltantes:
            msg = (
                f"{source_id}: colunas obrigatorias ausentes: {faltantes}. "
                "Carga interrompida (a especificacao proibe carga silenciosa)."
            )
            logger.error(msg)
            fechar_batch(batch_id, "FAILED", erro=msg)
            log_audit("ingestion_failed", target=source_id, outcome="error", data={"faltantes": faltantes})
            raise ContratoVioladoError(msg)

        criar_tabela_raw(tabela, df.columns)
        _sincronizar_colunas(tabela, df.columns)

        # Recarga da mesma fonte/aba: limpa o conteudo anterior (idempotencia)
        with get_connection() as conn:
            conn.execute(
                text(f"DELETE FROM raw.{_quote(tabela)} WHERE _source_sheet = :sh"),
                {"sh": sheet},
            )

        df_meta = adicionar_metadados_raw(
            df,
            source_file=contrato["filename"],
            source_sheet=sheet,
            batch_id=batch_id,
            file_hash=file_hash,
        )
        carregadas = insert_dataframe(df_meta, tabela, "raw")

        # Parquet: o Excel nunca mais e relido para analise (especificacao 4.2)
        settings.parquet_path.mkdir(parents=True, exist_ok=True)
        parquet = settings.parquet_path / f"{source_id}.parquet"
        df_meta.write_parquet(parquet)

        dur = int((time.perf_counter() - t0) * 1000)
        fechar_batch(
            batch_id, "SUCCESS", rows_read=df.height, rows_loaded=carregadas, duration_ms=dur
        )
        resultado.update(status="SUCCESS", linhas=carregadas, duracao_ms=dur, parquet=str(parquet))
        logger.info(f"{source_id}: {carregadas:,} linhas -> raw.{tabela} ({dur} ms)".replace(",", "."))
        log_audit(
            "ingestion_success",
            target=source_id,
            data={"batch_id": batch_id, "linhas": carregadas, "ms": dur},
        )
        return resultado

    except ContratoVioladoError:
        resultado["status"] = "FAILED"
        raise
    except Exception as exc:  # noqa: BLE001
        dur = int((time.perf_counter() - t0) * 1000)
        fechar_batch(batch_id, "FAILED", duration_ms=dur, erro=str(exc))
        resultado.update(status="FAILED", erro=str(exc))
        logger.exception(f"{source_id}: falha na carga")
        log_audit("ingestion_failed", target=source_id, outcome="error", data={"erro": str(exc)[:500]})
        raise


def carregar_todas(forcar: bool = False) -> list[dict[str, Any]]:
    """Carrega todas as fontes declaradas em config/sources/, na ordem definida."""
    contratos = list_source_contracts()
    logger.info(f"{len(contratos)} contratos de fonte encontrados")
    resultados = []
    for contrato in contratos:
        try:
            resultados.append(carregar_fonte(contrato, forcar=forcar))
        except ContratoVioladoError:
            resultados.append(
                {"source_id": contrato["source_id"], "status": "FAILED", "linhas": 0}
            )
    return resultados


def ler_raw(tabela: str) -> pl.DataFrame:
    """Le uma tabela RAW inteira (tudo texto)."""
    from src.db.engine import read_sql

    return read_sql(f'SELECT * FROM raw."{tabela}"')


def ler_parquet(source_id: str) -> pl.DataFrame:
    """Le o Parquet da fonte (mais rapido que o banco para ETL em lote)."""
    path = get_settings().parquet_path / f"{source_id}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Parquet ausente: {path}. Rode a ingestao primeiro.")
    return pl.read_parquet(path)
