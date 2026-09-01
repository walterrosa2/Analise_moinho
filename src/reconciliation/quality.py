"""
Testes automaticos de qualidade de dados.

Cada teste grava uma linha em app.data_quality_check com:
  status (PASS/WARN/FAIL), valor observado, esperado, e o SQL que reproduz
  as linhas problematicas ("Ver evidencia" na interface).

Principio: o teste NUNCA corrige o dado. Ele expoe o problema.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from src.db.engine import get_connection, read_sql
from src.logging_setup import logger


@dataclass
class Verificacao:
    nome: str
    categoria: str
    alvo: str
    sql: str
    severidade: str = "WARNING"
    esperado: float | None = 0.0
    tolerancia: float = 0.0
    evidencia: str | None = None
    descricao: str = ""
    # Comparacao: 'igual' (observado == esperado) ou 'menor_igual'
    comparacao: str = "igual"
    params: dict[str, Any] = field(default_factory=dict)


# =====================================================================
# Catalogo de verificacoes (especificacao secao 35)
# =====================================================================

VERIFICACOES: list[Verificacao] = [
    # --- Vendas ---------------------------------------------------
    Verificacao(
        nome="grao_item_unico",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="NUNOTA + SEQUENCIA deve ser unico",
        severidade="CRITICAL",
        sql="""
            SELECT COUNT(*) AS valor FROM (
                SELECT nunota, sequencia FROM analytics.fact_venda_item
                GROUP BY nunota, sequencia HAVING COUNT(*) > 1
            ) x
        """,
        evidencia="""
            SELECT nunota, sequencia, COUNT(*) AS repeticoes
            FROM analytics.fact_venda_item
            GROUP BY nunota, sequencia HAVING COUNT(*) > 1 ORDER BY 3 DESC
        """,
    ),
    Verificacao(
        nome="tipmov_dominio",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="TIPMOV deve conter apenas V ou D",
        severidade="CRITICAL",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE tipmov NOT IN ('V','D') OR tipmov IS NULL",
        evidencia="SELECT DISTINCT tipmov, COUNT(*) FROM analytics.fact_venda_item GROUP BY tipmov",
    ),
    Verificacao(
        nome="devolucao_sinal_negativo",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="Devolucao (TIPMOV=D) deve ter VLRTOT <= 0 — o sinal vem da origem (RN-03)",
        severidade="CRITICAL",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE is_devolucao AND vlrtot > 0",
        evidencia="SELECT nunota, sequencia, vlrtot, tonliq FROM analytics.fact_venda_item WHERE is_devolucao AND vlrtot > 0 LIMIT 200",
    ),
    Verificacao(
        nome="produto_preenchido",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="Todo item deve ter CODPROD",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE codprod IS NULL",
        evidencia="SELECT nunota, sequencia FROM analytics.fact_venda_item WHERE codprod IS NULL LIMIT 200",
    ),
    Verificacao(
        nome="cliente_preenchido",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="Todo item deve ter CODPARC",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE codparc IS NULL",
        evidencia="SELECT nunota, sequencia FROM analytics.fact_venda_item WHERE codparc IS NULL LIMIT 200",
    ),
    Verificacao(
        nome="data_referencia_preenchida",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="Todo item deve ter data de referencia",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE data_referencia IS NULL",
        evidencia="SELECT nunota, sequencia FROM analytics.fact_venda_item WHERE data_referencia IS NULL LIMIT 200",
    ),
    Verificacao(
        nome="item_sem_documento",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="Todo item deve ter documento correspondente",
        severidade="CRITICAL",
        sql="""
            SELECT COUNT(*) AS valor FROM analytics.fact_venda_item i
            LEFT JOIN analytics.fact_venda_documento d ON d.nunota = i.nunota
            WHERE d.nunota IS NULL
        """,
        evidencia="""
            SELECT i.nunota, i.sequencia FROM analytics.fact_venda_item i
            LEFT JOIN analytics.fact_venda_documento d ON d.nunota = i.nunota
            WHERE d.nunota IS NULL LIMIT 200
        """,
    ),
    Verificacao(
        nome="venda_fora_janela_declarada",
        categoria="VENDAS",
        alvo="analytics.fact_venda_item",
        descricao="Registros fora de 2023-01..2026-07 (declarado na fonte) — sinalizar, nao excluir (RN-11)",
        severidade="INFO",
        sql="""
            SELECT COUNT(*) AS valor FROM analytics.fact_venda_item
            WHERE data_referencia < DATE '2023-01-01' OR data_referencia > DATE '2026-07-31'
        """,
        evidencia="""
            SELECT ano_mes, COUNT(*) AS linhas, SUM(vlrtot) AS receita
            FROM analytics.fact_venda_item
            WHERE data_referencia < DATE '2023-01-01' OR data_referencia > DATE '2026-07-31'
            GROUP BY ano_mes ORDER BY ano_mes
        """,
    ),
    # --- Vendedores -----------------------------------------------
    Verificacao(
        nome="venda_sem_vendedor_cadastrado",
        categoria="VENDEDORES",
        alvo="analytics.dim_vendedor",
        descricao="Vendas cujo CODVEND nao existe no cadastro original (Q-02)",
        severidade="WARNING",
        sql="""
            SELECT COUNT(*) AS valor FROM analytics.fact_venda_item i
            JOIN analytics.dim_vendedor v ON v.codvend = i.codvend
            WHERE v.papel_origem = 'SEM_CADASTRO'
        """,
        evidencia="""
            SELECT v.codvend, v.apelido, COUNT(*) AS linhas, SUM(i.vlrtot) AS receita
            FROM analytics.fact_venda_item i
            JOIN analytics.dim_vendedor v ON v.codvend = i.codvend
            WHERE v.papel_origem = 'SEM_CADASTRO'
            GROUP BY v.codvend, v.apelido ORDER BY 4 DESC
        """,
    ),
    Verificacao(
        nome="vendedor_papel_nao_classificado",
        categoria="VENDEDORES",
        alvo="analytics.dim_vendedor",
        descricao="Vendedores com movimento e papel analitico pendente de homologacao (Q-01)",
        severidade="WARNING",
        sql="""
            SELECT COUNT(DISTINCT v.codvend) AS valor
            FROM analytics.dim_vendedor v
            JOIN analytics.fact_venda_item i ON i.codvend = v.codvend
            WHERE v.papel_analitico = 'NAO_CLASSIFICADO'
        """,
        evidencia="""
            SELECT v.codvend, v.apelido, v.tipo_vend, SUM(i.vlrtot) AS receita,
                   COUNT(DISTINCT i.codparc) AS clientes
            FROM analytics.dim_vendedor v
            JOIN analytics.fact_venda_item i ON i.codvend = v.codvend
            WHERE v.papel_analitico = 'NAO_CLASSIFICADO'
            GROUP BY 1,2,3 ORDER BY 4 DESC
        """,
    ),
    # --- Custos ---------------------------------------------------
    Verificacao(
        nome="item_sem_custo",
        categoria="CUSTOS",
        alvo="analytics.fact_venda_item",
        descricao="Itens sem custo encontrado no as-of join (RN-07)",
        severidade="WARNING",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE cost_match_status IN ('SEM_CUSTO','SEM_DATA')",
        evidencia="""
            SELECT codprod, COUNT(*) AS linhas, MIN(data_referencia) AS de, MAX(data_referencia) AS ate
            FROM analytics.fact_venda_item
            WHERE cost_match_status IN ('SEM_CUSTO','SEM_DATA')
            GROUP BY codprod ORDER BY 2 DESC
        """,
    ),
    Verificacao(
        nome="custo_muito_antigo",
        categoria="CUSTOS",
        alvo="analytics.fact_venda_item",
        descricao="Itens cujo custo vigente tem mais de 90 dias",
        severidade="INFO",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_venda_item WHERE cost_age_days > 90",
        evidencia="""
            SELECT codprod, MAX(cost_age_days) AS idade_maxima, COUNT(*) AS linhas
            FROM analytics.fact_venda_item WHERE cost_age_days > 90
            GROUP BY codprod ORDER BY 2 DESC
        """,
    ),
    Verificacao(
        nome="custo_negativo",
        categoria="CUSTOS",
        alvo="analytics.fact_custo_pa",
        descricao="Registros de custo com valor negativo — anomalia preservada (RN-14)",
        severidade="WARNING",
        sql="""
            SELECT COUNT(*) AS valor FROM analytics.fact_custo_pa
            WHERE cusmed < 0 OR cusmedicm < 0 OR cussemicm < 0
               OR cusrep < 0 OR cusger < 0 OR cusvariavel < 0
        """,
        evidencia="""
            SELECT codprod, produto, dtatual, cusmed, cusrep, cusger, cusvariavel
            FROM analytics.fact_custo_pa
            WHERE cusmed < 0 OR cusmedicm < 0 OR cussemicm < 0
               OR cusrep < 0 OR cusger < 0 OR cusvariavel < 0
        """,
    ),
    Verificacao(
        nome="custo_grao_duplicado",
        categoria="CUSTOS",
        alvo="analytics.fact_custo_pa",
        descricao="CODPROD+CODEMP+CODLOCAL+DTATUAL deve ser unico",
        severidade="CRITICAL",
        sql="""
            SELECT COUNT(*) AS valor FROM (
                SELECT codprod, codemp, codlocal, dtatual FROM analytics.fact_custo_pa
                GROUP BY 1,2,3,4 HAVING COUNT(*) > 1
            ) x
        """,
        evidencia="""
            SELECT codprod, codemp, codlocal, dtatual, COUNT(*)
            FROM analytics.fact_custo_pa GROUP BY 1,2,3,4 HAVING COUNT(*) > 1
        """,
    ),
    Verificacao(
        nome="custo_outlier",
        categoria="CUSTOS",
        alvo="analytics.v_venda_item",
        descricao="Itens cujo custo aplicado e outlier (>5x a mediana do produto) — Q-15",
        severidade="WARNING",
        sql="SELECT COUNT(*) AS valor FROM analytics.v_venda_item WHERE custo_outlier",
        evidencia="""
            SELECT codprod, descrprod, ano_mes, COUNT(*) AS linhas,
                   MAX(cusger) AS cusger_max, MAX(med_cusger) AS mediana_produto
            FROM analytics.v_venda_item WHERE custo_outlier
            GROUP BY codprod, descrprod, ano_mes ORDER BY 4 DESC
        """,
    ),
    Verificacao(
        nome="custo_amplitude_extrema",
        categoria="CUSTOS",
        alvo="analytics.fact_custo_pa",
        descricao="Produtos cujo CUSGER varia mais de 100x entre minimo e maximo (Q-15)",
        severidade="WARNING",
        sql="""
            SELECT COUNT(*) AS valor FROM analytics.mv_custo_mediana_produto
            WHERE max_cusger > 100 * NULLIF(min_cusger, 0)
        """,
        evidencia="""
            SELECT m.codprod, p.descrprod, m.min_cusger, m.max_cusger, m.med_cusger, m.registros
            FROM analytics.mv_custo_mediana_produto m
            LEFT JOIN analytics.dim_produto p ON p.codprod = m.codprod
            WHERE m.max_cusger > 100 * NULLIF(m.min_cusger, 0)
            ORDER BY m.max_cusger DESC
        """,
    ),
    # --- Produtos -------------------------------------------------
    Verificacao(
        nome="produto_sem_classificacao",
        categoria="PRODUTOS",
        alvo="analytics.dim_produto",
        descricao="Produtos sem classificacao comercial (Q-12)",
        severidade="WARNING",
        sql="SELECT COUNT(*) AS valor FROM analytics.dim_produto WHERE classificacao = 'NAO_CLASSIFICADO'",
        evidencia="SELECT codprod, descrprod, grupo_produto FROM analytics.dim_produto WHERE classificacao = 'NAO_CLASSIFICADO'",
    ),
    # --- Positivados ----------------------------------------------
    Verificacao(
        nome="positivados_explosao_confere",
        categoria="POSITIVADOS",
        alvo="analytics.fact_positivado",
        descricao="Quantidade explodida deve igualar QTD_POSITIVADOS da fonte (AC-07)",
        severidade="CRITICAL",
        sql="""
            SELECT COUNT(*) AS valor FROM analytics.fact_positivado_mes
            WHERE COALESCE(qtd_positivados_explodido,0) <> COALESCE(qtd_positivados_fonte,0)
        """,
        evidencia="""
            SELECT ano_mes, qtd_positivados_fonte, qtd_positivados_explodido,
                   qtd_positivados_explodido - qtd_positivados_fonte AS diferenca
            FROM analytics.fact_positivado_mes
            WHERE COALESCE(qtd_positivados_explodido,0) <> COALESCE(qtd_positivados_fonte,0)
        """,
    ),
    Verificacao(
        nome="positivado_sem_cliente_na_dim",
        categoria="POSITIVADOS",
        alvo="analytics.fact_positivado",
        descricao="Positivados sem venda na base 2023+ — esperado, pois cobrem 2021+ (RN-09)",
        severidade="INFO",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_positivado WHERE NOT cliente_existe_dim",
        evidencia="""
            SELECT ano_mes, COUNT(*) AS clientes
            FROM analytics.fact_positivado WHERE NOT cliente_existe_dim
            GROUP BY ano_mes ORDER BY ano_mes
        """,
    ),
    # --- CT-e / logistica -----------------------------------------
    Verificacao(
        nome="cte_sem_nfe_vinculada",
        categoria="LOGISTICA",
        alvo="analytics.fact_cte",
        descricao="CT-e sem nenhuma NF-e de venda vinculada (Q-08)",
        severidade="WARNING",
        sql="SELECT COUNT(*) AS valor FROM analytics.fact_cte WHERE qtd_nfe_vinculadas = 0",
        evidencia="""
            SELECT ano_mes, COUNT(*) AS ctes, SUM(vlrnota) AS frete
            FROM analytics.fact_cte WHERE qtd_nfe_vinculadas = 0
            GROUP BY ano_mes ORDER BY ano_mes
        """,
    ),
    Verificacao(
        nome="vinculo_cte_sem_match",
        categoria="LOGISTICA",
        alvo="analytics.bridge_cte_nfe",
        descricao="Chaves NF-e citadas no CT-e que nao existem na base de vendas",
        severidade="WARNING",
        sql="SELECT COUNT(*) AS valor FROM analytics.bridge_cte_nfe WHERE match_status = 'SEM_VINCULO'",
        evidencia="""
            SELECT chavecte, chave_nfe, numero_nota_venda
            FROM analytics.bridge_cte_nfe WHERE match_status = 'SEM_VINCULO' LIMIT 200
        """,
    ),
    Verificacao(
        nome="soma_rateio_por_cte",
        categoria="LOGISTICA",
        alvo="analytics.bridge_cte_nfe",
        descricao="A soma dos pesos de rateio de um CT-e com vinculo deve ser 1",
        severidade="CRITICAL",
        sql="""
            SELECT COUNT(*) AS valor FROM (
                SELECT frete_id, SUM(allocation_weight) AS peso
                FROM analytics.bridge_cte_nfe
                WHERE match_status <> 'SEM_VINCULO'
                GROUP BY frete_id HAVING ABS(SUM(allocation_weight) - 1) > 0.0001
            ) x
        """,
        evidencia="""
            SELECT frete_id, SUM(allocation_weight) AS peso, COUNT(*) AS vinculos
            FROM analytics.bridge_cte_nfe WHERE match_status <> 'SEM_VINCULO'
            GROUP BY frete_id HAVING ABS(SUM(allocation_weight) - 1) > 0.0001 LIMIT 200
        """,
    ),
    # --- Regras de seguranca analitica -----------------------------
    Verificacao(
        nome="medida_documento_fora_do_item",
        categoria="SEGURANCA_ANALITICA",
        alvo="analytics.fact_venda_item",
        descricao="fact_venda_item nao pode conter vlrnota nem vlrfrete_ordemcarga (RN-02)",
        severidade="CRITICAL",
        sql="""
            SELECT COUNT(*) AS valor FROM information_schema.columns
            WHERE table_schema = 'analytics' AND table_name = 'fact_venda_item'
              AND column_name IN ('vlrnota', 'vlrfrete_ordemcarga')
        """,
        evidencia="""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='analytics' AND table_name='fact_venda_item'
              AND column_name IN ('vlrnota','vlrfrete_ordemcarga')
        """,
    ),
]


def executar_verificacoes(batch_id: int | None = None) -> list[dict[str, Any]]:
    """Roda todo o catalogo e grava os resultados. Devolve o resumo."""
    resultados: list[dict[str, Any]] = []

    with get_connection() as conn:
        conn.execute(text("DELETE FROM app.data_quality_check"))

    for v in VERIFICACOES:
        try:
            df = read_sql(v.sql, v.params)
            observado = float(df["valor"][0]) if df.height else 0.0
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Verificacao '{v.nome}' falhou ao executar: {exc}")
            _gravar(v, batch_id, None, "SKIPPED", f"Erro ao executar: {exc}"[:500])
            resultados.append({"nome": v.nome, "status": "SKIPPED", "observado": None})
            continue

        esperado = v.esperado if v.esperado is not None else 0.0
        dentro = (
            abs(observado - esperado) <= v.tolerancia
            if v.comparacao == "igual"
            else observado <= esperado + v.tolerancia
        )

        if dentro:
            status = "PASS"
        elif v.severidade == "CRITICAL":
            status = "FAIL"
        elif v.severidade == "INFO":
            status = "PASS"  # informativo: registra o numero, nao reprova
        else:
            status = "WARN"

        msg = f"{v.descricao} | observado: {observado:,.0f}".replace(",", ".")
        _gravar(v, batch_id, observado, status, msg)
        resultados.append(
            {"nome": v.nome, "categoria": v.categoria, "status": status,
             "observado": observado, "severidade": v.severidade}
        )

        nivel = {"FAIL": logger.error, "WARN": logger.warning}.get(status, logger.info)
        nivel(f"[{status}] {v.nome}: {observado:,.0f}".replace(",", "."))

    falhas = sum(1 for r in resultados if r["status"] == "FAIL")
    avisos = sum(1 for r in resultados if r["status"] == "WARN")
    logger.info(
        f"Qualidade: {len(resultados)} verificacoes, {falhas} falha(s), {avisos} aviso(s)"
    )
    return resultados


def _gravar(
    v: Verificacao,
    batch_id: int | None,
    observado: float | None,
    status: str,
    mensagem: str,
) -> None:
    sql = """
        INSERT INTO app.data_quality_check
            (batch_id, check_name, category, target_object, severity, status,
             observed, expected, tolerance, message, evidence_sql)
        VALUES (:b, :n, :c, :t, :sev, :st, :obs, :exp, :tol, :msg, :ev)
    """
    with get_connection() as conn:
        conn.execute(
            text(sql),
            {
                "b": batch_id, "n": v.nome, "c": v.categoria, "t": v.alvo,
                "sev": v.severidade, "st": status, "obs": observado,
                "exp": v.esperado, "tol": v.tolerancia, "msg": mensagem,
                "ev": (v.evidencia or "").strip() or None,
            },
        )


def resumo() -> dict[str, Any]:
    """Resumo para a pagina de Qualidade."""
    df = read_sql(
        """
        SELECT status, COUNT(*) AS n FROM app.data_quality_check GROUP BY status
        """
    )
    contagem = {r["status"]: int(r["n"]) for r in df.iter_rows(named=True)}
    return {
        "total": sum(contagem.values()),
        "pass": contagem.get("PASS", 0),
        "warn": contagem.get("WARN", 0),
        "fail": contagem.get("FAIL", 0),
        "skipped": contagem.get("SKIPPED", 0),
    }
