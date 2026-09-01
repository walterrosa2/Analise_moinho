"""
Leitura de Excel e normalizacao de tipos sujos.

Principios:
  - A camada RAW recebe TEXTO, exatamente como veio (fidelidade).
  - A limpeza acontece no staging, com regras explicitas e testaveis.
  - Colunas marcadas como proibidas no contrato NUNCA sao lidas.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import fastexcel
import polars as pl

from src.logging_setup import logger

# Textos que representam ausencia de valor nas fontes do Moinho.
# 'NULL' aparece como literal em CIDORIGEM, UFORIGEM, CODTRIB, SERIENOTA,
# NOTAS_VENDA, PERC_ATING_VLR, MARKUP e outras.
TOKENS_NULOS = {"NULL", "null", "Null", "", "-", "#N/D", "#N/A", "NaN", "nan", "None"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_sheets(path: Path) -> list[str]:
    return list(fastexcel.read_excel(str(path)).sheet_names)


def read_sheet(path: Path, sheet: str, header_row: int | None = None) -> pl.DataFrame:
    """
    Le uma aba inteira.

    header_row=None usa a primeira linha como cabecalho (padrao).
    header_row=N (0-based) e usado nas planilhas com titulo antes do cabecalho.
    """
    reader = fastexcel.read_excel(str(path))
    if header_row is None:
        sheet_obj = reader.load_sheet_by_name(sheet)
    else:
        sheet_obj = reader.load_sheet_by_name(sheet, header_row=header_row)
    return sheet_obj.to_polars()


def read_sheet_raw_text(
    path: Path,
    sheet: str,
    colunas_proibidas: list[str] | None = None,
) -> pl.DataFrame:
    """
    Le a aba e converte TUDO para texto, preservando a representacao original.

    Datas viram ISO; numeros viram string sem notacao cientifica. Colunas
    proibidas (credenciais) sao descartadas antes de qualquer processamento.
    """
    df = read_sheet(path, sheet)
    proibidas = set(colunas_proibidas or [])
    if proibidas:
        presentes = [c for c in df.columns if c in proibidas]
        if presentes:
            logger.warning(
                f"Colunas bloqueadas por seguranca (nao lidas): {presentes} "
                f"em {path.name}::{sheet}"
            )
            df = df.drop(presentes)

    exprs = []
    for col in df.columns:
        s = df.get_column(col)
        if s.dtype in (pl.Date, pl.Datetime):
            exprs.append(pl.col(col).cast(pl.Utf8).alias(col))
        elif s.dtype.is_float():
            # 20007.0 -> "20007" quando for inteiro exato; evita ".0" espurio
            exprs.append(
                pl.when(pl.col(col).is_null())
                .then(None)
                .when(pl.col(col) == pl.col(col).round(0))
                .then(pl.col(col).cast(pl.Int64, strict=False).cast(pl.Utf8))
                .otherwise(pl.col(col).cast(pl.Utf8))
                .alias(col)
            )
        else:
            exprs.append(pl.col(col).cast(pl.Utf8).alias(col))

    return df.select(exprs)


# ---------------------------------------------------------------------
# Normalizadores (usados no staging)
# ---------------------------------------------------------------------


def limpar_texto(col: str) -> pl.Expr:
    """TRIM + tokens nulos viram NULL de verdade (nunca zero)."""
    return (
        pl.col(col)
        .cast(pl.Utf8)
        .str.strip_chars()
        .map_elements(
            lambda v: None if v is None or v in TOKENS_NULOS else v,
            return_dtype=pl.Utf8,
        )
    )


def para_decimal(col: str) -> pl.Expr:
    """
    Converte texto numerico pt-BR ou en-US para Float64.

    Trata: '1.234,56' (pt-BR), '1234.56' (en-US), '108,58', '5600', '0,00'.
    Estrategia: se houver virgula, ela e o separador decimal e o ponto e
    separador de milhar; senao, o ponto ja e o decimal.
    """
    base = pl.col(col).cast(pl.Utf8).str.strip_chars()
    limpo = (
        pl.when(base.is_null() | base.is_in(list(TOKENS_NULOS)))
        .then(None)
        .when(base.str.contains(","))
        .then(base.str.replace_all(r"\.", "").str.replace(",", ".", literal=True))
        .otherwise(base)
    )
    return limpo.str.replace_all(r"[^0-9eE\.\-\+]", "").cast(pl.Float64, strict=False)


def para_inteiro(col: str) -> pl.Expr:
    return para_decimal(col).round(0).cast(pl.Int64, strict=False)


def para_data(col: str) -> pl.Expr:
    """
    Converte texto para Date, aceitando os formatos vistos nas fontes:
    '2023-01-02 07:52:27.000', '2023-01-02 00:00:00', '2023-01-02',
    '02/01/2023'.
    """
    base = pl.col(col).cast(pl.Utf8).str.strip_chars()
    base = pl.when(base.is_null() | base.is_in(list(TOKENS_NULOS))).then(None).otherwise(base)
    iso = base.str.slice(0, 10)
    return (
        pl.coalesce(
            iso.str.to_date("%Y-%m-%d", strict=False),
            iso.str.to_date("%d/%m/%Y", strict=False),
        )
    )


def normalizar_cif_fob(col: str) -> pl.Expr:
    """
    'C - CIF - Contratacao...' -> 'C'; 'S - Sem Frete' -> 'S'.
    A primeira letra e o codigo; o resto e descricao (RN-05).
    """
    return (
        pl.when(limpar_texto(col).is_null())
        .then(None)
        .otherwise(limpar_texto(col).str.slice(0, 1).str.to_uppercase())
    )


def separar_codigo_descricao(col: str, parte: str = "descricao") -> pl.Expr:
    """
    '5357-UBERLANDIA' -> codigo '5357' / descricao 'UBERLANDIA'
    '4 - Varejo'      -> codigo '4'    / descricao 'Varejo'
    Sem separador, o valor inteiro e a descricao.
    """
    base = limpar_texto(col)
    tem_sep = base.str.contains(r"^\s*\d+\s*-")
    if parte == "codigo":
        return pl.when(tem_sep).then(base.str.extract(r"^\s*(\d+)\s*-", 1)).otherwise(None)
    return (
        pl.when(tem_sep)
        .then(base.str.replace(r"^\s*\d+\s*-\s*", "").str.strip_chars())
        .otherwise(base)
    )


def hash_documento(col: str) -> pl.Expr:
    """
    SHA-256 do CNPJ/CPF, apenas digitos. O documento em claro nunca entra
    no DW analitico (RN-13 / LGPD).
    """
    somente_digitos = limpar_texto(col).str.replace_all(r"\D", "")
    return (
        pl.when(somente_digitos.is_null() | (somente_digitos.str.len_chars() == 0))
        .then(None)
        .otherwise(
            somente_digitos.map_elements(
                lambda v: hashlib.sha256(v.encode()).hexdigest() if v else None,
                return_dtype=pl.Utf8,
            )
        )
    )


def adicionar_metadados_raw(
    df: pl.DataFrame,
    *,
    source_file: str,
    source_sheet: str,
    batch_id: int,
    file_hash: str,
) -> pl.DataFrame:
    """Anexa os 6 metadados de linhagem exigidos na camada RAW."""
    return df.with_columns(
        pl.lit(source_file).alias("_source_file"),
        pl.lit(source_sheet).alias("_source_sheet"),
        (pl.int_range(0, df.height, dtype=pl.Int64) + 1).alias("_source_row"),
        pl.lit(batch_id, dtype=pl.Int64).alias("_ingestion_batch_id"),
        pl.lit(datetime.now()).alias("_ingested_at"),
        pl.lit(file_hash).alias("_source_file_hash"),
    )


def validar_contrato(df: pl.DataFrame, contrato: dict[str, Any]) -> list[str]:
    """
    Confere as colunas obrigatorias. Devolve a lista de faltantes.

    Regra da especificacao (secao 34): coluna obrigatoria ausente NAO carrega
    em silencio — gera erro visivel e registro em log.
    """
    obrigatorias = contrato.get("required_columns") or []
    presentes = set(df.columns)
    return [c for c in obrigatorias if c not in presentes]
