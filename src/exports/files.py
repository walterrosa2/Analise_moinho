"""
Exportacao de tabelas para CSV e XLSX.

CSV sai no padrao pt-BR (separador ';', decimal ',') para abrir direto no
Excel brasileiro sem passo de importacao.
"""
from __future__ import annotations

import io

import polars as pl


def para_csv(df: pl.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.write_csv(buffer, separator=";", float_precision=4)
    texto = buffer.getvalue().decode("utf-8")
    # Decimal pt-BR: seguro porque o separador de campo e ';'
    linhas = []
    for linha in texto.splitlines():
        partes = linha.split(";")
        linhas.append(";".join(_virgula_decimal(p) for p in partes))
    # BOM para o Excel reconhecer UTF-8
    return ("﻿" + "\n".join(linhas)).encode("utf-8")


def _virgula_decimal(valor: str) -> str:
    v = valor.strip()
    if not v:
        return valor
    corpo = v[1:] if v[0] == "-" else v
    if corpo.replace(".", "", 1).isdigit() and "." in corpo:
        return v.replace(".", ",")
    return valor


def _sem_timezone(df: pl.DataFrame) -> pl.DataFrame:
    """
    O Excel nao representa fuso horario. Colunas TIMESTAMPTZ (started_at,
    updated_at...) sao convertidas para horario local ingenuo antes de exportar.
    """
    colunas = [
        c for c, dt in df.schema.items()
        if isinstance(dt, pl.Datetime) and dt.time_zone is not None
    ]
    if not colunas:
        return df
    return df.with_columns([pl.col(c).dt.replace_time_zone(None) for c in colunas])


def para_xlsx(df: pl.DataFrame, aba: str = "Dados") -> bytes:
    buffer = io.BytesIO()
    _sem_timezone(df).write_excel(buffer, worksheet=aba[:31], autofit=True)
    return buffer.getvalue()


def para_xlsx_multi(planilhas: dict[str, pl.DataFrame]) -> bytes:
    """Varias abas num arquivo so (usado no pacote de evidencias)."""
    import xlsxwriter

    buffer = io.BytesIO()
    with xlsxwriter.Workbook(buffer, {"in_memory": True}) as wb:
        for nome, df in planilhas.items():
            _sem_timezone(df).write_excel(workbook=wb, worksheet=nome[:31], autofit=True)
    return buffer.getvalue()
