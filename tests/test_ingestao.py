"""
Testes da camada de ingestão: contratos, fidelidade da RAW, idempotência
e as funções de normalização (que não precisam de banco).
"""
from __future__ import annotations

import polars as pl
import pytest

from src.config import list_source_contracts
from src.db.engine import read_sql, table_exists
from src.ingestion.readers import (
    hash_documento,
    limpar_texto,
    normalizar_cif_fob,
    para_data,
    para_decimal,
    separar_codigo_descricao,
    validar_contrato,
)

# =====================================================================
# Normalizadores — puros, sem banco
# =====================================================================


def test_decimal_pt_br():
    """A origem mistura '108,58' (pt-BR) e '5600' (sem separador)."""
    df = pl.DataFrame({"v": ["108,58", "1.234,56", "5600", "0,00", "1,9389", None, "NULL"]})
    r = df.select(para_decimal("v").alias("v"))["v"].to_list()
    assert r[0] == pytest.approx(108.58)
    assert r[1] == pytest.approx(1234.56)
    assert r[2] == pytest.approx(5600.0)
    assert r[3] == pytest.approx(0.0)
    assert r[4] == pytest.approx(1.9389)
    assert r[5] is None
    assert r[6] is None


def test_decimal_en_us_tambem_funciona():
    df = pl.DataFrame({"v": ["66.7650183732718", "25298.02"]})
    r = df.select(para_decimal("v").alias("v"))["v"].to_list()
    assert r[0] == pytest.approx(66.765018, rel=1e-6)
    assert r[1] == pytest.approx(25298.02)


def test_null_textual_vira_null_e_nao_zero():
    """Regra de segurança #5: NULL nunca é preenchido com zero."""
    df = pl.DataFrame({"v": ["NULL", "  ", "UBERLANDIA   ", None]})
    r = df.select(limpar_texto("v").alias("v"))["v"].to_list()
    assert r == [None, None, "UBERLANDIA", None]


def test_cif_fob_normalizado_pela_primeira_letra():
    df = pl.DataFrame({"v": [
        "C - CIF - Contratação do Frete por conta do Remetente",
        "F - FOB - Contratação do Frete por conta do Destinatário",
        "S - Sem Frete", "C", "F", "S", "T", "R - Transp. Próprio Remetente", None,
    ]})
    r = df.select(normalizar_cif_fob("v").alias("v"))["v"].to_list()
    assert r == ["C", "F", "S", "C", "F", "S", "T", "R", None]


def test_datas_em_varios_formatos():
    df = pl.DataFrame({"v": [
        "2023-01-02 07:52:27.000", "2023-01-02 00:00:00", "2023-01-02",
        "02/01/2023", "NULL", None,
    ]})
    r = df.select(para_data("v").alias("v"))["v"].to_list()
    assert all(str(d) == "2023-01-02" for d in r[:4])
    assert r[4] is None and r[5] is None


def test_separacao_codigo_descricao():
    df = pl.DataFrame({"v": ["5357-UBERLANDIA", "4 - Varejo", "SEM CODIGO", None]})
    desc = df.select(separar_codigo_descricao("v", "descricao").alias("v"))["v"].to_list()
    cod = df.select(separar_codigo_descricao("v", "codigo").alias("v"))["v"].to_list()
    assert desc == ["UBERLANDIA", "Varejo", "SEM CODIGO", None]
    assert cod == ["5357", "4", None, None]


def test_documento_e_hasheado_de_forma_estavel():
    """O mesmo CNPJ, com ou sem máscara, produz o mesmo hash."""
    df = pl.DataFrame({"v": ["19.226.696/0001-05", "19226696000105", "", None]})
    r = df.select(hash_documento("v").alias("v"))["v"].to_list()
    assert r[0] == r[1] and len(r[0]) == 64
    assert r[2] is None and r[3] is None
    assert "19226696000105" not in r[0]


def test_contrato_detecta_coluna_faltante():
    """Regra §34: coluna obrigatória ausente não carrega em silêncio."""
    df = pl.DataFrame({"NUNOTA": [1], "SEQUENCIA": [1]})
    faltantes = validar_contrato(df, {"required_columns": ["NUNOTA", "SEQUENCIA", "VLRTOT"]})
    assert faltantes == ["VLRTOT"]


# =====================================================================
# Contratos declarados
# =====================================================================


def test_contratos_declaram_as_fontes_esperadas():
    ids = {c["source_id"] for c in list_source_contracts()}
    esperados = {
        "vendas_dev", "vendedores", "custos_pa", "cte", "positivados_mensal",
        "trigo_compra", "trigo_estoque", "gestao_diaria_161", "gestao_diaria_outros",
    }
    assert esperados <= ids, f"Contratos faltando: {esperados - ids}"


def test_credenciais_estao_bloqueadas_no_contrato():
    """
    ADR-005: o inventário de fontes traz senhas em texto claro.
    Essa coluna não pode ser lida nem para a camada RAW.
    """
    contratos = {c["source_id"]: c for c in list_source_contracts()}
    externas = contratos.get("catalogo_fontes_externas")
    assert externas is not None
    bloqueadas = externas.get("colunas_proibidas") or []
    assert "Login e Senha" in bloqueadas
    assert "Login e Senha" not in (externas.get("all_columns") or [])


# =====================================================================
# Camada RAW e idempotência (exigem banco carregado)
# =====================================================================

precisa_banco = pytest.mark.skipif(
    not table_exists("raw", "vendas_dev"),
    reason="Banco não carregado. Rode: py scripts/run_pipeline.py",
)


@precisa_banco
def test_raw_preserva_todas_as_linhas():
    assert read_sql("SELECT COUNT(*) AS n FROM raw.vendas_dev")["n"][0] == 204_037
    assert read_sql("SELECT COUNT(*) AS n FROM raw.cte")["n"][0] == 32_789
    assert read_sql("SELECT COUNT(*) AS n FROM raw.custos_pa")["n"][0] == 29_135


@precisa_banco
def test_raw_guarda_tudo_como_texto():
    """Fidelidade: a RAW não converte valor nenhum."""
    tipos = read_sql(
        """
        SELECT DISTINCT data_type FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'vendas_dev'
          AND column_name NOT LIKE '\\_%'
        """
    )["data_type"].to_list()
    assert tipos == ["text"], f"RAW deixou de ser texto puro: {tipos}"


@precisa_banco
def test_raw_tem_os_seis_metadados_de_linhagem():
    colunas = read_sql(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = 'vendas_dev'
          AND column_name LIKE '\\_%'
        """
    )["column_name"].to_list()
    exigidos = {
        "_source_file", "_source_sheet", "_source_row",
        "_ingestion_batch_id", "_ingested_at", "_source_file_hash",
    }
    assert exigidos <= set(colunas)


@precisa_banco
def test_raw_preserva_o_literal_null_da_origem():
    """
    A RAW é fiel: 'NULL' textual continua lá. A conversão acontece no staging.
    """
    n = read_sql("SELECT COUNT(*) AS n FROM raw.cte WHERE \"CHAVECTE\" = 'NULL'")["n"][0]
    assert n == 1134


@precisa_banco
def test_carga_e_idempotente_por_hash():
    """AC-03: o mesmo arquivo carregado duas vezes não duplica dados."""
    lotes = read_sql(
        """
        SELECT source_id, source_file_hash, COUNT(*) AS n
        FROM app.ingestion_batch
        WHERE status = 'SUCCESS'
        GROUP BY source_id, source_file_hash
        HAVING COUNT(*) > 1
        """
    )
    assert lotes.height == 0, "Dois lotes SUCCESS com o mesmo hash — idempotência quebrada"


@precisa_banco
def test_todas_as_fontes_carregaram():
    """AC-01: as fontes declaradas foram carregadas pelo pipeline."""
    carregadas = set(
        read_sql(
            "SELECT DISTINCT source_id FROM app.ingestion_batch WHERE status = 'SUCCESS'"
        )["source_id"].to_list()
    )
    declaradas = {c["source_id"] for c in list_source_contracts()}
    assert declaradas <= carregadas, f"Não carregadas: {declaradas - carregadas}"


@precisa_banco
def test_nenhuma_credencial_no_banco():
    """Varre o catálogo em busca de vazamento de senha."""
    suspeitas = read_sql(
        """
        SELECT COUNT(*) AS n FROM app.data_source_catalog
        WHERE descricao ILIKE '%senha%' OR relatorio ILIKE '%senha%'
           OR descricao ILIKE '%password%' OR observacoes ILIKE '%senha:%'
        """
    )["n"][0]
    assert suspeitas == 0, "Possível credencial importada para o catálogo"

    colunas = read_sql(
        """
        SELECT COUNT(*) AS n FROM information_schema.columns
        WHERE table_schema IN ('raw', 'analytics', 'app')
          AND (column_name ILIKE '%senha%' OR column_name ILIKE '%password%'
               OR column_name ILIKE '%login e senha%')
        """
    )["n"][0]
    assert colunas == 0, "Coluna de credencial criada no banco"
