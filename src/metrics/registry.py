"""
Registro central de metricas.

Regra (especificacao secao 16): nenhuma formula vive dentro de uma pagina
Streamlit. Toda metrica e declarada aqui com id, rotulo, unidade, grao,
formula SQL, fonte, status e regra de sinal — e a interface exibe isso ao
consultor, para que nenhum numero apareca sem origem.

Status:
    PROVISIONAL  - calculada, ainda nao confrontada com fonte gerencial
    RECONCILIADA - confrontada e dentro da tolerancia
    HOMOLOGADA   - validada pelo negocio (nenhuma esta, ainda)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    PROVISIONAL = "PROVISIONAL"
    RECONCILIADA = "RECONCILIADA"
    HOMOLOGADA = "HOMOLOGADA"


class Unidade(str, Enum):
    MOEDA = "R$"
    TONELADA = "t"
    MOEDA_POR_TON = "R$/t"
    PERCENTUAL = "%"
    CONTAGEM = "un"
    DIAS = "dias"


@dataclass(frozen=True)
class Metrica:
    id: str
    label: str
    descricao: str
    unidade: Unidade
    grao: str
    formula: str
    fonte: str
    status: Status = Status.PROVISIONAL
    regra_sinal: str = ""
    regra_filtro: str = ""
    observacoes: str = ""
    homologado_em: str | None = None
    categoria: str = "COMERCIAL"
    # Expressao SQL sobre as materialized views (usada pelo Explorador)
    sql_expr: str = ""
    # Metricas derivadas dependem de outras
    depende_de: tuple[str, ...] = field(default_factory=tuple)

    @property
    def rotulo_completo(self) -> str:
        return f"{self.label} ({self.unidade.value})"


# =====================================================================
# COMERCIAIS
# =====================================================================

_METRICAS: list[Metrica] = [
    Metrica(
        id="receita_liquida",
        label="Receita líquida",
        descricao="Soma de VLRTOT dos itens. Devoluções já vêm negativas da origem "
                  "e são abatidas naturalmente.",
        unidade=Unidade.MOEDA,
        grao="item (NUNOTA+SEQUENCIA)",
        formula="SUM(vlrtot)",
        sql_expr="SUM(receita_liquida)",
        fonte="analytics.fact_venda_item",
        status=Status.RECONCILIADA,
        regra_sinal="Devolução negativa preservada — nunca usar ABS (RN-03).",
        observacoes="Reconciliada com 161 REAL.-DEVOLUÇÃO: 43/43 meses dentro de 0,5%, "
                    "divergência média 0,053%.",
    ),
    Metrica(
        id="vendas_brutas",
        label="Vendas brutas",
        descricao="Receita sem considerar devoluções.",
        unidade=Unidade.MOEDA,
        grao="item",
        formula="SUM(vlrtot) WHERE NOT is_devolucao",
        sql_expr="SUM(vendas_brutas)",
        fonte="analytics.fact_venda_item",
        status=Status.RECONCILIADA,
        observacoes="Equivale ao TIPO='REALIZADO' do 161 (confirmado numericamente).",
    ),
    Metrica(
        id="devolucoes",
        label="Devoluções",
        descricao="Valor devolvido no período (negativo).",
        unidade=Unidade.MOEDA,
        grao="item",
        formula="SUM(vlrtot) WHERE is_devolucao",
        sql_expr="SUM(devolucoes)",
        fonte="analytics.fact_venda_item",
        status=Status.RECONCILIADA,
        regra_sinal="Exibida como valor negativo, como está na origem.",
    ),
    Metrica(
        id="taxa_devolucao",
        label="Taxa de devolução",
        descricao="Devolução sobre venda bruta.",
        unidade=Unidade.PERCENTUAL,
        grao="agregado",
        formula="-SUM(devolucoes) / NULLIF(SUM(vendas_brutas), 0) * 100",
        sql_expr="-SUM(devolucoes) / NULLIF(SUM(vendas_brutas), 0) * 100",
        fonte="analytics.mv_sales_month",
        depende_de=("devolucoes", "vendas_brutas"),
    ),
    Metrica(
        id="volume_liquido_t",
        label="Volume líquido",
        descricao="Tonelagem líquida (TONLIQ), já abatida de devoluções.",
        unidade=Unidade.TONELADA,
        grao="item",
        formula="SUM(tonliq)",
        sql_expr="SUM(ton_liquida)",
        fonte="analytics.fact_venda_item",
        status=Status.RECONCILIADA,
        regra_sinal="Devolução negativa preservada.",
    ),
    Metrica(
        id="pmv",
        label="PMV — preço médio de venda",
        descricao="Receita dividida pela tonelagem, EXCLUINDO operações sem receita "
                  "(bonificação, amostra, doação), que têm tonelada e valor zero.",
        unidade=Unidade.MOEDA_POR_TON,
        grao="agregado",
        formula="SUM(vlrtot) / SUM(tonliq), ambos filtrando CODTIPOPER NOT IN (3107, 3102)",
        sql_expr="SUM(receita_para_pmv) / NULLIF(SUM(ton_para_pmv), 0)",
        fonte="analytics.mv_sales_month",
        regra_filtro="Exclui 3107 SAIDA BONIFICAÇÃO e 3102 AMOSTRA/DOAÇÃO (RN-04, Q-11).",
        observacoes="Incluir as bonificações rebaixaria o preço médio artificialmente. "
                    "O comportamento é configurável em config/settings.yaml.",
        depende_de=("receita_liquida", "volume_liquido_t"),
    ),
    Metrica(
        id="desconto",
        label="Desconto concedido",
        descricao="Soma de VLRDESC dos itens.",
        unidade=Unidade.MOEDA,
        grao="item",
        formula="SUM(vlrdesc)",
        sql_expr="SUM(desconto)",
        fonte="analytics.fact_venda_item",
    ),
    Metrica(
        id="comissao",
        label="Comissão",
        descricao="Soma de VLRCOM dos itens.",
        unidade=Unidade.MOEDA,
        grao="item",
        formula="SUM(vlrcom)",
        sql_expr="SUM(comissao)",
        fonte="analytics.fact_venda_item",
        observacoes="Não reproduz o 'Vr Comissão' do 161 OUTROS (Q-13): o gerencial "
                    "parece usar comissão liberada, não a destacada na nota.",
    ),
    Metrica(
        id="clientes_ativos",
        label="Clientes ativos",
        descricao="Clientes distintos com movimento no período.",
        unidade=Unidade.CONTAGEM,
        grao="agregado",
        formula="COUNT(DISTINCT codparc)",
        sql_expr="COUNT(DISTINCT codparc)",
        fonte="analytics.fact_venda_item",
        categoria="CLIENTES",
    ),
    Metrica(
        id="clientes_novos",
        label="Clientes novos (positivados)",
        descricao="Clientes cuja PRIMEIRA compra ocorre no período.",
        unidade=Unidade.CONTAGEM,
        grao="mês",
        formula="COUNT(*) FROM fact_positivado",
        sql_expr="COUNT(DISTINCT codparc)",
        fonte="analytics.fact_positivado",
        status=Status.RECONCILIADA,
        observacoes="Verificado: 2.871 vínculos para 2.871 clientes distintos — "
                    "positivado é entrada, não recorrência (RN-15).",
        categoria="CLIENTES",
    ),
    Metrica(
        id="ticket_medio",
        label="Ticket médio por documento",
        descricao="Receita dividida pelo número de documentos.",
        unidade=Unidade.MOEDA,
        grao="agregado",
        formula="SUM(vlrtot) / COUNT(DISTINCT nunota)",
        sql_expr="SUM(receita_liquida) / NULLIF(SUM(documentos), 0)",
        fonte="analytics.mv_sales_month",
        depende_de=("receita_liquida",),
    ),
    Metrica(
        id="ton_por_cliente",
        label="Toneladas por cliente",
        descricao="Volume médio por cliente ativo.",
        unidade=Unidade.TONELADA,
        grao="agregado",
        formula="SUM(tonliq) / COUNT(DISTINCT codparc)",
        sql_expr="SUM(ton_liquida) / NULLIF(COUNT(DISTINCT codparc), 0)",
        fonte="analytics.mv_sales_customer_month",
        categoria="CLIENTES",
    ),
]

# =====================================================================
# CUSTOS — uma metrica por conceito, mais margem proxy
# =====================================================================

_BASES_CUSTO = [
    ("cusmed", "CUSMED", "Custo médio"),
    ("cusmedicm", "CUSMEDICM", "Custo médio com ICMS"),
    ("cussemicm", "CUSSEMICM", "Custo médio sem ICMS"),
    ("cusrep", "CUSREP", "Custo de reposição"),
    ("cusger", "CUSGER", "Custo gerencial"),
    ("cusvariavel", "CUSVARIAVEL", "Custo variável"),
]

for _id, _sigla, _nome in _BASES_CUSTO:
    _METRICAS.append(
        Metrica(
            id=f"custo_total_{_id}",
            label=f"Custo total — {_sigla}",
            descricao=f"{_nome} aplicado à QUANTIDADE vendida (o custo está na unidade de venda, não por tonelada), via as-of join.",
            unidade=Unidade.MOEDA,
            grao="item",
            formula=f"SUM(qtd * {_id}) FILTER (WHERE NOT custo_outlier)",
            sql_expr=f"SUM(custo_{_id})",
            fonte="analytics.fact_venda_item (custo as-of de fact_custo_pa)",
            regra_filtro="Custo vigente: maior DTATUAL <= data de referência (RN-07).",
            observacoes="Conceito NÃO homologado economicamente (Q-04).",
            categoria="CUSTOS",
        )
    )
    _METRICAS.append(
        Metrica(
            id=f"margem_proxy_{_id}",
            label=f"Margem Proxy — Base {_sigla}",
            descricao=f"Receita menos {_nome} aplicado à quantidade. "
                      "NÃO é margem contábil.",
            unidade=Unidade.MOEDA,
            grao="agregado",
            formula=f"SUM(vlrtot) - SUM(qtd * {_id}), ambos excluindo linhas com outlier de custo",
            sql_expr=f"SUM(receita_com_custo) - SUM(custo_{_id})",
            fonte="analytics.mv_sales_month",
            regra_filtro="Exclui itens sem custo e com outlier de custo (Q-15); a receita do denominador usa a MESMA população de linhas.",
            observacoes="O termo 'margem' é proibido até a Controladoria homologar o "
                        "conceito de custo (especificação §6.3 e §36.3).",
            depende_de=("receita_liquida", f"custo_total_{_id}"),
            categoria="CUSTOS",
        )
    )
    _METRICAS.append(
        Metrica(
            id=f"margem_proxy_pct_{_id}",
            label=f"Margem Proxy % — Base {_sigla}",
            descricao="Margem proxy sobre a receita.",
            unidade=Unidade.PERCENTUAL,
            grao="agregado",
            formula=f"(SUM(vlrtot) - SUM(qtd * {_id})) / NULLIF(SUM(vlrtot), 0) * 100, sobre linhas sem outlier",
            sql_expr=f"(SUM(receita_com_custo) - SUM(custo_{_id})) / NULLIF(SUM(receita_com_custo), 0) * 100",
            fonte="analytics.mv_sales_month",
            depende_de=(f"margem_proxy_{_id}",),
            categoria="CUSTOS",
        )
    )

# =====================================================================
# LOGISTICA
# =====================================================================

_METRICAS += [
    Metrica(
        id="frete_alocado",
        label="Frete alocado",
        descricao="Valor de CT-e rateado às notas de venda por tonelagem.",
        unidade=Unidade.MOEDA,
        grao="vínculo CT-e × NF-e",
        formula="SUM(vlrfrete_alocado) WHERE match_status <> 'SEM_VINCULO'",
        sql_expr="SUM(frete_alocado)",
        fonte="analytics.bridge_cte_nfe",
        regra_filtro="Só CT-e com NF-e de venda identificada.",
        observacoes="15,52% do frete total NÃO é alocado (CT-e sem NF-e correspondente). "
                    "O indicador é exibido junto com a métrica, sempre (RN-08).",
        categoria="LOGISTICA",
    ),
    Metrica(
        id="frete_por_ton",
        label="Frete por tonelada",
        descricao="Frete alocado dividido pela tonelagem transportada.",
        unidade=Unidade.MOEDA_POR_TON,
        grao="agregado",
        formula="SUM(vlrfrete_alocado) / SUM(ABS(tonliq))",
        sql_expr="SUM(frete_alocado) / NULLIF(SUM(ton_liquida), 0)",
        fonte="analytics.mv_freight_route_month",
        depende_de=("frete_alocado", "volume_liquido_t"),
        categoria="LOGISTICA",
    ),
    Metrica(
        id="frete_sobre_receita",
        label="Frete sobre receita",
        descricao="Peso do custo logístico alocado na receita.",
        unidade=Unidade.PERCENTUAL,
        grao="agregado",
        formula="SUM(vlrfrete_alocado) / NULLIF(SUM(vlrtot), 0) * 100",
        sql_expr="SUM(frete_alocado) / NULLIF(SUM(receita_liquida), 0) * 100",
        fonte="analytics.mv_sales_month",
        depende_de=("frete_alocado", "receita_liquida"),
        categoria="LOGISTICA",
    ),
    Metrica(
        id="pct_frete_nao_alocado",
        label="% de frete não alocado",
        descricao="Parte do frete que não pôde ser vinculada a uma nota de venda.",
        unidade=Unidade.PERCENTUAL,
        grao="agregado",
        formula="(frete_total_cte - frete_alocado) / frete_total_cte * 100",
        sql_expr="",
        fonte="analytics.fact_cte + analytics.bridge_cte_nfe",
        status=Status.RECONCILIADA,
        observacoes="Métrica de honestidade: deve aparecer em toda tela de logística.",
        categoria="LOGISTICA",
    ),
]

# =====================================================================
# TRIBUTOS
# =====================================================================

_METRICAS += [
    Metrica(
        id="icms",
        label="ICMS destacado",
        descricao="Soma de VLRICMS dos itens.",
        unidade=Unidade.MOEDA,
        grao="item",
        formula="SUM(vlricms)",
        sql_expr="SUM(icms)",
        fonte="analytics.fact_venda_item",
        observacoes="Difere do 'Vr ICMS' do 161 OUTROS, que aparenta ser ICMS a "
                    "recolher (Q-13). Não são a mesma coisa.",
        categoria="TRIBUTOS",
    ),
    Metrica(
        id="substituicao",
        label="ICMS substituição tributária",
        descricao="Soma de VLRSUBST dos itens.",
        unidade=Unidade.MOEDA,
        grao="item",
        formula="SUM(vlrsubst)",
        sql_expr="SUM(substituicao)",
        fonte="analytics.fact_venda_item",
        categoria="TRIBUTOS",
    ),
]

# =====================================================================
# API
# =====================================================================

REGISTRY: dict[str, Metrica] = {m.id: m for m in _METRICAS}


def get(metric_id: str) -> Metrica:
    if metric_id not in REGISTRY:
        raise KeyError(
            f"Métrica '{metric_id}' não existe no registro. "
            f"Disponíveis: {', '.join(sorted(REGISTRY))}"
        )
    return REGISTRY[metric_id]


def listar(categoria: str | None = None) -> list[Metrica]:
    ms = list(REGISTRY.values())
    if categoria:
        ms = [m for m in ms if m.categoria == categoria]
    return sorted(ms, key=lambda m: (m.categoria, m.label))


def categorias() -> list[str]:
    return sorted({m.categoria for m in REGISTRY.values()})


def bases_custo() -> list[tuple[str, str, str]]:
    return list(_BASES_CUSTO)


def como_tabela() -> list[dict[str, str]]:
    """Registro completo para a página de Qualidade → Métricas."""
    return [
        {
            "ID": m.id,
            "Métrica": m.label,
            "Unidade": m.unidade.value,
            "Categoria": m.categoria,
            "Grão": m.grao,
            "Fórmula": m.formula,
            "Fonte": m.fonte,
            "Status": m.status.value,
            "Regra de sinal": m.regra_sinal or "—",
            "Regra de filtro": m.regra_filtro or "—",
            "Observações": m.observacoes or "—",
            "Homologada em": m.homologado_em or "—",
        }
        for m in listar()
    ]
