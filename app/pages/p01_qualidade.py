"""
Página de Qualidade e Reconciliação.

A especificação (§28) trata esta tela como obrigatória: sem ela a plataforma
"corre o risco de parecer precisa sem realmente ser confiável".
É a primeira página construída, de propósito.
"""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from src.db.engine import read_sql
from src.metrics import registry

st.title("Qualidade e Reconciliação dos Dados")
st.caption(
    "Antes de apresentar qualquer número, veja aqui o que é confiável, o que diverge "
    "e o que ainda aguarda decisão do negócio."
)


@st.cache_data(ttl=300, show_spinner=False)
def _carga() -> pl.DataFrame:
    return read_sql(
        """
        SELECT source_id, source_file, source_sheet, status, rows_read, rows_loaded,
               started_at, duration_ms, source_file_hash, error_message
        FROM app.ingestion_batch
        WHERE status IN ('SUCCESS', 'FAILED')
        ORDER BY started_at DESC
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def _qualidade() -> pl.DataFrame:
    return read_sql(
        """
        SELECT check_name, category, target_object, severity, status,
               observed, expected, message, evidence_sql, run_at
        FROM app.data_quality_check
        ORDER BY CASE status WHEN 'FAIL' THEN 1 WHEN 'WARN' THEN 2 ELSE 3 END,
                 category, check_name
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def _reconciliacao() -> pl.DataFrame:
    return read_sql(
        """
        SELECT scope, period, dimension, metric_id, value_source, value_model,
               diff_abs, diff_pct, tolerance_pct, status, explanation
        FROM app.reconciliation_result
        ORDER BY scope, period, dimension, metric_id
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def _evidencia(sql: str) -> pl.DataFrame:
    return read_sql(sql)


@st.cache_data(ttl=300, show_spinner=False)
def _volumetria() -> pl.DataFrame:
    return read_sql(
        """
        SELECT 'analytics.fact_venda_item'      AS tabela, COUNT(*) AS linhas FROM analytics.fact_venda_item
        UNION ALL SELECT 'analytics.fact_venda_documento', COUNT(*) FROM analytics.fact_venda_documento
        UNION ALL SELECT 'analytics.fact_custo_pa',        COUNT(*) FROM analytics.fact_custo_pa
        UNION ALL SELECT 'analytics.fact_cte',             COUNT(*) FROM analytics.fact_cte
        UNION ALL SELECT 'analytics.bridge_cte_nfe',       COUNT(*) FROM analytics.bridge_cte_nfe
        UNION ALL SELECT 'analytics.fact_positivado',      COUNT(*) FROM analytics.fact_positivado
        UNION ALL SELECT 'analytics.fact_gestao_diaria',   COUNT(*) FROM analytics.fact_gestao_diaria
        UNION ALL SELECT 'analytics.fact_despesa_mensal',  COUNT(*) FROM analytics.fact_despesa_mensal
        UNION ALL SELECT 'analytics.dim_cliente',          COUNT(*) FROM analytics.dim_cliente
        UNION ALL SELECT 'analytics.dim_produto',          COUNT(*) FROM analytics.dim_produto
        UNION ALL SELECT 'analytics.dim_vendedor',         COUNT(*) FROM analytics.dim_vendedor
        ORDER BY 2 DESC
        """
    )


carga = _carga()
checks = _qualidade()
recon = _reconciliacao()

# ---------------------------------------------------------------------
# Cartões de estado geral
# ---------------------------------------------------------------------
c = st.columns(5)
falhas = checks.filter(pl.col("status") == "FAIL").height
avisos = checks.filter(pl.col("status") == "WARN").height
ok_recon = recon.filter(pl.col("status") == "OK").height
div_recon = recon.filter(pl.col("status") == "DIVERGENTE").height

ui.cartao(c[0], "Última carga",
          str(carga["started_at"][0])[:16] if carga.height else "—",
          ajuda="Momento do último lote carregado com sucesso.")
ui.cartao(c[1], "Linhas carregadas", ui.inteiro(carga["rows_loaded"].sum() if carga.height else 0))
ui.cartao(c[2], "Verificações", f"{checks.height}",
          delta=f"{falhas} falha(s)" if falhas else "sem falhas",
          delta_invertido=bool(falhas))
ui.cartao(c[3], "Avisos", f"{avisos}", ajuda="Situações conhecidas e documentadas.")
ui.cartao(c[4], "Reconciliação",
          f"{ok_recon}/{ok_recon + div_recon}" if (ok_recon + div_recon) else "—",
          ajuda="Pontos dentro da tolerância de 0,5%.")

if falhas:
    st.error(f"**{falhas} verificação(ões) crítica(s) falharam.** Corrija antes de apresentar números.")
else:
    st.success("Nenhuma verificação crítica falhou. Os avisos abaixo são situações conhecidas e documentadas.")

abas = st.tabs([
    "Verificações", "Reconciliação com o 161", "Cargas e linhagem",
    "Registro de métricas", "Dúvidas em aberto",
])

# ---------------------------------------------------------------------
# 1. Verificações
# ---------------------------------------------------------------------
with abas[0]:
    ui.secao("Testes automáticos de qualidade",
             "Nenhum teste corrige o dado — todos apenas expõem o que foi encontrado.")

    for categoria in checks["category"].unique().sort().to_list():
        sub = checks.filter(pl.col("category") == categoria)
        n_fail = sub.filter(pl.col("status") == "FAIL").height
        n_warn = sub.filter(pl.col("status") == "WARN").height
        marca = "🔴" if n_fail else ("🟡" if n_warn else "✅")
        with st.expander(f"{marca} {categoria} — {sub.height} verificação(ões)",
                         expanded=bool(n_fail)):
            for r in sub.iter_rows(named=True):
                col1, col2 = st.columns([5, 1])
                col1.markdown(
                    f"**{ui.selo_status(r['status'])} · `{r['check_name']}`**  \n"
                    f"{r['message'] or ''}  \n"
                    f"<small>Alvo: `{r['target_object']}` · severidade {r['severity']}</small>",
                    unsafe_allow_html=True,
                )
                mostrar = (
                    r["evidence_sql"]
                    and (r["observed"] or 0) > 0
                    and col2.button("Ver evidência", key=f"ev_{r['check_name']}",
                                    use_container_width=True)
                )
                if mostrar:
                    st.session_state[f"show_{r['check_name']}"] = True
                if st.session_state.get(f"show_{r['check_name']}"):
                    with st.container(border=True):
                        st.caption("Linhas que originaram este resultado")
                        try:
                            ev = _evidencia(r["evidence_sql"])
                            ui.tabela(ev, f"evidencia_{r['check_name']}", altura=300,
                                      chave=f"ev_{r['check_name']}")
                        except Exception as exc:  # noqa: BLE001
                            st.warning(f"Não foi possível carregar a evidência: {exc}")
                        st.code(r["evidence_sql"].strip(), language="sql")
                st.divider()

# ---------------------------------------------------------------------
# 2. Reconciliação
# ---------------------------------------------------------------------
with abas[1]:
    ui.secao(
        "Modelo calculado × fonte gerencial",
        "Divergência nunca é ajustada para 'bater'. Quando existe, é explicada.",
    )

    st.markdown(
        "**Leitura essencial:** o `TIPO = REALIZADO` do 161 corresponde à **venda bruta** do "
        "modelo, e `REAL.-DEVOLUÇÃO` ao **líquido de devolução** — descoberto por confronto "
        "numérico, não estava documentado na fonte."
    )

    resumo = recon.group_by(["scope", "metric_id", "status"]).agg(
        pl.len().alias("pontos"),
        pl.col("diff_pct").abs().mean().round(3).alias("divergencia_media_pct"),
    ).sort(["scope", "metric_id", "status"])
    ui.tabela(resumo, "reconciliacao_resumo", altura=320, chave="rec_resumo")

    mensal = recon.filter(pl.col("scope") == "161_MENSAL_TOTAL")
    if mensal.height:
        ok = mensal.filter(pl.col("status") == "OK").height
        media = float(mensal["diff_pct"].abs().mean() or 0)
        st.success(
            f"**Reconciliação mensal total: {ok}/{mensal.height} pontos dentro de 0,5%**, "
            f"divergência média de {ui.percentual(media, 3)}. "
            "A divergência que resta ao quebrar por classificação vem da regra "
            "produto → categoria, ainda provisional (Q-12/Q-14)."
        )
        ui.grafico(
            ui.linha(
                mensal.filter(pl.col("metric_id") == "receita_liquida").sort("period"),
                "period", "diff_pct",
                "Divergência % por mês — receita líquida (tolerância ±0,5%)",
            ),
            mensal, "reconciliacao_mensal",
        )

    escopos = recon["scope"].unique().sort().to_list()
    escolhido = st.selectbox("Detalhar escopo", escopos, key="rec_escopo")
    detalhe = recon.filter(pl.col("scope") == escolhido).with_columns(
        pl.col("status").map_elements(ui.selo_status, return_dtype=pl.Utf8).alias("situacao")
    ).select(
        "period", "dimension", "metric_id", "value_source", "value_model",
        "diff_abs", "diff_pct", "situacao", "explanation",
    )
    ui.tabela(detalhe, f"reconciliacao_{escolhido}", altura=420, chave="rec_det")

# ---------------------------------------------------------------------
# 3. Cargas e linhagem
# ---------------------------------------------------------------------
with abas[2]:
    ui.secao("Lotes de carga", "Cada lote guarda o hash do arquivo: recarregar o mesmo arquivo não duplica dados.")
    ui.tabela(
        carga.select("source_id", "source_file", "source_sheet", "status",
                     "rows_read", "rows_loaded", "started_at", "duration_ms",
                     pl.col("source_file_hash").str.slice(0, 12).alias("hash")),
        "cargas", altura=380, chave="cargas",
    )

    ui.secao("Volumetria do modelo analítico")
    ui.tabela(_volumetria(), "volumetria", altura=340, chave="volumetria")

    ui.secao("Linhagem")
    st.markdown(
        """
| Camada | O que é | Onde |
|---|---|---|
| Origem | Planilhas Excel, **nunca modificadas** | `data/input/` |
| RAW | Cópia fiel, tudo texto, com 6 metadados de linhagem | `raw.*` |
| Parquet | Cópia colunar para ETL (o Excel não é relido) | `data/parquet/` |
| Staging | Tipagem, TRIM, decimal pt-BR, `'NULL'` → NULL, domínios normalizados | em memória |
| Analytics | Dimensões, fatos, ponte, as-of de custo, rateio de frete | `analytics.*` |
| Views | Recortes mensais pré-agregados | `analytics.mv_*` |

Toda linha de `raw.*` carrega `_source_file`, `_source_sheet`, `_source_row`,
`_ingestion_batch_id`, `_ingested_at` e `_source_file_hash`.
"""
    )

# ---------------------------------------------------------------------
# 4. Registro de métricas
# ---------------------------------------------------------------------
with abas[3]:
    ui.secao(
        "Registro central de métricas",
        "Nenhuma fórmula vive dentro de uma página. Toda métrica é declarada uma vez, "
        "com grão, fonte, regra de sinal e status.",
    )
    tabela_metricas = pl.DataFrame(registry.como_tabela())
    categorias = ["(todas)"] + registry.categorias()
    cat = st.selectbox("Categoria", categorias, key="met_cat")
    if cat != "(todas)":
        tabela_metricas = tabela_metricas.filter(pl.col("Categoria") == cat)
    ui.tabela(tabela_metricas, "registro_metricas", altura=520, chave="metricas")

    st.caption(
        "Status: **PROVISIONAL** = calculada, ainda não confrontada · "
        "**RECONCILIADA** = confrontada com fonte gerencial dentro da tolerância · "
        "**HOMOLOGADA** = validada pelo negócio (nenhuma está, ainda)."
    )

# ---------------------------------------------------------------------
# 5. Dúvidas em aberto
# ---------------------------------------------------------------------
with abas[4]:
    ui.secao(
        "Decisões que não foram tomadas em silêncio",
        "Enquanto uma pergunta estiver aberta, a métrica dependente permanece provisional.",
    )
    caminho = "docs/open_questions.md"
    try:

        from src.config import get_settings

        texto = (get_settings().root / caminho).read_text(encoding="utf-8")
        ui.markdown_seguro(texto)
    except Exception:  # noqa: BLE001
        st.warning(f"Não foi possível ler `{caminho}`.")
