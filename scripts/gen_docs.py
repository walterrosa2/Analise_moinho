"""
Gera docs/data_dictionary.md e docs/reconciliation.md a partir do BANCO REAL.

Documentacao escrita a mao envelhece; esta e derivada do schema e dos
resultados vigentes, entao acompanha o modelo automaticamente.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.db.engine import read_sql
from src.metrics import registry

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def _fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return str(v)


def dicionario_de_dados() -> str:
    L: list[str] = [
        "# Dicionário de Dados",
        "",
        "> Gerado por `scripts/gen_docs.py` a partir do schema real do banco.",
        "> Não editar à mão: rode o script novamente após alterar uma migration.",
        "",
    ]

    volumetria = read_sql(
        """
        SELECT table_schema, table_name,
               (SELECT COUNT(*) FROM information_schema.columns c
                 WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) AS colunas
        FROM information_schema.tables t
        WHERE table_schema IN ('raw', 'analytics', 'app') AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name
        """
    )

    L += ["## Camadas", "",
          "| Schema | Papel |", "|---|---|",
          "| `raw` | Cópia fiel do Excel, tudo TEXT, com metadados de linhagem. Nunca alterada. |",
          "| `staging` | Transformações intermediárias (em memória, no ETL). |",
          "| `analytics` | Modelo dimensional consumido pela aplicação. |",
          "| `app` | Estado da plataforma: lotes, qualidade, reconciliação, visões salvas. |",
          ""]

    for schema in ("analytics", "app", "raw"):
        tabelas = volumetria.filter(volumetria["table_schema"] == schema)
        if tabelas.height == 0:
            continue
        L += ["---", "", f"## Schema `{schema}`", ""]

        for t in tabelas.iter_rows(named=True):
            nome = t["table_name"]
            try:
                n = read_sql(f'SELECT COUNT(*) AS n FROM "{schema}"."{nome}"')["n"][0]
            except Exception:  # noqa: BLE001
                n = None

            comentario = read_sql(
                """
                SELECT obj_description(
                    (:s || '.' || :t)::regclass, 'pg_class'
                ) AS descricao
                """,
                {"s": schema, "t": nome},
            )
            desc = comentario["descricao"][0] if comentario.height else None

            L += [f"### `{schema}.{nome}`", ""]
            if desc:
                L += [f"> {desc}", ""]
            L += [f"- Linhas: **{_fmt(n)}** · Colunas: {t['colunas']}", ""]

            if schema == "raw":
                L += ["Todas as colunas são `TEXT` (fidelidade à origem), mais os metadados "
                      "`_source_file`, `_source_sheet`, `_source_row`, `_ingestion_batch_id`, "
                      "`_ingested_at` e `_source_file_hash`.", ""]
                continue

            colunas = read_sql(
                """
                SELECT c.column_name, c.data_type, c.is_nullable,
                       col_description((:s || '.' || :t)::regclass, c.ordinal_position) AS comentario
                FROM information_schema.columns c
                WHERE c.table_schema = :s AND c.table_name = :t
                ORDER BY c.ordinal_position
                """,
                {"s": schema, "t": nome},
            )
            L += ["| Coluna | Tipo | Nulo? | Observação |", "|---|---|---|---|"]
            for c in colunas.iter_rows(named=True):
                obs = (c["comentario"] or "").replace("\n", " ").replace("|", "\\|")
                L.append(
                    f"| `{c['column_name']}` | {c['data_type']} | "
                    f"{'sim' if c['is_nullable'] == 'YES' else 'não'} | {obs or '—'} |"
                )
            L.append("")

    # Views e MVs
    views = read_sql(
        """
        SELECT matviewname AS nome, 'materialized view' AS tipo FROM pg_matviews
        WHERE schemaname = 'analytics'
        UNION ALL
        SELECT viewname, 'view' FROM pg_views WHERE schemaname = 'analytics'
        ORDER BY 2, 1
        """
    )
    if views.height:
        L += ["---", "", "## Views do schema `analytics`", "",
              "| Objeto | Tipo | Linhas |", "|---|---|---|"]
        for v in views.iter_rows(named=True):
            try:
                n = read_sql(f'SELECT COUNT(*) AS n FROM analytics."{v["nome"]}"')["n"][0]
            except Exception:  # noqa: BLE001
                n = None
            L.append(f"| `analytics.{v['nome']}` | {v['tipo']} | {_fmt(n)} |")
        L.append("")

    # Registro de métricas
    L += ["---", "", "## Registro de métricas", "",
          "Fonte: `src/metrics/registry.py`. Nenhuma fórmula vive dentro de uma página.", "",
          "| ID | Métrica | Unidade | Grão | Fórmula | Status |", "|---|---|---|---|---|---|"]
    for m in registry.listar():
        formula = m.formula.replace("|", "\\|")
        L.append(
            f"| `{m.id}` | {m.label} | {m.unidade.value} | {m.grao} | `{formula}` | {m.status.value} |"
        )
    L.append("")

    return "\n".join(L)


def relatorio_reconciliacao() -> str:
    L = [
        "# Reconciliação — modelo calculado × fonte gerencial",
        "",
        "> Gerado por `scripts/gen_docs.py` a partir de `app.reconciliation_result`.",
        "",
        "**Regra inegociável:** nenhum dado é ajustado para 'bater'. Divergência acima da",
        "tolerância permanece marcada como `DIVERGENTE` até ser explicada.",
        "",
        "---",
        "",
        "## Mapeamento descoberto",
        "",
        "O relatório 161 não documenta o significado de seus tipos. O confronto numérico",
        "estabeleceu a correspondência:",
        "",
        "| `TIPO` no 161 | Equivale no modelo | Evidência (2023) |",
        "|---|---|---|",
        "| `REALIZADO` | **vendas brutas** (sem devolução) | R$ 144,44 mi / 51.171 t ↔ R$ 144,44 mi / 51.172 t |",
        "| `REAL.-DEVOLUÇÃO` | **receita líquida** (com devolução) | R$ 142,18 mi / 50.484 t ↔ R$ 142,18 mi / 50.484 t |",
        "| `DEVOLUÇÃO` | devoluções (positivo na fonte, negativo no modelo) | R$ 2,26 mi ↔ −R$ 2,26 mi |",
        "",
        "Mapear `REALIZADO` para o líquido — a leitura intuitiva do nome — produzia ~2,3% de",
        "divergência sistemática em todos os meses.",
        "",
        "---",
        "",
        "## Resultado por escopo",
        "",
    ]

    resumo = read_sql(
        """
        SELECT scope, metric_id, status, COUNT(*) AS pontos,
               ROUND(AVG(ABS(diff_pct))::numeric, 3) AS divergencia_media_pct,
               ROUND(MAX(ABS(diff_pct))::numeric, 3) AS divergencia_maxima_pct
        FROM app.reconciliation_result
        GROUP BY scope, metric_id, status
        ORDER BY scope, metric_id, status
        """
    )
    L += ["| Escopo | Métrica | Situação | Pontos | Divergência média | Máxima |",
          "|---|---|---|---|---|---|"]
    for r in resumo.iter_rows(named=True):
        L.append(
            f"| `{r['scope']}` | {r['metric_id']} | {r['status']} | {r['pontos']} | "
            f"{_fmt(r['divergencia_media_pct'])}% | {_fmt(r['divergencia_maxima_pct'])}% |"
        )
    L.append("")

    mensal = read_sql(
        """
        SELECT COUNT(*) AS pontos,
               COUNT(*) FILTER (WHERE status = 'OK') AS ok,
               ROUND(AVG(ABS(diff_pct))::numeric, 4) AS media
        FROM app.reconciliation_result WHERE scope = '161_MENSAL_TOTAL'
        """
    )
    if mensal.height:
        r = mensal.to_dicts()[0]
        L += ["---", "", "## Conclusão", "",
              f"A reconciliação mensal total fecha em **{r['ok']}/{r['pontos']} pontos dentro da",
              f"tolerância de 0,5%**, com divergência média de **{_fmt(r['media'])}%**.",
              "",
              "A divergência que aparece ao quebrar por classificação vem exclusivamente da regra",
              "produto → categoria, ainda `PROVISIONAL` (ver `docs/open_questions.md`, Q-12 e Q-14).",
              "",
              "As métricas de `161 OUTROS` (`Vr ICMS`, `Vr Comissão`) não são reproduzíveis pela",
              "base transacional atual — a hipótese e o que destravaria estão em Q-13.",
              ""]

    detalhe = read_sql(
        """
        SELECT period, dimension, metric_id, value_source, value_model, diff_pct, status
        FROM app.reconciliation_result
        WHERE scope = '161_MENSAL_TOTAL'
        ORDER BY period, metric_id
        """
    )
    if detalhe.height:
        L += ["---", "", "## Detalhe mensal (total, sem quebra por classificação)", "",
              "| Período | Métrica | Fonte (161) | Modelo | Diferença % | Situação |",
              "|---|---|---|---|---|---|"]
        for r in detalhe.iter_rows(named=True):
            L.append(
                f"| {r['period']} | {r['metric_id']} | {_fmt(r['value_source'])} | "
                f"{_fmt(r['value_model'])} | {_fmt(r['diff_pct'])}% | {r['status']} |"
            )
        L.append("")

    return "\n".join(L)


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data_dictionary.md").write_text(dicionario_de_dados(), encoding="utf-8")
    print(f"OK  {DOCS / 'data_dictionary.md'}")
    (DOCS / "reconciliation.md").write_text(relatorio_reconciliacao(), encoding="utf-8")
    print(f"OK  {DOCS / 'reconciliation.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
