"""
Testes das regras de negócio inegociáveis.

Cada teste corresponde a uma regra de `docs/business_rules.md` ou a um
critério de aceite de `.specify/memory/specify.md`. Se um deles quebrar,
a plataforma passou a mentir sobre algo que já foi verificado.
"""
from __future__ import annotations

import pytest

from src.db.engine import read_sql, table_exists

pytestmark = pytest.mark.skipif(
    not table_exists("analytics", "fact_venda_item"),
    reason="Banco não carregado. Rode: py scripts/run_pipeline.py",
)


def _valor(sql: str, params: dict | None = None):
    df = read_sql(sql, params)
    return df.row(0)[0] if df.height else None


# =====================================================================
# RN-01 · Grão
# =====================================================================


def test_grao_item_e_unico():
    """AC-04: NUNOTA + SEQUENCIA identifica unicamente o item."""
    duplicadas = _valor(
        """
        SELECT COUNT(*) FROM (
            SELECT nunota, sequencia FROM analytics.fact_venda_item
            GROUP BY nunota, sequencia HAVING COUNT(*) > 1
        ) x
        """
    )
    assert duplicadas == 0


def test_volume_de_itens_bate_com_a_fonte():
    total = _valor("SELECT COUNT(*) FROM analytics.fact_venda_item")
    assert total == 204_037, f"Esperado 204.037 itens da fonte, encontrado {total}"


def test_documentos_distintos():
    total = _valor("SELECT COUNT(*) FROM analytics.fact_venda_documento")
    assert total == 87_274


# =====================================================================
# RN-02 · Medidas de documento fora do grão de item
# =====================================================================


def test_item_nao_contem_medidas_de_documento():
    """
    AC-05: somar VLRNOTA no grão de item infla a receita em 321,7%.
    A coluna simplesmente não pode existir em fact_venda_item.
    """
    presentes = _valor(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = 'fact_venda_item'
          AND column_name IN ('vlrnota', 'vlrfrete_ordemcarga')
        """
    )
    assert presentes == 0, "Medida de documento reintroduzida no grão de item (RN-02)"


def test_vlrnota_vive_no_documento():
    presentes = _valor(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = 'fact_venda_documento'
          AND column_name = 'vlrnota'
        """
    )
    assert presentes == 1


# =====================================================================
# RN-03 · Sinal da devolução
# =====================================================================


def test_devolucao_sempre_negativa():
    positivas = _valor(
        "SELECT COUNT(*) FROM analytics.fact_venda_item WHERE is_devolucao AND vlrtot > 0"
    )
    assert positivas == 0, "Devolução com valor positivo — o sinal da origem foi alterado"


def test_tipmov_dominio_fechado():
    fora = _valor(
        "SELECT COUNT(*) FROM analytics.fact_venda_item "
        "WHERE tipmov IS NULL OR tipmov NOT IN ('V', 'D')"
    )
    assert fora == 0


def test_receita_liquida_conhecida():
    """Total verificado na Fase 0: R$ 518.355.684,26."""
    receita = float(_valor("SELECT SUM(vlrtot) FROM analytics.fact_venda_item"))
    assert abs(receita - 518_355_684.26) < 1.0, f"Receita líquida mudou: {receita:,.2f}"


def test_volume_liquido_conhecido():
    ton = float(_valor("SELECT SUM(tonliq) FROM analytics.fact_venda_item"))
    assert abs(ton - 198_790.03) < 1.0, f"Volume líquido mudou: {ton:,.2f}"


# =====================================================================
# RN-07 · As-of join de custos
# =====================================================================


def test_asof_registra_status_em_todo_item():
    sem_status = _valor(
        "SELECT COUNT(*) FROM analytics.fact_venda_item WHERE cost_match_status IS NULL"
    )
    assert sem_status == 0, "Item sem status de correspondência de custo (AC-09)"


def test_asof_nunca_usa_custo_futuro():
    """O custo aplicado precisa ser vigente: DTATUAL <= data de referência."""
    futuros = _valor(
        """
        SELECT COUNT(*) FROM analytics.fact_venda_item
        WHERE cost_match_date IS NOT NULL AND cost_match_date > data_referencia
        """
    )
    assert futuros == 0, "As-of join usou custo posterior à venda"


def test_cobertura_de_custo_alta():
    sem_custo = _valor(
        "SELECT COUNT(*) FROM analytics.fact_venda_item "
        "WHERE cost_match_status IN ('SEM_CUSTO', 'SEM_DATA')"
    )
    total = _valor("SELECT COUNT(*) FROM analytics.fact_venda_item")
    assert sem_custo / total < 0.01, f"Cobertura de custo caiu: {sem_custo} sem custo"


def test_seis_bases_de_custo_disponiveis():
    """AC-08: os seis conceitos coexistem."""
    colunas = read_sql(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = 'fact_venda_item'
          AND column_name IN ('cusmed','cusmedicm','cussemicm','cusrep','cusger','cusvariavel')
        """
    )
    assert colunas.height == 6


def test_margem_proxy_economicamente_plausivel():
    """
    Guarda contra o erro de unidade que produzia 98,7% de margem (Q-15).
    Um moinho não opera com margem acima de 60% nem abaixo de zero no agregado.
    """
    margem = float(_valor(
        """
        SELECT 100 * (SUM(receita_com_custo) - SUM(custo_cusger))
                   / NULLIF(SUM(receita_com_custo), 0)
        FROM analytics.mv_sales_month
        """
    ))
    assert 0 < margem < 60, f"Margem proxy implausível: {margem:.2f}% — verifique a unidade do custo"


# =====================================================================
# RN-08 · Ponte CT-e ↔ NF-e
# =====================================================================


def test_rateio_soma_um_por_cte():
    """AC-06: os pesos de rateio de um CT-e vinculado somam 1."""
    fora = _valor(
        """
        SELECT COUNT(*) FROM (
            SELECT frete_id FROM analytics.bridge_cte_nfe
            WHERE match_status <> 'SEM_VINCULO'
            GROUP BY frete_id HAVING ABS(SUM(allocation_weight) - 1) > 0.0001
        ) x
        """
    )
    assert fora == 0


def test_metodo_de_rateio_sempre_registrado():
    sem_metodo = _valor(
        "SELECT COUNT(*) FROM analytics.bridge_cte_nfe WHERE allocation_method IS NULL"
    )
    assert sem_metodo == 0, "Rateio sem método declarado — a especificação proíbe rateio oculto"


def test_frete_alocado_nao_excede_o_total():
    total = float(_valor("SELECT SUM(vlrnota) FROM analytics.fact_cte"))
    alocado = float(_valor(
        "SELECT SUM(vlrfrete_alocado) FROM analytics.bridge_cte_nfe "
        "WHERE match_status <> 'SEM_VINCULO'"
    ))
    assert alocado <= total + 1.0, "Frete alocado maior que o total dos CT-e"


def test_chavecte_nao_serve_como_chave_primaria():
    """
    CHAVECTE é única quando existe, mas está AUSENTE em 1.134 CT-e (3,46%) —
    por isso a PK é o surrogate frete_id.

    (O profiling inicial contou 1.133 "duplicatas" porque a origem traz o
    literal 'NULL' como texto; o staging o converte para NULL de verdade.)
    """
    sem_chave = _valor("SELECT COUNT(*) FROM analytics.fact_cte WHERE chavecte IS NULL")
    assert sem_chave > 0, "Se todo CT-e passou a ter chave, reveja a decisão do surrogate key"

    repetidas = _valor(
        """
        SELECT COUNT(*) FROM (
            SELECT chavecte FROM analytics.fact_cte
            WHERE chavecte IS NOT NULL GROUP BY chavecte HAVING COUNT(*) > 1
        ) x
        """
    )
    assert repetidas == 0, "CHAVECTE passou a repetir — investigue a origem"


# =====================================================================
# RN-09 / RN-15 · Positivados
# =====================================================================


def test_explosao_de_positivados_confere():
    """AC-07: a soma explodida iguala QTD_POSITIVADOS em todos os meses."""
    divergentes = _valor(
        """
        SELECT COUNT(*) FROM analytics.fact_positivado_mes
        WHERE COALESCE(qtd_positivados_explodido, 0) <> COALESCE(qtd_positivados_fonte, 0)
        """
    )
    assert divergentes == 0


def test_positivado_e_entrada_nao_recorrencia():
    """RN-15: cada cliente aparece uma única vez."""
    repetidos = _valor(
        """
        SELECT COUNT(*) FROM (
            SELECT codparc FROM analytics.fact_positivado
            GROUP BY codparc HAVING COUNT(*) > 1
        ) x
        """
    )
    assert repetidos == 0


def test_periodo_de_implantacao_sinalizado():
    """AC-15: os meses atípicos são marcados, não excluídos."""
    marcados = _valor(
        "SELECT COUNT(*) FROM analytics.fact_positivado_mes WHERE periodo_implantacao_erp"
    )
    assert marcados == 3, "Os três meses de implantação do ERP devem estar sinalizados"

    fevereiro = _valor(
        "SELECT qtd_positivados_fonte FROM analytics.fact_positivado_mes "
        "WHERE ano = 2021 AND mes = 2"
    )
    assert fevereiro == 729, "Dado de implantação foi alterado — ele deve ser preservado"


# =====================================================================
# Dimensões e configuração
# =====================================================================


def test_papel_de_vendedor_nunca_inferido_por_nome():
    """RN-06: a origem do papel é sempre rastreável."""
    sem_origem = _valor(
        "SELECT COUNT(*) FROM analytics.dim_vendedor WHERE papel_origem IS NULL"
    )
    assert sem_origem == 0

    origens = read_sql("SELECT DISTINCT papel_origem FROM analytics.dim_vendedor")
    validas = {"CONFIG_EXPLICITA", "DEFAULT_TIPOVEND", "SEM_CADASTRO", "NAO_CLASSIFICADO"}
    assert set(origens["papel_origem"].to_list()) <= validas


def test_canais_de_venda_nao_contam_como_rca():
    """Q-01: 'V DIRETA FARELO' e afins não podem virar RCA fictício."""
    papel = _valor(
        "SELECT papel_analitico FROM analytics.dim_vendedor WHERE codvend = 457"
    )
    assert papel == "NAO_CLASSIFICADO"


def test_classificacao_de_produto_tem_origem():
    sem_origem = _valor(
        "SELECT COUNT(*) FROM analytics.dim_produto WHERE classificacao_origem IS NULL"
    )
    assert sem_origem == 0


def test_documento_do_cliente_nao_esta_em_claro():
    """RN-13 / LGPD: só o hash SHA-256 entra no DW."""
    colunas = read_sql(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = 'dim_cliente'
        """
    )["column_name"].to_list()
    assert "cgccpf_hash" in colunas
    assert not any(c in colunas for c in ("cgccpf", "cgccpf_par", "cnpj_cpf"))

    amostra = read_sql(
        "SELECT cgccpf_hash FROM analytics.dim_cliente "
        "WHERE cgccpf_hash IS NOT NULL LIMIT 5"
    )
    for h in amostra["cgccpf_hash"].to_list():
        assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


# =====================================================================
# Reconciliação
# =====================================================================


def test_reconciliacao_mensal_dentro_da_tolerancia():
    """AC-18: o modelo reproduz o gerencial no total mensal."""
    fora = _valor(
        """
        SELECT COUNT(*) FROM app.reconciliation_result
        WHERE scope = '161_MENSAL_TOTAL' AND status = 'DIVERGENTE'
        """
    )
    assert fora == 0, "A reconciliação mensal total saiu da tolerância de 0,5%"


def test_divergencia_media_muito_baixa():
    media = float(_valor(
        """
        SELECT AVG(ABS(diff_pct)) FROM app.reconciliation_result
        WHERE scope = '161_MENSAL_TOTAL'
        """
    ))
    assert media < 0.2, f"Divergência média subiu para {media:.3f}%"


def test_nenhuma_verificacao_critica_falhou():
    falhas = _valor("SELECT COUNT(*) FROM app.data_quality_check WHERE status = 'FAIL'")
    assert falhas == 0, "Há verificação crítica de qualidade falhando"
