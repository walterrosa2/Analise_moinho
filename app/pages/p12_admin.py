"""Admin e Diagnóstico — estado do pipeline, configuração e catálogo de fontes."""
from __future__ import annotations

import polars as pl
import streamlit as st

from app.components import ui
from src.config import get_settings, list_source_contracts, load_yaml
from src.db import migrate
from src.db.engine import read_sql

st.title("Admin e Diagnóstico")

settings = get_settings()

abas = st.tabs(["Estado do banco", "Cargas", "Configuração", "Catálogo de fontes", "Auditoria"])

# ---------------------------------------------------------------------
with abas[0]:
    ui.secao("Conexão")
    c = st.columns(3)
    c[0].metric("Banco", settings.postgres_db)
    c[1].metric("Host:porta", f"{settings.postgres_host}:{settings.postgres_port}")
    c[2].metric("Nível de log", settings.log_level)
    st.caption(f"URL: `{settings.db_url_safe}` — a senha nunca é exibida nem registrada em log.")

    ui.secao("Migrations")
    status = pl.DataFrame(migrate.status())
    ui.tabela(status, "migrations", altura=260, chave="mig")
    divergentes = status.filter(pl.col("checksum_ok") == False)  # noqa: E712
    if divergentes.height:
        st.warning(
            f"{divergentes.height} migration(s) foram alteradas depois de aplicadas. "
            "Crie uma nova migration em vez de editar uma já aplicada.",
            icon="⚠️",
        )

    ui.secao("Volumetria")
    vol = read_sql(
        """
        SELECT schemaname AS schema, relname AS tabela, n_live_tup AS linhas_estimadas,
               pg_size_pretty(pg_total_relation_size(relid)) AS tamanho
        FROM pg_stat_user_tables
        WHERE schemaname IN ('raw', 'analytics', 'app')
        ORDER BY pg_total_relation_size(relid) DESC
        """
    )
    ui.tabela(vol, "volumetria_banco", altura=420, chave="vol")

    ui.secao("Materialized views")
    mvs = read_sql(
        """
        SELECT schemaname AS schema, matviewname AS view,
               pg_size_pretty(pg_total_relation_size(
                   (schemaname || '.' || matviewname)::regclass)) AS tamanho,
               ispopulated AS populada
        FROM pg_matviews WHERE schemaname = 'analytics'
        ORDER BY matviewname
        """
    )
    ui.tabela(mvs, "materialized_views", altura=340, chave="mvs")

# ---------------------------------------------------------------------
with abas[1]:
    ui.secao("Histórico de cargas")
    lotes = read_sql(
        """
        SELECT batch_id, source_id, source_file, source_sheet, status,
               rows_read, rows_loaded, started_at, finished_at, duration_ms,
               LEFT(source_file_hash, 16) AS hash, error_message
        FROM app.ingestion_batch ORDER BY batch_id DESC LIMIT 200
        """
    )
    ui.tabela(lotes, "lotes_carga", altura=440, chave="lotes")

    falhas = lotes.filter(pl.col("status") == "FAILED")
    if falhas.height:
        st.error(f"{falhas.height} carga(s) falharam. Detalhes na coluna `error_message`.")

    ui.secao("Como recarregar")
    st.code(
        "# Carga incremental (pula arquivos com o mesmo hash)\n"
        "py scripts/run_pipeline.py\n\n"
        "# Recarga completa\n"
        "py scripts/run_pipeline.py --forcar\n\n"
        "# Apenas uma etapa\n"
        "py scripts/run_pipeline.py --etapa views",
        language="bash",
    )

# ---------------------------------------------------------------------
with abas[2]:
    ui.secao("Parâmetros analíticos", "Tudo aqui é regra de negócio — nada é hardcode.")
    cfg = load_yaml("settings.yaml")
    st.json(cfg, expanded=False)

    ui.secao("Classificação de produto")
    st.json(load_yaml("product_classification.yaml"), expanded=False)

    ui.secao("Papéis de vendedor")
    papeis = load_yaml("seller_roles.yaml")
    st.json(papeis, expanded=False)
    if papeis.get("status") != "HOMOLOGADO":
        st.warning(
            f"Status: **{papeis.get('status', 'desconhecido')}**. Enquanto não for homologado, "
            "rankings de produtividade de RCA excluem os códigos `NAO_CLASSIFICADO` (Q-01).",
            icon="⚠️",
        )

    ui.secao("Contratos de dados")
    contratos = pl.DataFrame([
        {
            "source_id": c.get("source_id"),
            "arquivo": c.get("filename"),
            "aba": c.get("sheet"),
            "tabela_raw": c.get("raw_table"),
            "ordem": c.get("load_order"),
            "obrigatorias": len(c.get("required_columns") or []),
            "colunas": len(c.get("all_columns") or []),
            "bloqueadas": len(c.get("colunas_proibidas") or []),
        }
        for c in list_source_contracts()
    ])
    ui.tabela(contratos, "contratos", altura=380, chave="contratos")

    bloqueadas = contratos.filter(pl.col("bloqueadas") > 0)
    if bloqueadas.height:
        st.info(
            "Colunas com credenciais em texto claro são **bloqueadas na leitura** — não entram "
            "nem na camada RAW. Ver `docs/decisions.md` (ADR-005).",
            icon="🔒",
        )

# ---------------------------------------------------------------------
with abas[3]:
    ui.secao(
        "Catálogo de fontes de dados",
        "Inventário de relatórios disponíveis e backlog de dados que ainda faltam.",
    )
    catalogo = read_sql(
        "SELECT origem, relatorio, descricao, status FROM app.data_source_catalog "
        "ORDER BY status, relatorio"
    )
    ui.tabela(catalogo, "catalogo_fontes", altura=460, chave="catalogo")
    st.caption(
        "As credenciais presentes na planilha de inventário **nunca** são importadas, "
        "exibidas ou registradas em log."
    )

# ---------------------------------------------------------------------
with abas[4]:
    ui.secao("Trilha de auditoria", "Últimos eventos de `logs/audit.jsonl`.")
    caminho = settings.log_path / "audit.jsonl"
    if not caminho.exists():
        st.info("Nenhum evento de auditoria registrado ainda.")
    else:
        import json

        linhas = caminho.read_text(encoding="utf-8", errors="replace").splitlines()[-300:]
        eventos = []
        for linha in reversed(linhas):
            try:
                registro = json.loads(linha)
                payload = registro.get("record", {}).get("message", {})
                if isinstance(payload, str):
                    payload = json.loads(payload.replace("'", '"'))
                eventos.append({
                    "timestamp": payload.get("timestamp", ""),
                    "ator": payload.get("actor", ""),
                    "ação": payload.get("action", ""),
                    "alvo": payload.get("target", ""),
                    "resultado": payload.get("outcome", ""),
                    "dados": str(payload.get("data", ""))[:160],
                })
            except Exception:  # noqa: BLE001
                continue
        if eventos:
            ui.tabela(pl.DataFrame(eventos), "auditoria", altura=460, chave="audit")
        else:
            st.info("Nenhum evento estruturado encontrado no arquivo de auditoria.")

    st.caption(
        "Chaves sensíveis (senha, token, CNPJ/CPF) são redigidas antes da escrita — "
        "ver `src/logging_setup.py`."
    )
