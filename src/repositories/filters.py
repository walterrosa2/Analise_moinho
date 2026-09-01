"""
Filtros globais compartilhados por todas as paginas.

Um unico objeto Filtros atravessa a aplicacao inteira, garantindo que dois
graficos lado a lado estejam sempre falando do mesmo recorte.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Filtros:
    """Recorte analitico ativo. Traduz-se em WHERE + parametros."""

    periodo_inicio: str | None = None   # 'YYYY-MM'
    periodo_fim: str | None = None
    empresas: list[int] = field(default_factory=list)
    classificacoes: list[str] = field(default_factory=list)
    produtos: list[int] = field(default_factory=list)
    ufs: list[str] = field(default_factory=list)
    regioes: list[int] = field(default_factory=list)
    vendedores: list[int] = field(default_factory=list)
    papeis: list[str] = field(default_factory=list)
    clientes: list[int] = field(default_factory=list)
    ramos: list[str] = field(default_factory=list)
    cif_fob: list[str] = field(default_factory=list)
    incluir_devolucoes: bool = True
    apenas_devolucoes: bool = False

    # Mapa campo logico -> coluna fisica. Cada consulta declara o que possui,
    # para que o mesmo filtro sirva a MVs com colunas diferentes.
    def where(self, colunas: dict[str, str]) -> tuple[str, dict[str, Any]]:
        """
        Monta o WHERE para as colunas disponiveis na consulta.

        `colunas` mapeia o nome logico do filtro para a coluna real, ex.:
            {"periodo": "ano_mes", "uf": "uf_cliente", "vendedor": "codvend"}
        Filtros sem coluna correspondente sao ignorados (nao quebram).
        """
        clausulas: list[str] = []
        params: dict[str, Any] = {}

        def add_in(chave: str, valores: list[Any], prefixo: str) -> None:
            col = colunas.get(chave)
            if col and valores:
                nomes = []
                for i, v in enumerate(valores):
                    p = f"{prefixo}{i}"
                    params[p] = v
                    nomes.append(f":{p}")
                clausulas.append(f"{col} IN ({', '.join(nomes)})")

        periodo = colunas.get("periodo")
        if periodo:
            if self.periodo_inicio:
                clausulas.append(f"{periodo} >= :periodo_inicio")
                params["periodo_inicio"] = self.periodo_inicio
            if self.periodo_fim:
                clausulas.append(f"{periodo} <= :periodo_fim")
                params["periodo_fim"] = self.periodo_fim

        add_in("empresa", self.empresas, "emp")
        add_in("classificacao", self.classificacoes, "cla")
        add_in("produto", self.produtos, "prod")
        add_in("uf", self.ufs, "uf")
        add_in("regiao", self.regioes, "reg")
        add_in("vendedor", self.vendedores, "vend")
        add_in("papel", self.papeis, "pap")
        add_in("cliente", self.clientes, "cli")
        add_in("ramo", self.ramos, "ram")
        add_in("cif_fob", self.cif_fob, "cf")

        dev = colunas.get("is_devolucao")
        if dev:
            if self.apenas_devolucoes:
                clausulas.append(f"{dev} = TRUE")
            elif not self.incluir_devolucoes:
                clausulas.append(f"{dev} = FALSE")

        return (" AND ".join(clausulas) if clausulas else "TRUE"), params

    def descricao(self) -> str:
        """Texto curto do recorte ativo, para carimbar exportacoes."""
        partes = []
        if self.periodo_inicio or self.periodo_fim:
            partes.append(f"{self.periodo_inicio or '...'} a {self.periodo_fim or '...'}")
        for rotulo, valores in (
            ("classificação", self.classificacoes),
            ("UF", self.ufs),
            ("vendedor", [str(v) for v in self.vendedores]),
            ("papel", self.papeis),
        ):
            if valores:
                partes.append(f"{rotulo}: {', '.join(map(str, valores[:3]))}"
                              + ("…" if len(valores) > 3 else ""))
        if self.apenas_devolucoes:
            partes.append("apenas devoluções")
        elif not self.incluir_devolucoes:
            partes.append("sem devoluções")
        return " | ".join(partes) or "sem filtros"

    def ativo(self) -> bool:
        return bool(
            self.periodo_inicio or self.periodo_fim or self.empresas or self.classificacoes
            or self.produtos or self.ufs or self.regioes or self.vendedores or self.papeis
            or self.clientes or self.ramos or self.cif_fob
            or self.apenas_devolucoes or not self.incluir_devolucoes
        )


# Mapas de coluna por fonte de dados (evita espalhar strings pelas paginas)
COLUNAS_VENDA_ITEM = {
    "periodo": "ano_mes",
    "empresa": "codemp",
    "classificacao": "classificacao",
    "produto": "codprod",
    "uf": "uf_cliente",
    "regiao": "codreg",
    "vendedor": "codvend",
    "papel": "papel_analitico",
    "cliente": "codparc",
    "ramo": "ramo_atividade",
    "cif_fob": "cif_fob",
    "is_devolucao": "is_devolucao",
}

COLUNAS_MV_MES = {"periodo": "ano_mes"}

COLUNAS_MV_PRODUTO = {
    "periodo": "ano_mes",
    "classificacao": "classificacao",
    "produto": "codprod",
}

COLUNAS_MV_VENDEDOR = {
    "periodo": "ano_mes",
    "vendedor": "codvend",
    "papel": "papel_analitico",
}

COLUNAS_MV_REGIAO = {
    "periodo": "ano_mes",
    "uf": "uf_cliente",
    "regiao": "codreg",
}

COLUNAS_MV_CLIENTE = {
    "periodo": "ano_mes",
    "cliente": "codparc",
    "uf": "uf_cliente",
    "regiao": "codreg",
    "vendedor": "codvend",
    "ramo": "ramo_atividade",
}
