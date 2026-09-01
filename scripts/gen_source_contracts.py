"""
Gera config/sources/*.yaml a partir do perfil REAL das fontes.

As colunas obrigatorias vem de artifacts/profile.json (leitura real), nao da
especificacao. Assim o contrato nunca exige uma coluna que o arquivo nao tem
nem deixa passar uma coluna que sumiu.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "artifacts" / "profile.json"
OUT_DIR = ROOT / "config" / "sources"

# source_id -> (arquivo, aba, tabela raw, grao, ordem, obrigatorias, observacao)
SOURCES = [
    (
        "gestao_diaria_161",
        "161 - Gestão Diária Comercial V1.xlsx",
        "Planilha1",
        "gestao_diaria_161",
        ["ANO", "MES", "TIPO", "COD_CLA"],
        10,
        ["ANO", "MES", "TIPO", "COD_CLA", "DESC_CLA", "VALOR", "TONELADA"],
        "Camada gerencial agregada. Usada para reconciliacao, nunca como base causal.",
    ),
    (
        "gestao_diaria_outros",
        "161 - Gestão Diária Comercial (OUTROS) V1.xlsx",
        "Planilha1",
        "gestao_diaria_outros",
        ["ANO", "MES", "DESCRICAO"],
        11,
        ["ANO", "MES", "DESCRICAO", "ATUAL"],
        "Despesas comerciais mensais. Semantica de ORC/ANT pendente (Q-03).",
    ),
    (
        "vendas_dev",
        "VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx",
        "Dados Vend_Dev 012023-072026",
        "vendas_dev",
        ["NUNOTA", "SEQUENCIA"],
        1,
        [
            "NUNOTA", "SEQUENCIA", "CODEMP", "CODPROD", "CODPARC", "CODVEND",
            "DTNEG", "DTFATUR", "TIPMOV", "CODTIPOPER", "VLRTOT", "TONLIQ",
            "VLRNOTA", "CHAVENFE",
        ],
        "Fonte principal da plataforma. Grao NUNOTA+SEQUENCIA confirmado unico.",
    ),
    (
        "vendedores",
        "VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx",
        "Vendedor_Supervisor",
        "vendedores",
        ["CODVEND"],
        3,
        ["CODVEND", "APELIDO_VENDEDOR", "TipoVend", "VENDEDOR_ATIVO"],
        "Cadastro historico: 458 codigos, apenas 34 com movimento.",
    ),
    (
        "custos_pa",
        "VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx",
        "Custos PA 012023 - 072026",
        "custos_pa",
        ["CODPROD", "CODEMP", "CODLOCAL", "DTATUAL"],
        4,
        [
            "CODPROD", "PRODUTO", "CODGRUPOPROD", "GRUPO_PRODUTO", "CODEMP",
            "CODLOCAL", "DTATUAL", "CUSMED", "CUSMEDICM", "CUSSEMICM",
            "CUSREP", "CUSGER", "CUSVARIAVEL",
        ],
        "Seis conceitos de custo. Nenhum e oficial ate homologacao (Q-04).",
    ),
    (
        "cte",
        "CTE Venda 012023 - 072026 V1.xlsx",
        "CTE Venda 012023 - 072026",
        "cte",
        None,
        6,
        ["CODEMP", "NUNOTA", "CHAVECTE", "CODPARC", "VLRNOTA", "CHAVES_NFE_VENDA"],
        "CHAVECTE repete 1.133x: PK e surrogate frete_id. ORDEMCARGA invalida em 55,89%.",
    ),
    (
        "positivados_mensal",
        "POSITIVADOS V1.xlsx",
        "parceiros positivados ",
        "positivados_mensal",
        ["ANO", "MES"],
        7,
        ["ANO", "MES", "QTD_POSITIVADOS", "PARC_POSITIVADOS"],
        "PARC_POSITIVADOS e lista separada por virgula. Explosao bate 100% com QTD.",
    ),
    (
        "trigo_compra",
        "Relatorio Compra de Trigo - Max.xlsx",
        "Compra",
        "trigo_compra",
        None,
        8,
        [],
        "Cabecalho de duas linhas com celulas mescladas: parser posicional dedicado.",
    ),
    (
        "trigo_estoque",
        "Relatorio Compra de Trigo - Max.xlsx",
        "Estoque",
        "trigo_estoque",
        None,
        9,
        [],
        "Idem. Periodo real: Jan/25 a Jul/26.",
    ),
    (
        "regiao_comercial",
        "REGIÃO COMERCIAL POR REPRESENTANTE -SANATHIELLE.xlsx",
        "GERAL",
        "regiao_comercial_geral",
        None,
        12,
        ["CIDADE"],
        "Fonte adicional (fora da especificacao): mapa cidade -> regiao comercial -> representante.",
    ),
    (
        "regiao_representante",
        "REGIÃO COMERCIAL POR REPRESENTANTE -SANATHIELLE.xlsx",
        "REPRESENTANTE",
        "regiao_representante",
        None,
        13,
        ["CIDADE", "CÓDIGO-REPRESENTANTE"],
        "Traz CODIGO-REPRESENTANTE, que liga a dim_vendedor.",
    ),
    (
        "catalogo_fontes",
        "Inventário de Dados relatórios Sankhya e outros - Sanathielle.xlsx",
        "Sankhya",
        "catalogo_fontes",
        None,
        14,
        ["FONTE", "LOCALIZAÇÃO"],
        "Catalogo/backlog. NAO e fato transacional.",
    ),
    (
        "catalogo_fontes_externas",
        "Inventário de Dados relatórios Sankhya e outros - Sanathielle.xlsx",
        "Outras fontes",
        "catalogo_fontes_externas",
        None,
        15,
        ["FONTE", "LOCALIZAÇÃO"],
        "Fontes externas (CONAB, Safras, Infoprice...). A coluna de credenciais e BLOQUEADA na leitura.",
    ),
]

# Colunas que NUNCA sao lidas, em nenhuma camada (contem credenciais em claro)
COLUNAS_PROIBIDAS = ["Login e Senha", "LOGIN E SENHA", "SENHA", "Senha", "PASSWORD"]


def yaml_list(items: list[str], indent: int = 2) -> str:
    if not items:
        return " []"
    pad = " " * indent
    return "\n" + "\n".join(f'{pad}- "{i}"' for i in items)


def main() -> int:
    if not PROFILE.exists():
        print(f"ERRO: rode scripts/profile_sources.py antes ({PROFILE} nao existe)")
        return 1

    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], dict] = {}
    for f in profile["arquivos"]:
        for a in f.get("abas", []):
            index[(f["arquivo"], a["aba"])] = {"file": f, "sheet": a}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gerados = 0

    for sid, filename, sheet, raw_table, grain, order, required, obs in SOURCES:
        key = (filename, sheet)
        if key not in index:
            print(f"AVISO: {sid}: aba '{sheet}' nao encontrada em '{filename}' — pulando")
            continue
        info = index[key]
        cols = [c for c in info["sheet"]["nomes_colunas"] if c not in COLUNAS_PROIBIDAS]
        excluidas = [c for c in info["sheet"]["nomes_colunas"] if c in COLUNAS_PROIBIDAS]

        pattern = filename.split(" 0")[0].split(" V1")[0]
        lines = [
            f"# Contrato de dados: {sid}",
            "# Gerado por scripts/gen_source_contracts.py a partir da leitura REAL do arquivo.",
            "# Se uma coluna obrigatoria faltar, a carga FALHA de forma visivel (nunca silenciosa).",
            "",
            f"source_id: {sid}",
            f"load_order: {order}",
            f'filename: "{filename}"',
            f'filename_pattern: "{pattern}*.xlsx"',
            f'sheet: "{sheet}"',
            f"raw_table: {raw_table}",
            f'descricao: >-\n  {obs}',
            "",
            f"# Perfil observado em {profile['gerado_em'][:10]}",
            "perfil_observado:",
            f"  linhas: {info['sheet']['linhas']}",
            f"  colunas: {info['sheet']['colunas']}",
            f"  sha256_arquivo: \"{info['file']['sha256']}\"",
            "",
        ]

        if grain:
            lines += ["grain:" + yaml_list(grain), ""]
        else:
            lines += [
                "# Sem grao unico verificado nesta fonte (ver docs/source_profile.md)",
                "grain: []",
                "",
            ]

        lines += ["required_columns:" + yaml_list(required), ""]
        lines += ["all_columns:" + yaml_list(cols), ""]

        if excluidas:
            lines += [
                "# SEGURANCA: colunas que a plataforma se recusa a ler (credenciais em claro).",
                "# Nao entram nem na camada RAW. Ver docs/decisions.md (ADR-005).",
                "colunas_proibidas:" + yaml_list(excluidas),
                "",
            ]

        out = OUT_DIR / f"{sid}.yaml"
        out.write_text("\n".join(lines), encoding="utf-8")
        marca = f"  [!] {len(excluidas)} coluna(s) bloqueada(s)" if excluidas else ""
        print(f"OK  {out.name}  ({len(cols)} colunas){marca}")
        gerados += 1

    print(f"\n{gerados} contratos gerados em {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
