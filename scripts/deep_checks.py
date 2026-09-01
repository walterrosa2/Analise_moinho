"""
Fase 0 - Verificacoes cruzadas que decidem regras de modelagem.

Responde, com dados reais, perguntas que a especificacao deixa em aberto:
  1. TIPMOV 'D' implica sempre valores negativos?
  2. Quantos CODVEND das vendas existem no cadastro? Qual o TipoVend deles?
  3. As chaves NF-e do CT-e encontram as vendas?
  4. VLRNOTA se repete mesmo entre os itens (justificando a proibicao de somar)?
  5. Cobertura do as-of join de custos (produtos vendidos sem custo).
  6. Positivados: a explosao de PARC_POSITIVADOS bate com QTD_POSITIVADOS?

Saida: artifacts/deep_checks.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import fastexcel
import polars as pl

# Console Windows costuma ser cp1252: evita UnicodeEncodeError nos relatorios
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "input"
OUT = ROOT / "artifacts" / "deep_checks.md"

VENDAS_FILE = INPUT / "VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx"
CTE_FILE = INPUT / "CTE Venda 012023 - 072026 V1.xlsx"
POSITIVADOS_FILE = INPUT / "POSITIVADOS V1.xlsx"
REGIAO_FILE = INPUT / "REGIÃO COMERCIAL POR REPRESENTANTE -SANATHIELLE.xlsx"

L: list[str] = []


def say(line: str = "") -> None:
    print(line)
    L.append(line)


def read(path: Path, sheet: str) -> pl.DataFrame:
    return fastexcel.read_excel(str(path)).load_sheet_by_name(sheet).to_polars()


def clean(s: pl.Expr) -> pl.Expr:
    """Trim + 'NULL' textual vira null."""
    return (
        s.cast(pl.Utf8)
        .str.strip_chars()
        .replace({"NULL": None, "": None, "null": None})
    )


def main() -> None:
    say("# Verificações Cruzadas (Fase 0)\n")
    say("> Gerado por `scripts/deep_checks.py`. Cada resposta abaixo determina")
    say("> uma decisão de modelagem registrada em `docs/business_rules.md`.\n")

    say("## 1. Base de vendas — carregando...\n")
    vendas = read(VENDAS_FILE, "Dados Vend_Dev 012023-072026")
    say(f"- Linhas: **{vendas.height:,}** | Colunas: **{vendas.width}**".replace(",", "."))

    # ---------------- 1. TIPMOV x sinal ----------------
    say("\n## 1. `TIPMOV` × sinal das medidas\n")
    tm = (
        vendas.group_by("TIPMOV")
        .agg(
            pl.len().alias("linhas"),
            (pl.col("VLRTOT") < 0).sum().alias("vlrtot_negativo"),
            (pl.col("VLRTOT") > 0).sum().alias("vlrtot_positivo"),
            (pl.col("TONLIQ") < 0).sum().alias("tonliq_negativo"),
            pl.col("VLRTOT").sum().alias("soma_vlrtot"),
            pl.col("TONLIQ").sum().alias("soma_tonliq"),
        )
        .sort("TIPMOV")
    )
    say("| TIPMOV | Linhas | VLRTOT<0 | VLRTOT>0 | TONLIQ<0 | Σ VLRTOT | Σ TONLIQ |")
    say("|---|---|---|---|---|---|---|")
    for r in tm.iter_rows(named=True):
        say(
            f"| `{r['TIPMOV']}` | {r['linhas']:,} | {r['vlrtot_negativo']:,} | "
            f"{r['vlrtot_positivo']:,} | {r['tonliq_negativo']:,} | "
            f"{r['soma_vlrtot']:,.2f} | {r['soma_tonliq']:,.3f} |".replace(",", ".")
        )

    # Operacoes por TIPMOV
    say("\n### Operações (`CODTIPOPER` / `DESCROPER`) por TIPMOV\n")
    ops = (
        vendas.group_by(["TIPMOV", "CODTIPOPER", "DESCROPER"])
        .agg(pl.len().alias("linhas"), pl.col("VLRTOT").sum().alias("vlrtot"))
        .sort(["TIPMOV", "linhas"], descending=[False, True])
    )
    say("| TIPMOV | CODTIPOPER | DESCROPER | Linhas | Σ VLRTOT |")
    say("|---|---|---|---|---|")
    for r in ops.iter_rows(named=True):
        desc = str(r["DESCROPER"]).strip()
        say(
            f"| {r['TIPMOV']} | {r['CODTIPOPER']:.0f} | {desc} | "
            f"{r['linhas']:,} | {r['vlrtot']:,.2f} |".replace(",", ".")
        )

    # ---------------- 2. CIF_FOB ----------------
    say("\n## 2. `CIF_FOB` — domínio inconsistente\n")
    cf = (
        vendas.group_by("CIF_FOB")
        .agg(pl.len().alias("linhas"))
        .sort("linhas", descending=True)
    )
    say("| Valor bruto | Linhas |")
    say("|---|---|")
    for r in cf.iter_rows(named=True):
        say(f"| `{r['CIF_FOB']}` | {r['linhas']:,} |".replace(",", "."))
    say("\n> Necessária normalização para `C` / `F` / `R` / `S` / `T`"
        " (a primeira letra é o código; o restante é descrição).")

    # ---------------- 3. VLRNOTA repetido ----------------
    say("\n## 3. `VLRNOTA` no grão de item (por que é proibido somar)\n")
    por_nota = vendas.group_by("NUNOTA").agg(
        pl.len().alias("itens"),
        pl.col("VLRNOTA").n_unique().alias("vlrnota_distintos"),
        pl.col("VLRNOTA").first().alias("vlrnota"),
        pl.col("VLRTOT").sum().alias("soma_itens"),
    )
    multi = por_nota.filter(pl.col("itens") > 1)
    say(f"- Notas com mais de 1 item: **{multi.height:,}** de {por_nota.height:,}".replace(",", "."))
    say(f"- Notas em que `VLRNOTA` varia entre os itens: "
        f"**{por_nota.filter(pl.col('vlrnota_distintos') > 1).height:,}**".replace(",", "."))
    soma_item = float(vendas["VLRTOT"].sum())
    soma_doc_errada = float(vendas["VLRNOTA"].sum())
    soma_doc_certa = float(por_nota["vlrnota"].sum())
    say(f"- Σ `VLRTOT` (itens, CORRETO): **R$ {soma_item:,.2f}**".replace(",", "."))
    say(f"- Σ `VLRNOTA` no grão de item (ERRADO): **R$ {soma_doc_errada:,.2f}**".replace(",", "."))
    say(f"- Σ `VLRNOTA` deduplicado por NUNOTA: **R$ {soma_doc_certa:,.2f}**".replace(",", "."))
    if soma_item:
        infl = 100 * (soma_doc_errada / soma_item - 1)
        say(f"- **Inflação se somar VLRNOTA por item: {infl:,.1f}%**".replace(",", "."))

    # VLRFRETE_ORDEMCARGA
    say("\n### `VLRFRETE_ORDEMCARGA` no grão de item\n")
    frete_item = float(vendas["VLRFRETE_ORDEMCARGA"].fill_null(0).sum())
    frete_ordem = float(
        vendas.filter(pl.col("ORDEMCARGA").is_not_null() & (pl.col("ORDEMCARGA") != 0))
        .group_by("ORDEMCARGA")
        .agg(pl.col("VLRFRETE_ORDEMCARGA").first().alias("v"))["v"]
        .fill_null(0)
        .sum()
    )
    say(f"- Σ por item (ERRADO): **R$ {frete_item:,.2f}**".replace(",", "."))
    say(f"- Σ deduplicado por ORDEMCARGA: **R$ {frete_ordem:,.2f}**".replace(",", "."))
    if frete_ordem:
        say(f"- **Inflação: {100 * (frete_item / frete_ordem - 1):,.1f}%**".replace(",", "."))

    # ---------------- 4. Vendedores ----------------
    say("\n## 4. Vendedores: cadastro × movimento\n")
    vend_cad = read(VENDAS_FILE, "Vendedor_Supervisor")
    cad_cods = set(
        vend_cad.select(clean(pl.col("CODVEND")).alias("c"))["c"]
        .drop_nulls()
        .cast(pl.Float64, strict=False)
        .cast(pl.Int64, strict=False)
        .to_list()
    )
    mov = (
        vendas.group_by("CODVEND")
        .agg(
            pl.len().alias("linhas"),
            pl.col("VLRTOT").sum().alias("receita"),
            pl.col("TONLIQ").sum().alias("toneladas"),
            pl.col("CODPARC").n_unique().alias("clientes"),
        )
        .sort("receita", descending=True)
    )
    mov_cods = {int(c) for c in mov["CODVEND"].drop_nulls().to_list()}
    say(f"- Cadastro (`Vendedor_Supervisor`): **{len(cad_cods)}** códigos")
    say(f"- Com movimento na base de vendas: **{len(mov_cods)}** códigos")
    say(f"- Movimentam mas NÃO estão no cadastro: **{sorted(mov_cods - cad_cods)}**")
    say(f"- Cadastrados sem nenhuma venda: **{len(cad_cods - mov_cods)}**")

    cad_idx = vend_cad.select(
        clean(pl.col("CODVEND")).cast(pl.Float64, strict=False).cast(pl.Int64).alias("CODVEND"),
        clean(pl.col("APELIDO_VENDEDOR")).alias("apelido"),
        clean(pl.col("TipoVend")).alias("tipo"),
        clean(pl.col("VENDEDOR_ATIVO")).alias("ativo"),
    )
    top = (
        mov.with_columns(pl.col("CODVEND").cast(pl.Int64))
        .join(cad_idx, on="CODVEND", how="left")
    )
    total_rec = float(vendas["VLRTOT"].sum())
    say("\n### Todos os vendedores com movimento (ordenados por receita)\n")
    say("| CODVEND | Apelido | TipoVend | Ativo | Linhas | Receita | % | Clientes | Toneladas |")
    say("|---|---|---|---|---|---|---|---|---|")
    for r in top.iter_rows(named=True):
        pct = 100 * r["receita"] / total_rec if total_rec else 0
        say(
            f"| {r['CODVEND']} | {r['apelido'] or '—'} | {r['tipo'] or '—'} | "
            f"{r['ativo'] or '—'} | {r['linhas']:,} | {r['receita']:,.2f} | {pct:.2f}% | "
            f"{r['clientes']:,} | {r['toneladas']:,.1f} |".replace(",", ".")
        )

    # Supervisores
    say("\n### `CODSUPERVISOR`\n")
    sup = vendas.group_by("CODSUPERVISOR").agg(
        pl.len().alias("linhas"), pl.col("VLRTOT").sum().alias("receita")
    ).sort("receita", descending=True)
    say("| CODSUPERVISOR | Linhas | Receita |")
    say("|---|---|---|")
    for r in sup.iter_rows(named=True):
        cod = r["CODSUPERVISOR"]
        cod_txt = f"{cod:.0f}" if cod is not None else "NULO"
        say(f"| {cod_txt} | {r['linhas']:,} | {r['receita']:,.2f} |".replace(",", "."))

    # ---------------- 5. Custos: cobertura ----------------
    say("\n## 5. Custos PA — cobertura dos produtos vendidos\n")
    custos = read(VENDAS_FILE, "Custos PA 012023 - 072026")
    prod_venda = set(vendas["CODPROD"].drop_nulls().cast(pl.Int64).to_list())
    prod_custo = set(custos["CODPROD"].drop_nulls().cast(pl.Int64).to_list())
    sem_custo = prod_venda - prod_custo
    say(f"- Produtos distintos vendidos: **{len(prod_venda)}**")
    say(f"- Produtos distintos na tabela de custo: **{len(prod_custo)}**")
    say(f"- Vendidos SEM nenhum custo cadastrado: **{len(sem_custo)}** → {sorted(sem_custo)}")
    if sem_custo:
        linhas_sem = vendas.filter(pl.col("CODPROD").cast(pl.Int64).is_in(list(sem_custo)))
        say(f"- Linhas de venda afetadas: **{linhas_sem.height:,}** "
            f"({100 * linhas_sem.height / vendas.height:.2f}% do total)".replace(",", "."))

    say("\n### Datas de custo (`DTATUAL`)\n")
    dt = custos.select(pl.col("DTATUAL"))
    say(f"- Tipo lido: `{dt.dtypes[0]}`")
    say(f"- Amostra: {custos['DTATUAL'].drop_nulls().head(3).to_list()}")
    say(f"- Datas distintas: **{custos['DTATUAL'].n_unique():,}**".replace(",", "."))
    say(f"- CODEMP na tabela de custo: {sorted(custos['CODEMP'].unique().to_list())}")
    say(f"- CODLOCAL na tabela de custo: {sorted(custos['CODLOCAL'].unique().to_list())}")
    say(f"- CODLOCALORIG nas vendas: "
        f"{sorted(vendas['CODLOCALORIG'].drop_nulls().unique().cast(pl.Utf8).to_list())}")

    # ---------------- 6. CT-e x NF-e ----------------
    say("\n## 6. CT-e × NF-e (bridge)\n")
    cte = read(CTE_FILE, "CTE Venda 012023 - 072026")
    cte = cte.with_columns(
        clean(pl.col("CHAVES_NFE_VENDA")).alias("chaves"),
        clean(pl.col("NOTAS_VENDA")).alias("notas"),
        clean(pl.col("ORDEMCARGA")).alias("oc"),
    )
    sem_chave = cte.filter(pl.col("chaves").is_null()).height
    say(f"- Linhas de CT-e: **{cte.height:,}**".replace(",", "."))
    say(f"- Sem `CHAVES_NFE_VENDA`: **{sem_chave:,}** "
        f"({100 * sem_chave / cte.height:.2f}%)".replace(",", "."))
    sem_oc = cte.filter(pl.col("oc").is_null() | (pl.col("oc") == "0")).height
    say(f"- Sem `ORDEMCARGA` válida (nulo ou 0): **{sem_oc:,}** "
        f"({100 * sem_oc / cte.height:.2f}%)".replace(",", "."))

    exploded = (
        cte.filter(pl.col("chaves").is_not_null())
        .with_columns(pl.col("chaves").str.split(";").alias("lista"))
        .explode("lista")
        .with_columns(pl.col("lista").str.strip_chars().alias("chave_nfe"))
        .filter(pl.col("chave_nfe").str.len_chars() > 0)
    )
    say(f"- Vínculos CT-e→NF-e após explosão por `;`: **{exploded.height:,}**".replace(",", "."))
    nfe_venda = set(
        vendas.select(clean(pl.col("CHAVENFE")).alias("k"))["k"].drop_nulls().to_list()
    )
    nfe_cte = set(exploded["chave_nfe"].drop_nulls().to_list())
    achou = nfe_cte & nfe_venda
    say(f"- Chaves NF-e distintas citadas nos CT-e: **{len(nfe_cte):,}**".replace(",", "."))
    say(f"- Dessas, encontradas na base de vendas: **{len(achou):,}** "
        f"({100 * len(achou) / len(nfe_cte):.2f}%)".replace(",", "."))
    say(f"- Não encontradas: **{len(nfe_cte - achou):,}**".replace(",", "."))
    amostra_nao = sorted(nfe_cte - achou)[:3]
    if amostra_nao:
        say(f"- Amostra não encontrada: {amostra_nao}")

    say("\n### Operações de CT-e\n")
    ops_cte = (
        cte.group_by(["CODTIPOPER", "DESCROPER"]).agg(pl.len().alias("linhas")).sort("linhas", descending=True)
    )
    say("| CODTIPOPER | DESCROPER | Linhas |")
    say("|---|---|---|")
    for r in ops_cte.iter_rows(named=True):
        say(f"| {r['CODTIPOPER']} | {str(r['DESCROPER']).strip()} | {r['linhas']:,} |".replace(",", "."))

    # ---------------- 7. Positivados ----------------
    say("\n## 7. Positivados — explosão de `PARC_POSITIVADOS`\n")
    pos = read(POSITIVADOS_FILE, "parceiros positivados ")
    pos = pos.with_columns(
        pl.col("ANO").cast(pl.Int64),
        pl.col("MES").cast(pl.Int64),
        pl.col("QTD_POSITIVADOS").cast(pl.Int64),
        clean(pl.col("PARC_POSITIVADOS")).alias("lista"),
    ).with_columns(
        pl.col("lista")
        .str.split(",")
        .list.eval(pl.element().str.strip_chars().filter(pl.element().str.len_chars() > 0))
        .list.len()
        .alias("qtd_explodido")
    )
    div = pos.filter(pl.col("QTD_POSITIVADOS") != pl.col("qtd_explodido"))
    say(f"- Meses: **{pos.height}**")
    say(f"- Meses em que a explosão diverge de `QTD_POSITIVADOS`: **{div.height}**")
    if div.height:
        say("\n| ANO | MES | QTD declarado | QTD explodido | Diferença |")
        say("|---|---|---|---|---|")
        for r in div.iter_rows(named=True):
            say(f"| {r['ANO']} | {r['MES']} | {r['QTD_POSITIVADOS']} | "
                f"{r['qtd_explodido']} | {r['qtd_explodido'] - r['QTD_POSITIVADOS']} |")

    say("\n### Meses de implantação do ERP (fora do padrão)\n")
    say("| ANO | MES | QTD_POSITIVADOS |")
    say("|---|---|---|")
    for r in pos.sort(["ANO", "MES"]).head(8).iter_rows(named=True):
        say(f"| {r['ANO']} | {r['MES']} | {r['QTD_POSITIVADOS']} |")

    parc_pos = set(
        pos.with_columns(pl.col("lista").str.split(",").alias("l"))
        .explode("l")
        .with_columns(pl.col("l").str.strip_chars().alias("codparc"))
        .filter(pl.col("codparc").str.len_chars() > 0)["codparc"]
        .cast(pl.Int64, strict=False)
        .drop_nulls()
        .to_list()
    )
    parc_venda = set(vendas["CODPARC"].drop_nulls().cast(pl.Int64).to_list())
    say(f"\n- Clientes distintos positivados: **{len(parc_pos):,}**".replace(",", "."))
    say(f"- Presentes na base de vendas 2023+: **{len(parc_pos & parc_venda):,}** "
        f"({100 * len(parc_pos & parc_venda) / len(parc_pos):.1f}%)".replace(",", "."))
    say("> Positivados cobrem 2021+; a base de vendas começa em 2023. "
        "A diferença é esperada, não é erro.")

    # ---------------- 8. Regiao comercial ----------------
    say("\n## 8. Região comercial por representante (arquivo extra, fora da especificação)\n")
    reg = read(REGIAO_FILE, "REPRESENTANTE")
    reg = reg.with_columns(
        pl.col("CÓDIGO-REPRESENTANTE").cast(pl.Float64, strict=False).cast(pl.Int64, strict=False).alias("cod")
    )
    cods_reg = set(reg["cod"].drop_nulls().to_list())
    say(f"- Aba `REPRESENTANTE`: {reg.height} linhas, **{len(cods_reg)}** códigos de representante")
    say(f"- Códigos: {sorted(cods_reg)}")
    say(f"- Desses, com movimento nas vendas: **{len(cods_reg & mov_cods)}** → {sorted(cods_reg & mov_cods)}")
    say(f"- No arquivo mas sem venda: {sorted(cods_reg - mov_cods)}")
    say(f"- Vendem mas não estão nesse arquivo: {sorted(mov_cods - cods_reg)}")

    geral = read(REGIAO_FILE, "GERAL")
    say(f"\n- Aba `GERAL`: {geral.height} linhas — mapa CIDADE → REGIÃO COMERCIAL → REPRESENTANTE")
    regioes = (
        geral.select(clean(pl.col("REGIÃO COMERCIAL")).alias("r"))["r"].drop_nulls().unique().sort().to_list()
    )
    say(f"- Regiões comerciais nomeadas ({len(regioes)}): {regioes}")

    # ---------------- 9. Periodo ----------------
    say("\n## 9. Cobertura temporal real\n")
    dtneg = vendas["DTNEG"].drop_nulls()
    say(f"- `DTNEG` vendas: **{dtneg.min()}** a **{dtneg.max()}**")
    say("> A especificação declara 01/2023–07/2026; há registros anteriores a 2023 "
        "(a filtragem deve ser explícita, nunca silenciosa).")
    fora = vendas.filter(pl.col("DTNEG") < pl.datetime(2023, 1, 1))
    say(f"- Linhas com `DTNEG` < 2023-01-01: **{fora.height:,}**".replace(",", "."))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"\n>>> {OUT}")


if __name__ == "__main__":
    main()
