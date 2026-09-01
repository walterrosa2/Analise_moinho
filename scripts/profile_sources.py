"""
Fase 0 - Discovery Tecnico.

Le TODOS os arquivos Excel de data/input, sem alterar nada, e gera:
  - docs/source_profile.md  : perfil real (abas, colunas, tipos, nulos, cardinalidade)
  - artifacts/profile.json  : perfil em formato maquina

Regra: evidencia > suposicao. Nada aqui assume o que a especificacao diz.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
DOCS_DIR = ROOT / "docs"
ARTIFACTS_DIR = ROOT / "artifacts"

MAX_DISTINCT_SHOWN = 25


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def list_sheets(path: Path) -> list[str]:
    import fastexcel

    reader = fastexcel.read_excel(str(path))
    return list(reader.sheet_names)


def read_sheet(path: Path, sheet: str) -> pl.DataFrame:
    import fastexcel

    reader = fastexcel.read_excel(str(path))
    sheet_obj = reader.load_sheet_by_name(sheet)
    return sheet_obj.to_polars()


def profile_column(df: pl.DataFrame, col: str) -> dict:
    s = df.get_column(col)
    n = s.len()
    n_null = int(s.null_count())
    try:
        n_unique = int(s.n_unique())
    except Exception:
        n_unique = -1

    info: dict = {
        "coluna": col,
        "dtype": str(s.dtype),
        "linhas": n,
        "nulos": n_null,
        "pct_nulo": round(100.0 * n_null / n, 2) if n else 0.0,
        "distintos": n_unique,
    }

    non_null = s.drop_nulls()
    if non_null.len() == 0:
        info["amostra"] = []
        return info

    if s.dtype.is_numeric():
        try:
            info["min"] = float(non_null.min())
            info["max"] = float(non_null.max())
            info["media"] = round(float(non_null.mean()), 4)
            info["negativos"] = int((non_null < 0).sum())
            info["zeros"] = int((non_null == 0).sum())
        except Exception:
            pass
    elif s.dtype in (pl.Date, pl.Datetime):
        info["min"] = str(non_null.min())
        info["max"] = str(non_null.max())

    # Amostra de valores distintos (util para dominios pequenos: TIPMOV, CIF_FOB, TIPO...)
    if 0 < n_unique <= MAX_DISTINCT_SHOWN:
        try:
            vals = non_null.unique().sort().to_list()
            info["dominio"] = [str(v) for v in vals]
        except Exception:
            info["dominio"] = [str(v) for v in non_null.unique().to_list()]
    else:
        info["amostra"] = [str(v) for v in non_null.head(3).to_list()]

    return info


def check_grain(df: pl.DataFrame, keys: list[str]) -> dict | None:
    if not all(k in df.columns for k in keys):
        return None
    total = df.height
    distintos = df.select(keys).unique().height
    return {
        "chave": " + ".join(keys),
        "linhas": total,
        "combinacoes_distintas": distintos,
        "unico": distintos == total,
        "duplicadas": total - distintos,
    }


# Graos candidatos a testar
GRAIN_CANDIDATES = [
    ["NUNOTA", "SEQUENCIA"],
    ["NUNOTA"],
    ["CODVEND"],
    ["CODPROD", "CODEMP", "CODLOCAL", "DTATUAL"],
    ["CODPROD", "DTATUAL"],
    ["ANO", "MES", "TIPO", "COD_CLA"],
    ["ANO", "MES", "DESCRICAO"],
    ["ANO", "MES"],
    ["CHAVECTE"],
    ["MES_ANO"],
]


def main() -> int:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in INPUT_DIR.glob("*.xlsx") if not p.name.startswith("~$"))
    if not files:
        print(f"ERRO: nenhum .xlsx em {INPUT_DIR}", file=sys.stderr)
        return 1

    report: dict = {
        "gerado_em": datetime.now(UTC).isoformat(),
        "input_dir": str(INPUT_DIR),
        "arquivos": [],
    }

    for path in files:
        print(f"\n>>> {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
        entry: dict = {
            "arquivo": path.name,
            "tamanho_bytes": path.stat().st_size,
            "sha256": file_hash(path),
            "abas": [],
        }
        try:
            sheets = list_sheets(path)
        except Exception as exc:  # noqa: BLE001
            entry["erro"] = f"falha ao abrir: {exc}"
            report["arquivos"].append(entry)
            print(f"    ERRO: {exc}")
            continue

        entry["abas_encontradas"] = sheets
        for sheet in sheets:
            print(f"    aba: {sheet} ...", end=" ", flush=True)
            try:
                df = read_sheet(path, sheet)
            except Exception as exc:  # noqa: BLE001
                entry["abas"].append({"aba": sheet, "erro": str(exc)})
                print(f"ERRO {exc}")
                continue

            sheet_info: dict = {
                "aba": sheet,
                "linhas": df.height,
                "colunas": df.width,
                "nomes_colunas": df.columns,
                "perfil_colunas": [profile_column(df, c) for c in df.columns],
                "graos_testados": [],
            }
            for keys in GRAIN_CANDIDATES:
                g = check_grain(df, keys)
                if g:
                    sheet_info["graos_testados"].append(g)

            entry["abas"].append(sheet_info)
            print(f"{df.height} linhas x {df.width} colunas")

        report["arquivos"].append(entry)

    out_json = ARTIFACTS_DIR / "profile.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {out_json}")

    render_markdown(report, DOCS_DIR / "source_profile.md")
    print(f"MD:   {DOCS_DIR / 'source_profile.md'}")
    return 0


def _fmt_int(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def render_markdown(report: dict, out: Path) -> None:
    L: list[str] = []
    L.append("# Perfil Real das Fontes (`docs/source_profile.md`)\n")
    L.append("> Gerado automaticamente por `scripts/profile_sources.py`.")
    L.append("> **Evidência > suposição**: este documento reflete a leitura real dos arquivos,")
    L.append("> não o que a especificação técnica presume.\n")
    L.append(f"- Gerado em: `{report['gerado_em']}`")
    L.append(f"- Diretório: `{report['input_dir']}`")
    L.append(f"- Arquivos analisados: **{len(report['arquivos'])}**\n")
    L.append("---\n")

    L.append("## Sumário\n")
    L.append("| Arquivo | Abas | Total linhas |")
    L.append("|---|---|---|")
    for f in report["arquivos"]:
        abas = len(f.get("abas", []))
        tot = sum(a.get("linhas", 0) for a in f.get("abas", []))
        L.append(f"| `{f['arquivo']}` | {abas} | {_fmt_int(tot)} |")
    L.append("")
    L.append("---\n")

    for f in report["arquivos"]:
        L.append(f"## Arquivo: `{f['arquivo']}`\n")
        L.append(f"- Tamanho: {f['tamanho_bytes'] / 1024 / 1024:.2f} MB")
        L.append(f"- SHA-256: `{f['sha256']}`")
        abas_txt = ", ".join(repr(s) for s in f.get("abas_encontradas", []))
        L.append(f"- Abas encontradas: {abas_txt}\n")
        if "erro" in f:
            L.append(f"> **ERRO:** {f['erro']}\n")
            continue

        for a in f.get("abas", []):
            L.append(f"### Aba: `{a['aba']}`\n")
            if "erro" in a:
                L.append(f"> **ERRO:** {a['erro']}\n")
                continue
            L.append(f"**{_fmt_int(a['linhas'])} linhas x {a['colunas']} colunas**\n")

            graos = list(a.get("graos_testados", []))
            if graos:
                L.append("#### Teste de grão\n")
                L.append("| Chave candidata | Linhas | Distintas | Único? | Duplicadas |")
                L.append("|---|---|---|---|---|")
                for g in graos:
                    mark = "SIM" if g["unico"] else "**NAO**"
                    L.append(
                        f"| `{g['chave']}` | {_fmt_int(g['linhas'])} "
                        f"| {_fmt_int(g['combinacoes_distintas'])} "
                        f"| {mark} | {_fmt_int(g['duplicadas'])} |"
                    )
                L.append("")

            L.append("#### Colunas\n")
            L.append("| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |")
            L.append("|---|---|---|---|---|---|---|---|")
            for i, c in enumerate(a["perfil_colunas"], 1):
                dom = c.get("dominio")
                if dom is not None:
                    dom_txt = ", ".join(f"`{d}`" for d in dom[:MAX_DISTINCT_SHOWN])
                else:
                    dom_txt = ", ".join(f"`{d}`" for d in c.get("amostra", []))
                dom_txt = dom_txt.replace("|", "\\|")[:220]
                mn = c.get("min", "")
                mx = c.get("max", "")
                if isinstance(mn, float):
                    mn = f"{mn:,.2f}".replace(",", ".")
                if isinstance(mx, float):
                    mx = f"{mx:,.2f}".replace(",", ".")
                L.append(
                    f"| {i} | `{c['coluna']}` | {c['dtype']} | {c['pct_nulo']}% | "
                    f"{_fmt_int(c['distintos'])} | {dom_txt} | {mn} | {mx} |"
                )
            L.append("")

            neg = [c for c in a["perfil_colunas"] if c.get("negativos", 0) > 0]
            if neg:
                L.append("#### Colunas com valores negativos (indício de devolução/estorno)\n")
                for c in neg:
                    L.append(f"- `{c['coluna']}`: {_fmt_int(c['negativos'])} negativos")
                L.append("")
        L.append("---\n")

    out.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
