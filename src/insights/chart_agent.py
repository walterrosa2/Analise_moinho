"""
Ajuda contextual e analise local para graficos.

O objetivo deste modulo e transformar os dados ja expostos no grafico em uma
leitura assistida: objetivo do visual, como interpretar e pontos numericos que
merecem atencao. Nao chama LLM nem servico externo; a analise e deterministica
para preservar rastreabilidade e funcionamento offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

import plotly.graph_objects as go
import polars as pl


@dataclass(frozen=True)
class GraphSpec:
    objetivo: str
    como_ler: str
    foco: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphAnalysis:
    objetivo: str
    como_ler: str
    analise: tuple[str, ...]
    atencoes: tuple[str, ...] = ()


EXATOS: dict[str, GraphSpec] = {
    "receita_volume": GraphSpec(
        "Comparar a evolução da receita líquida com o volume vendido no mesmo recorte.",
        "A linha mostra receita; as barras mostram toneladas. Quando as curvas se afastam, o PMV ou o mix provavelmente mudou.",
        ("receita_liquida", "ton_liquida"),
    ),
    "pmv": GraphSpec(
        "Acompanhar a variação mensal do preço médio de venda.",
        "Subidas e quedas do PMV devem ser lidas junto com volume e mix, porque produtos diferentes podem mover o preço médio consolidado.",
        ("pmv",),
    ),
    "mix_volume": GraphSpec(
        "Mostrar como as classificações disputam participação no volume total.",
        "A área 100% empilhada compara participação, não tamanho absoluto. Uma faixa maior significa mais peso no mix do período.",
        ("ton_liquida",),
    ),
    "mix_receita": GraphSpec(
        "Mostrar como as classificações disputam participação na receita total.",
        "A área 100% empilhada compara participação em receita. Mudanças podem vir de volume, preço ou ambos.",
        ("receita_liquida",),
    ),
    "variacao_classificacao": GraphSpec(
        "Explicar quais classificações puxaram a receita para cima ou para baixo contra o período anterior.",
        "Barras positivas aumentam a variação total; barras negativas reduzem. O total final é a soma das contribuições exibidas.",
        ("variacao", "efeito_volume", "efeito_preco"),
    ),
    "vendas_devolucoes": GraphSpec(
        "Separar venda bruta e devolução para medir o quanto retorna contra o que foi vendido.",
        "A linha representa venda bruta; as barras mostram devoluções em módulo. Devolução alta em meses de venda alta pode indicar risco operacional ou comercial.",
        ("vendas_brutas", "devolucoes"),
    ),
    "pmv_desconto": GraphSpec(
        "Avaliar se movimentos de preço médio vieram acompanhados de mais desconto concedido.",
        "A linha mostra PMV; as barras mostram desconto. Alta de desconto com PMV em queda merece investigacao de politica comercial.",
        ("pmv", "desconto"),
    ),
    "quadrante_vendedores": GraphSpec(
        "Comparar vendedores em dois eixos de performance escolhidos na tela.",
        "A posição mostra os eixos selecionados; o tamanho da bolha mostra receita; a cor mostra margem proxy. As medianas dividem o grupo comparável.",
        ("receita_liquida", "margem_proxy_pct"),
    ),
    "movimento_base": GraphSpec(
        "Acompanhar a saude da base de clientes ao longo do tempo.",
        "Ativos mostram clientes com movimento no mês; novos são primeiras compras; reativados voltaram após longo intervalo sem compra.",
        ("ativos", "novos", "reativados"),
    ),
    "matriz_clientes": GraphSpec(
        "Priorizar clientes combinando tamanho atual e crescimento ou retração.",
        "Quanto mais à direita, maior participação. Acima de zero cresce; abaixo de zero retrai. Clientes grandes em queda pedem investigação primeiro.",
        ("participacao_pct", "variacao_pct", "valor_b"),
    ),
    "rfm_scatter": GraphSpec(
        "Ler recência e frequência para identificar clientes saudáveis, em risco ou pouco explorados.",
        "Menor recência e maior frequência indicam relacionamento mais ativo. O tamanho representa receita e a cor resume o score RFM.",
        ("recencia_dias", "frequencia_meses", "receita", "score_total"),
    ),
    "cross_sell": GraphSpec(
        "Encontrar clientes com baixa diversidade de compra e potencial de cross-sell.",
        "Poucos produtos com receita relevante indicam concentracao de carteira; muitos produtos sugerem relacionamento mais amplo.",
        ("produtos", "receita_liquida", "ton_liquida"),
    ),
    "positivados_mes": GraphSpec(
        "Medir o ritmo mensal de entrada de novos clientes.",
        "Cada barra é uma coorte de primeira compra. Picos isolados devem ser separados de mudanças sustentadas de aquisição.",
        ("positivados",),
    ),
    "receita_positivados": GraphSpec(
        "Avaliar a receita gerada pelos clientes novos ao longo do tempo.",
        "A linha mostra o valor associado aos positivados do mês. Compare com quantidade de clientes para diferenciar volume de entrada e qualidade da entrada.",
        ("vlrtot_positivados",),
    ),
    "perc_positivados": GraphSpec(
        "Medir o peso dos clientes novos dentro da receita mensal total.",
        "Percentuais altos indicam que a receita do mês dependeu mais de clientes recém-entrados.",
        ("perc_positivados_geral",),
    ),
    "taxa_recompra": GraphSpec(
        "Comparar a taxa de segunda compra entre coortes.",
        "Coortes recentes tendem a parecer piores por terem menos tempo de maturação. Compare meses com idade semelhante.",
        ("taxa_recompra_pct",),
    ),
    "receita_coorte": GraphSpec(
        "Comparar o valor medio acumulado por cliente de cada coorte.",
        "Barras maiores indicam coortes que geraram mais valor medio depois da entrada.",
        ("receita_media_por_cliente",),
    ),
    "matriz_retencao": GraphSpec(
        "Mostrar quanto de cada coorte continua comprando apos a entrada.",
        "Cada linha é uma coorte; cada coluna é a idade da coorte em meses. Cores mais intensas indicam maior retenção.",
        ("retencao_pct",),
    ),
    "recompra_janelas": GraphSpec(
        "Comparar recompra em janelas padronizadas de 30 a 365 dias.",
        "Linhas mais altas indicam recompra mais rapida ou mais frequente. Janelas maiores devem ser sempre iguais ou superiores as menores.",
        ("taxa_pct",),
    ),
    "sem_recompra": GraphSpec(
        "Identificar coortes em que muitos clientes novos nunca voltaram a comprar.",
        "Barras altas apontam entrada sem retenção. O gráfico indica onde investigar carteira, produto, preço ou atendimento.",
        ("sem_recompra_pct",),
    ),
    "comparar_custos": GraphSpec(
        "Comparar PMV e todos os conceitos de custo no tempo.",
        "A distância entre as linhas mostra o impacto da escolha da base. Nenhuma linha de custo é oficial sem homologação da Controladoria.",
        ("pmv", "cusger", "cusvariavel"),
    ),
    "conceitos_media": GraphSpec(
        "Resumir a diferença média entre os conceitos de custo.",
        "Barras mais altas indicam conceitos que pressionam mais a margem proxy. A comparação é exploratória até homologação.",
        ("Média R$/t",),
    ),
    "custo_pmv_produto": GraphSpec(
        "Comparar custo por tonelada e PMV produto a produto.",
        "Pontos proximos ou acima da diagonal economica esperada indicam spread comprimido; a cor mostra margem proxy.",
        ("custo_por_ton", "pmv", "margem_proxy_pct"),
    ),
    "menores_margens": GraphSpec(
        "Listar produtos com menor margem proxy percentual.",
        "Barras mais baixas ou negativas pedem validação de custo, preço, desconto e outliers antes de conclusão comercial.",
        ("margem_proxy_pct",),
    ),
    "spread": GraphSpec(
        "Mostrar a folga mensal entre PMV e custo por tonelada.",
        "Barras positivas indicam PMV acima do custo escolhido; barras negativas indicam compressao forte da margem proxy.",
        ("spread_por_ton",),
    ),
    "margem_pct": GraphSpec(
        "Acompanhar a margem proxy percentual no tempo.",
        "Quedas persistentes indicam perda de spread ou mudanca de mix. A leitura depende da base de custo selecionada.",
        ("margem_proxy_pct",),
    ),
    "amplitude_custos": GraphSpec(
        "Mostrar produtos em que a escolha do conceito de custo mais muda a conclusao.",
        "Amplitude alta significa que as bases de custo divergem muito entre si. Esses produtos dependem mais de homologacao da Controladoria.",
        ("amplitude_pct",),
    ),
    "frete_mensal": GraphSpec(
        "Acompanhar valor de frete alocado e custo logístico por tonelada no tempo.",
        "Barras mostram frete total; linha mostra R$/t. Alta de R$/t sem alta de frete total pode indicar cargas menores ou rotas mais caras.",
        ("frete", "frete_por_ton"),
    ),
    "frete_receita": GraphSpec(
        "Medir o peso do frete alocado sobre a receita.",
        "Percentual maior significa que a logística consumiu mais da receita do período. Leia junto com o indicador de frete não alocado.",
        ("frete_sobre_receita",),
    ),
    "rotas_frete": GraphSpec(
        "Identificar as rotas que mais consomem valor absoluto de frete.",
        "Barras maiores indicam maior gasto total. Uma rota relevante em valor não é necessariamente a mais cara por tonelada.",
        ("frete",),
    ),
    "rotas_caras": GraphSpec(
        "Identificar rotas com maior custo logístico por tonelada.",
        "O filtro mínimo de tonelagem reduz distorção por viagens muito pequenas. Compare com distância e perfil de carga antes de concluir.",
        ("frete_por_ton",),
    ),
    "boxplot_uf": GraphSpec(
        "Comparar a dispersão do frete por tonelada entre UFs de destino.",
        "Caixas largas e muitos pontos extremos indicam alta variabilidade dentro da mesma UF.",
        ("frete_por_ton",),
    ),
    "dispersao_carga": GraphSpec(
        "Testar se cargas pequenas custam mais por tonelada.",
        "Pontos à esquerda e altos indicam notas pequenas com R$/t elevado. A distância e a rota também precisam ser verificadas.",
        ("ton", "frete_por_ton", "frete"),
    ),
    "faixas_carga_gr": GraphSpec(
        "Comparar o R$/t mediano por faixas de tamanho da carga.",
        "Barras maiores em faixas pequenas reforçam a hipótese de perda de escala logística.",
        ("rs_por_ton_mediano",),
    ),
    "series_trigo": GraphSpec(
        "Comparar trigo, custos e PMV no mesmo eixo temporal.",
        "Curvas que se movem juntas sugerem repasse ou pressão de custo; a página é exploratória e não prova causalidade.",
        ("trigo_preco_medio", "pmv", "cusger_por_ton"),
    ),
    "compra_trigo": GraphSpec(
        "Mostrar o volume mensal de compra de trigo.",
        "Picos e vales ajudam a separar efeito de compra, estoque e custo médio observado.",
        ("trigo_ton_comprada",),
    ),
    "estoque_trigo": GraphSpec(
        "Acompanhar o estoque fisico de trigo disponivel no tempo.",
        "Mudanças no estoque podem suavizar ou atrasar o efeito do preço de compra sobre custo e PMV.",
        ("trigo_ton_estoque",),
    ),
    "base_100": GraphSpec(
        "Comparar variações relativas entre séries com unidades diferentes.",
        "Todas as séries partem de 100. Acima de 100 cresceu contra o primeiro mês; abaixo de 100 caiu.",
        (),
    ),
    "correlacao_defasagem": GraphSpec(
        "Testar em qual defasagem mensal duas séries se movem mais juntas.",
        "Valores perto de 1 ou -1 indicam relação linear forte; perto de 0 indicam baixa relação. Correlação não prova causa.",
        ("correlacao", "defasagem_meses"),
    ),
    "dispersao_trigo": GraphSpec(
        "Visualizar a relação direta entre duas séries sem defasagem.",
        "Pontos alinhados sugerem associacao linear. Dispersao alta indica que outros fatores explicam parte do movimento.",
        (),
    ),
    "reconciliacao_mensal": GraphSpec(
        "Mostrar a divergência mensal entre modelo analítico e fonte gerencial.",
        "A linha deve ficar dentro da tolerância definida. Picos indicam meses que precisam de explicação antes de apresentar.",
        ("diff_pct",),
    ),
    "orcado_realizado": GraphSpec(
        "Comparar o valor realizado contra o orçamento da fonte gerencial 161.",
        "As barras lado a lado mostram se o realizado ficou acima ou abaixo do planejado em cada mês.",
        ("REALIZADO", "ORÇADO"),
    ),
}

PREFIXOS: tuple[tuple[str, GraphSpec], ...] = (
    ("mapa_uf_", GraphSpec(
        "Ler a distribuição geográfica real do cliente por UF.",
        "A cor representa a métrica escolhida. O mapa usa geografia real, não região comercial interna.",
    )),
    ("uf_", GraphSpec(
        "Ordenar UFs pela métrica escolhida no mapa.",
        "Use o ranking quando o mapa não carregar ou para comparar valores com mais precisão.",
    )),
    ("evolucao_", GraphSpec(
        "Comparar a evolução temporal da métrica escolhida entre categorias.",
        "Cada linha é uma categoria. Separação persistente indica diferença estrutural; cruzamentos indicam mudança de posição.",
    )),
    ("regiao_", GraphSpec(
        "Acompanhar regioes comerciais ao longo do tempo.",
        "A região comercial é atribuição interna. Não confundir com UF ou cidade real do cliente.",
    )),
    ("heatmap_", GraphSpec(
        "Encontrar concentrações, picos e lacunas no cruzamento mês x categoria.",
        "Cores mais intensas indicam maior valor. Leia por linha para tendência e por coluna para comparação no mesmo mês.",
    )),
    ("receita_classificacao", GraphSpec(
        "Mostrar a composição mensal da receita por classificação.",
        "O tamanho total da barra é a receita do mês; cada cor mostra a contribuição de uma classificação.",
        ("receita_liquida",),
    )),
    ("ton_classificacao", GraphSpec(
        "Mostrar a composição mensal do volume por classificação.",
        "O tamanho total da barra é a tonelagem do mês; cada cor mostra a contribuição de uma classificação.",
        ("ton_liquida",),
    )),
    ("delta_mix", GraphSpec(
        "Mostrar quem ganhou ou perdeu participação de volume entre dois períodos.",
        "Barras positivas ganharam share; negativas perderam. O numero esta em pontos percentuais.",
        ("delta_share_pp",),
    )),
    ("waterfall_", GraphSpec(
        "Explicar a contribuição de cada categoria para a variação total.",
        "Barras positivas puxam o total para cima; negativas puxam para baixo. A barra final soma as contribuicoes exibidas.",
        ("variacao",),
    )),
    ("efeito_volume", GraphSpec(
        "Separar a parcela da variacao atribuida a quantidade vendida.",
        "Valores positivos indicam ganho por volume; negativos indicam perda por volume.",
        ("efeito_volume",),
    )),
    ("efeito_preco", GraphSpec(
        "Separar a parcela da variação atribuída a preço médio.",
        "Valores positivos indicam ganho por preço; negativos indicam perda por preço.",
        ("efeito_preco",),
    )),
    ("receita_", GraphSpec(
        "Ordenar categorias pelo valor de receita no recorte.",
        "Barras maiores concentram mais receita. Use junto com participação para medir dependência.",
        ("receita_liquida", "receita"),
    )),
    ("disp_", GraphSpec(
        "Comparar dois indicadores em dispersão para achar grupos fora do padrão.",
        "Pontos isolados ou distantes do conjunto merecem investigação. Tamanho e cor agregam contexto quando disponíveis.",
    )),
    ("dispersao_", GraphSpec(
        "Comparar dois indicadores em dispersão para achar relações e outliers.",
        "O eixo X e o eixo Y mostram medidas diferentes; pontos distantes do bloco principal pedem detalhamento.",
    )),
    ("pareto_", GraphSpec(
        "Medir concentração e dependência nos maiores itens.",
        "As barras mostram valor por categoria e a linha mostra percentual acumulado. Quanto mais rápido chega a 80%, maior a concentração.",
        ("receita_liquida", "frete"),
    )),
    ("treemap_", GraphSpec(
        "Visualizar concentracao por area proporcional.",
        "Retângulos maiores representam maior participação no total. Use para enxergar rapidamente quem domina o recorte.",
    )),
    ("ranking_", GraphSpec(
        "Ordenar os maiores elementos do recorte pela métrica principal.",
        "A ordem das barras mostra prioridade de leitura. O ranking mede resultado observado, não causa.",
    )),
    ("clientes_", GraphSpec(
        "Entender distribuição ou concentração de clientes no recorte.",
        "Barras maiores indicam mais clientes; compare com receita ou volume antes de inferir valor economico.",
        ("clientes",),
    )),
    ("rfm_", GraphSpec(
        "Ler saúde e valor da carteira pelo modelo RFM.",
        "Scores mais altos combinam compra recente, frequente e com maior valor. Use como triagem, não como decisão final.",
    )),
    ("pmv_custo_", GraphSpec(
        "Comparar PMV com o custo por tonelada da base escolhida.",
        "Quando as linhas se aproximam, o spread diminui. A margem é proxy porque o conceito de custo não está homologado.",
        ("pmv", "custo_por_ton"),
    )),
    ("historico_", GraphSpec(
        "Mostrar o historico completo dos conceitos de custo de um produto.",
        "Saltos ou quebras podem indicar mudança real, cadastro atípico ou necessidade de validar unidade e data do custo.",
    )),
    ("frete_", GraphSpec(
        "Ordenar categorias pelo valor de frete alocado.",
        "Barras maiores mostram onde o frete pesa mais em valor absoluto. Leia junto com R$/t para separar escala de eficiencia.",
        ("frete",),
    )),
    ("rs_ton_", GraphSpec(
        "Comparar custo logístico por tonelada entre categorias.",
        "Barras maiores indicam maior R$/t. Verifique volume, distância e vínculo de CT-e antes de concluir.",
        ("frete_por_ton",),
    )),
    ("explorador_", GraphSpec(
        "Responder a pergunta configurada no Explorador com a dimensão, métrica e visual escolhidos.",
        "A leitura depende da configuração ativa. A tabela completa abaixo preserva os dados que originaram o gráfico.",
    )),
)

COLUNAS_TEMPO = ("ano_mes", "period", "coorte", "data", "mes")
COLUNAS_CATEGORIA = (
    "rotulo", "descrprod", "rota", "vendedor", "cliente", "regiao", "uf",
    "Conceito", "faixa", "janela", "scope", "metric_id",
)
IGNORAR_NUMERICAS = {
    "chave", "codprod", "codparc", "codvend", "codreg", "codemp", "nunota",
    "sequencia", "ano", "mes", "defasagem_meses", "meses_comparados",
}
PRIORIDADE_METRICAS = (
    "receita_liquida", "receita", "valor_b", "variacao", "vendas_brutas",
    "devolucoes", "frete", "frete_por_ton", "frete_sobre_receita", "pmv",
    "custo_por_ton", "spread_por_ton", "margem_proxy_pct", "ton_liquida",
    "ton", "clientes", "positivados", "taxa_recompra_pct", "retencao_pct",
    "sem_recompra_pct", "correlacao", "diff_pct",
)


def dados_do_fig(fig: go.Figure) -> pl.DataFrame | None:
    """Extrai uma tabela minima de um Plotly Figure para analise quando a pagina nao passou dados."""
    linhas: list[dict[str, Any]] = []
    for trace in fig.data:
        tipo = getattr(trace, "type", "") or ""
        nome = str(getattr(trace, "name", None) or "valor")

        if tipo == "heatmap":
            xs = _as_list(getattr(trace, "x", None))
            ys = _as_list(getattr(trace, "y", None))
            zs = _as_list(getattr(trace, "z", None))
            for iy, y in enumerate(ys):
                row_z = _as_list(zs[iy]) if iy < len(zs) else []
                for ix, x in enumerate(xs):
                    valor = row_z[ix] if ix < len(row_z) else None
                    linhas.append({"x": x, "rotulo": y, "valor": valor})
            continue

        if tipo == "treemap":
            labels = _as_list(getattr(trace, "labels", None))
            values = _as_list(getattr(trace, "values", None))
            for label, value in zip(labels, values, strict=False):
                linhas.append({"rotulo": label, "valor": value})
            continue

        x = _as_list(getattr(trace, "x", None))
        y = _as_list(getattr(trace, "y", None))
        if not x and not y:
            continue

        # Barras horizontais guardam a categoria em y e o valor em x.
        orientacao = getattr(trace, "orientation", None)
        if orientacao == "h" and x and y:
            for categoria, valor in zip(y, x, strict=False):
                linhas.append({"rotulo": categoria, nome: valor})
            continue

        if x and y:
            for eixo, valor in zip(x, y, strict=False):
                linhas.append({"x": eixo, nome: valor})
        elif y:
            for valor in y:
                linhas.append({"rotulo": nome, "valor": valor})

    if not linhas:
        return None
    try:
        return pl.DataFrame(linhas)
    except Exception:  # noqa: BLE001
        return None


def analisar(
    nome: str,
    dados: pl.DataFrame | None,
    fig: go.Figure | None = None,
    ajuda: str | None = None,
) -> GraphAnalysis | None:
    """Gera objetivo, como ler e analise numerica para um grafico."""
    base = dados if dados is not None and dados.height else (dados_do_fig(fig) if fig else None)
    spec = _spec(nome, fig)
    objetivo = ajuda or spec.objetivo
    como_ler = spec.como_ler or _como_ler_generico(fig, base)
    if base is None or base.height == 0:
        return GraphAnalysis(
            objetivo=objetivo,
            como_ler=como_ler,
            analise=("Sem dados tabulares suficientes para analisar este recorte.",),
        )

    analise, atencoes = _analise_dados(nome, base, spec)
    return GraphAnalysis(objetivo=objetivo, como_ler=como_ler, analise=tuple(analise), atencoes=tuple(atencoes))


def ajuda_indicador(titulo: str) -> str | None:
    """Ajuda objetiva para cartoes/KPIs comuns."""
    t = _normalizar(titulo)
    if "receita liquida" in t:
        return "Soma de VLRTOT no grão de item. Devoluções entram negativas, então o número já é líquido do que voltou."
    if "vendas brutas" in t:
        return "Receita das vendas antes de abater devoluções. Ajuda a separar venda realizada de retorno."
    if "receita" in t:
        return "Valor econômico observado no recorte. Use junto com volume, clientes e concentração para entender a origem do total."
    if "devolu" in t:
        return "Valor de itens devolvidos, preservado com sinal negativo conforme veio da origem."
    if "volume" in t or "tonelada" in t:
        return "Soma de TONLIQ. Devoluções reduzem a tonelagem porque a origem já traz o sinal negativo."
    if t == "pmv" or "pmv " in t or "pmv medio" in t:
        return "Preço médio de venda: receita dividida por toneladas, excluindo bonificações e amostras sem receita por padrão."
    if "clientes ativos" in t or t == "clientes":
        return "Clientes distintos com movimento no recorte filtrado. Não é o mesmo que positivados do mês."
    if "clientes novos" in t or "positivado" in t:
        return "Clientes cuja primeira compra ocorreu no período. É entrada de coorte, não cliente ativo recorrente."
    if "documentos" in t:
        return "Quantidade de notas/documentos distintos. Medidas de documento não devem ser somadas no grão de item."
    if "produtos" in t:
        return "Quantidade de produtos distintos no recorte. Ajuda a medir amplitude de mix ou oportunidade de cross-sell."
    if "desconto" in t:
        return "Soma de VLRDESC dos itens. Use junto com PMV para avaliar pressão comercial."
    if "frete total" in t:
        return "Total dos CT-e de frete de venda carregados. Parte pode não estar vinculada a NF-e de venda."
    if "frete alocado" in t:
        return "Valor de CT-e distribuído às notas de venda vinculadas, com rateio explícito por tonelagem."
    if "nao alocado" in t:
        return "Parcela do frete sem vínculo confiável com NF-e de venda. Deve limitar conclusões de custo logístico."
    if "sem nf" in t:
        return "Percentual de CT-e sem chave NF-e de venda informada ou encontrada na base."
    if "sem ordem" in t:
        return "Percentual de CT-e sem ORDEMCARGA válida. Evidencia por que ordem de carga não é chave confiável."
    if t == "ct e" or "ct-e" in titulo.lower():
        return "Quantidade de conhecimentos de transporte eletrônicos no recorte logístico."
    if "custo" in t and "medio" in t:
        return "Custo médio da base selecionada. Os conceitos ainda não são homologados economicamente."
    if "custo" in t:
        return "Custo calculado com a base escolhida no filtro. Nenhuma base é custo oficial sem validação da Controladoria."
    if "margem proxy" in t:
        return "Receita comparável menos custo da base selecionada. É margem proxy, não margem contábil oficial."
    if "spread" in t:
        return "Diferença entre PMV e custo por tonelada. Mede folga exploratória, não margem contábil."
    if "recompra" in t:
        return "Percentual de clientes de uma coorte que voltaram a comprar dentro da janela indicada."
    if "receita acumulada" in t:
        return "Receita somada ao longo da vida observada dos clientes/coortes no recorte."
    if "media mensal" in t:
        return "Média aritmética mensal do indicador no período analisado."
    if "ultimo mes" in t:
        return "Valor observado no mês mais recente disponível dentro do recorte."
    if "top " in t:
        return "Participação acumulada dos maiores itens no total do recorte. Mede concentração."
    if "clientes" in t:
        return "Quantidade de clientes observada no recorte. Compare com receita e frequência antes de inferir qualidade da carteira."
    if "vendedores com movimento" in t:
        return "Vendedores/códigos com venda observada no recorte. Não inclui cadastros sem movimento."
    if "maior vendedor" in t or "maior cliente" in t:
        return "Participação do maior item no total. Mede concentração, não explica causa."
    if "rotas" in t:
        return "Quantidade de pares origem-destino com frete alocado no recorte."
    if "r$/t mediano" in t:
        return "Mediana do frete por tonelada. Menos sensível a rotas extremas do que a média."
    if "percentil 90" in t or "p90" in t:
        return "Valor acima do qual estão os 10% casos mais caros. Usado para destacar rotas atípicas."
    if "recencia" in t:
        return "Dias desde a última compra observada. Quanto menor, mais recente é o relacionamento."
    if "frequencia" in t:
        return "Quantidade de meses com compra. Ajuda a diferenciar cliente recorrente de cliente ocasional."
    if "ticket" in t:
        return "Receita média por documento ou cliente, conforme o contexto da tela."
    if "verificacao" in t:
        return "Quantidade de checagens automáticas executadas sobre dados, grãos e reconciliação."
    if "reconciliacao" in t:
        return "Pontos comparados contra fonte gerencial dentro da tolerância definida, sem ajuste para forçar encaixe."
    if "linhas carregadas" in t:
        return "Total de linhas importadas nos lotes de carga bem-sucedidos."
    if "ultima carga" in t:
        return "Data e hora do lote mais recente registrado pelo pipeline."
    return None


def _spec(nome: str, fig: go.Figure | None) -> GraphSpec:
    if nome in EXATOS:
        return EXATOS[nome]
    for prefixo, spec in PREFIXOS:
        if nome.startswith(prefixo):
            return spec
    return GraphSpec(
        "Ajudar a comparar os valores do recorte atual e encontrar picos, quedas, concentrações ou pontos fora do padrão.",
        _como_ler_generico(fig, None),
    )


def _analise_dados(nome: str, df: pl.DataFrame, spec: GraphSpec) -> tuple[list[str], list[str]]:
    analise: list[str] = []
    atencoes: list[str] = []
    colunas_num = _colunas_numericas(df)
    if not colunas_num:
        return ["O gráfico tem dados, mas nenhuma coluna numérica adequada para leitura automática."], atencoes

    if "correlacao" in df.columns:
        analise.extend(_analise_correlacao(df))
        atencoes.append("Correlação indica associação estatística; não estabelece causalidade.")
        return _limitar(analise), atencoes

    primaria = _coluna_primaria(nome, df, spec, colunas_num)
    tempo = _coluna_tempo(df)
    categoria = _coluna_categoria(df)

    if tempo:
        analise.extend(_analise_temporal(df, tempo, primaria))

    if "variacao" in df.columns or nome.startswith("waterfall_"):
        analise.extend(_analise_variacao(df))
    elif categoria:
        analise.extend(_analise_categorica(df, categoria, primaria))

    if len(colunas_num) >= 2:
        analise.extend(_analise_relacao(df, colunas_num, primaria))

    if any("margem_proxy" in c for c in df.columns):
        atencoes.append("Margem proxy depende da base de custo selecionada e não é margem contábil homologada.")
    if any(c in df.columns for c in ("frete", "frete_por_ton", "frete_sobre_receita")):
        atencoes.append("Leitura logística deve considerar o percentual de frete não alocado.")
    if any(c in df.columns for c in ("trigo_preco_medio", "cusger_por_ton", "cusvariavel_por_ton")):
        atencoes.append("A página de trigo mostra correlação exploratória; não há prova de causalidade.")
    if "devolucoes" in df.columns:
        atencoes.append("Devoluções são preservadas com sinal negativo na origem.")

    if not analise:
        valores = _valores_numericos(df, primaria)
        if valores:
            analise.append(
                f"{_rotulo(primaria)} vai de {_fmt(primaria, min(valores))} a {_fmt(primaria, max(valores))} no recorte."
            )
    return _limitar(analise), list(dict.fromkeys(atencoes))[:3]


def _as_list(valor: Any) -> list[Any]:
    if valor is None:
        return []
    try:
        return list(valor)
    except TypeError:
        return [valor]


def _analise_temporal(df: pl.DataFrame, tempo: str, metrica: str) -> list[str]:
    d = _ordenar(df, tempo)
    serie = d.select(tempo, pl.col(metrica).cast(pl.Float64, strict=False).alias("_v")).drop_nulls()
    if serie.height == 0:
        return []

    primeiro = float(serie["_v"][0])
    ultimo = float(serie["_v"][-1])
    periodo_ini = str(serie[tempo][0])
    periodo_fim = str(serie[tempo][-1])
    out = [
        f"{_rotulo(metrica)} foi de {_fmt(metrica, primeiro)} em {periodo_ini} para {_fmt(metrica, ultimo)} em {periodo_fim} ({_fmt_delta_pct(_pct(primeiro, ultimo))})."
    ]
    idx_max = int(serie["_v"].arg_max())
    idx_min = int(serie["_v"].arg_min())
    out.append(
        f"Pico em {serie[tempo][idx_max]}: {_fmt(metrica, float(serie['_v'][idx_max]))}; menor ponto em {serie[tempo][idx_min]}: {_fmt(metrica, float(serie['_v'][idx_min]))}."
    )
    return out


def _analise_categorica(df: pl.DataFrame, categoria: str, metrica: str) -> list[str]:
    d = _com_valor(df, metrica).sort("_valor", descending=True)
    if d.height == 0:
        return []

    total = float(d["_valor"].sum() or 0)
    maior = d.sort("_valor", descending=True).head(1).to_dicts()[0]
    menor = d.sort("_valor").head(1).to_dicts()[0]
    out = []
    if total > 0:
        share = 100 * float(maior["_valor"] or 0) / total
        out.append(
            f"Maior contribuição: {maior.get(categoria, '—')} com {_fmt(metrica, maior['_valor'])}, equivalente a {_fmt_pct(share)} do total exibido."
        )
        if d.height >= 5:
            top5 = float(d.head(5)["_valor"].sum() or 0)
            out.append(f"Top 5 soma {_fmt_pct(100 * top5 / total)} do total exibido, indicando o grau de concentração do recorte.")
    else:
        out.append(f"Maior valor: {maior.get(categoria, '—')} com {_fmt(metrica, maior['_valor'])}.")

    if menor.get(categoria) != maior.get(categoria):
        out.append(f"Menor valor: {menor.get(categoria, '—')} com {_fmt(metrica, menor['_valor'])}.")
    return out


def _analise_variacao(df: pl.DataFrame) -> list[str]:
    col = "variacao" if "variacao" in df.columns else _primeira_coluna(df, ("delta_share_pp", "efeito_volume", "efeito_preco"))
    if not col:
        return []
    d = _com_valor(df, col)
    if d.height == 0:
        return []
    cat = _coluna_categoria(d) or "rotulo"
    positivas = d.filter(pl.col("_valor") > 0).sort("_valor", descending=True)
    negativas = d.filter(pl.col("_valor") < 0).sort("_valor")
    out = []
    if positivas.height:
        r = positivas.head(1).to_dicts()[0]
        out.append(f"Maior contribuição positiva: {r.get(cat, '—')} com {_fmt(col, r['_valor'])}.")
    if negativas.height:
        r = negativas.head(1).to_dicts()[0]
        out.append(f"Maior pressão negativa: {r.get(cat, '—')} com {_fmt(col, r['_valor'])}.")
    total = float(d["_valor"].sum() or 0)
    out.append(f"Soma das variações exibidas: {_fmt(col, total)}.")
    return out


def _analise_relacao(df: pl.DataFrame, colunas: list[str], primaria: str) -> list[str]:
    candidatas = [c for c in colunas if c != primaria]
    if not candidatas:
        return []
    segunda = candidatas[0]
    pares = df.select(
        pl.col(primaria).cast(pl.Float64, strict=False).alias("_a"),
        pl.col(segunda).cast(pl.Float64, strict=False).alias("_b"),
    ).drop_nulls()
    if pares.height < 4:
        return []
    try:
        corr = pares.select(pl.corr("_a", "_b")).item()
    except Exception:  # noqa: BLE001
        return []
    if corr is None or not isfinite(float(corr)):
        return []
    corr = float(corr)
    intensidade = "forte" if abs(corr) >= 0.7 else ("moderada" if abs(corr) >= 0.4 else "fraca")
    direcao = "positiva" if corr >= 0 else "negativa"
    return [
        f"Relação entre {_rotulo(primaria)} e {_rotulo(segunda)}: correlação {direcao} {intensidade} ({corr:.2f})."
    ]


def _analise_correlacao(df: pl.DataFrame) -> list[str]:
    d = _com_valor(df, "correlacao").with_columns(pl.col("_valor").abs().alias("_abs"))
    if d.height == 0:
        return []
    melhor = d.sort("_abs", descending=True).head(1).to_dicts()[0]
    lag = melhor.get("defasagem_meses", "—")
    corr = float(melhor["_valor"] or 0)
    direcao = "positiva" if corr >= 0 else "negativa"
    out = [f"Maior correlação em módulo: {_fmt_num(corr, 3)} na defasagem de {lag} mês(es), com direção {direcao}."]
    if "meses_comparados" in melhor:
        out.append(f"Cálculo feito sobre {int(melhor['meses_comparados'] or 0)} meses comparáveis nessa defasagem.")
    return out


def _colunas_numericas(df: pl.DataFrame) -> list[str]:
    colunas = []
    for c in df.columns:
        if c in IGNORAR_NUMERICAS or c.startswith("_"):
            continue
        if _valores_numericos(df, c):
            colunas.append(c)
    return colunas


def _coluna_primaria(nome: str, df: pl.DataFrame, spec: GraphSpec, colunas: list[str]) -> str:
    for c in spec.foco:
        if c in colunas:
            return c
    nome_norm = _normalizar(nome)
    preferencias = []
    if "pmv" in nome_norm:
        preferencias.extend(["pmv", "preco_medio", "trigo_preco_medio"])
    if "frete" in nome_norm or "rota" in nome_norm or "logistica" in nome_norm:
        preferencias.extend(["frete_por_ton", "frete", "frete_sobre_receita"])
    if "margem" in nome_norm:
        preferencias.extend(["margem_proxy_pct", "margem_proxy"])
    if "cliente" in nome_norm:
        preferencias.extend(["clientes", "receita_liquida"])
    preferencias.extend(PRIORIDADE_METRICAS)
    for c in preferencias:
        if c in colunas:
            return c
    return colunas[0]


def _coluna_tempo(df: pl.DataFrame) -> str | None:
    for c in COLUNAS_TEMPO:
        if c in df.columns:
            return c
    return None


def _coluna_categoria(df: pl.DataFrame) -> str | None:
    for c in COLUNAS_CATEGORIA:
        if c in df.columns:
            return c
    for c in df.columns:
        if c.startswith("_"):
            continue
        try:
            if not _valores_numericos(df, c):
                return c
        except Exception:  # noqa: BLE001
            continue
    return None


def _valores_numericos(df: pl.DataFrame, coluna: str) -> list[float]:
    try:
        serie = df[coluna].cast(pl.Float64, strict=False).drop_nulls()
    except Exception:  # noqa: BLE001
        return []
    valores: list[float] = []
    for v in serie.to_list():
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if isfinite(f):
            valores.append(f)
    return valores


def _com_valor(df: pl.DataFrame, coluna: str) -> pl.DataFrame:
    return df.with_columns(pl.col(coluna).cast(pl.Float64, strict=False).alias("_valor")).filter(
        pl.col("_valor").is_not_null()
    )


def _ordenar(df: pl.DataFrame, coluna: str) -> pl.DataFrame:
    try:
        return df.sort(coluna)
    except Exception:  # noqa: BLE001
        return df


def _primeira_coluna(df: pl.DataFrame, nomes: tuple[str, ...]) -> str | None:
    return next((c for c in nomes if c in df.columns), None)


def _limitar(linhas: list[str], max_linhas: int = 4) -> list[str]:
    out = []
    vistos = set()
    for linha in linhas:
        if linha and linha not in vistos:
            out.append(linha)
            vistos.add(linha)
        if len(out) >= max_linhas:
            break
    return out or ["Sem padrão numérico relevante detectado neste recorte."]


def _como_ler_generico(fig: go.Figure | None, dados: pl.DataFrame | None) -> str:
    tipo = ""
    if fig and fig.data:
        tipo = str(getattr(fig.data[0], "type", "") or "")
    if tipo == "bar":
        return "Compare o comprimento das barras; valores maiores indicam maior peso da categoria ou do período."
    if tipo == "scatter":
        return "Compare posição no eixo X e Y; pontos isolados sugerem outliers ou perfis diferentes."
    if tipo == "heatmap":
        return "Cores mais intensas indicam valores maiores; leia por linha e por coluna para achar padrões."
    if tipo == "waterfall":
        return "Barras positivas e negativas explicam a contribuição de cada categoria para o total."
    if tipo == "treemap":
        return "A área de cada bloco é proporcional ao valor; blocos maiores concentram mais do total."
    if dados is not None and _coluna_tempo(dados):
        return "Leia da esquerda para a direita para entender tendência, picos e quedas."
    return "Compare os maiores e menores valores e use a tabela do gráfico para validar a leitura."


def _fmt(coluna: str, valor: Any) -> str:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "—"
    c = _normalizar(coluna)
    if "pct" in c or "percent" in c:
        return _fmt_pct(v)
    if "share" in c or c.endswith("pp"):
        return f"{_fmt_num(v, 1)} p.p."
    if c == "correlacao":
        return _fmt_num(v, 3)
    if any(k in c for k in (
        "receita", "frete", "custo", "cus", "margem", "desconto", "valor",
        "pmv", "preco", "ticket", "spread", "r$/t", "rs_por_ton", "orcado",
        "realizado",
    )):
        sufixo = "/t" if any(k in c for k in (
            "pmv", "por ton", "r$/t", "rs_por_ton", "preco medio", "spread", "cus",
        )) else ""
        sinal = "-" if v < 0 else ""
        return f"{sinal}R$ {_fmt_num(abs(v), 2)}{sufixo}"
    if any(k in c for k in ("ton", "volume")):
        return f"{_fmt_num(v, 1)} t"
    if any(k in c for k in ("clientes", "documentos", "produtos", "notas", "positivados", "ativos", "novos", "reativados")):
        return _fmt_num(v, 0)
    return _fmt_num(v, 2)


def _fmt_num(v: float, casas: int = 2) -> str:
    return f"{v:,.{casas}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _fmt_pct(v: float | None) -> str:
    return "—" if v is None else f"{_fmt_num(v, 1)}%"


def _fmt_delta_pct(v: float | None) -> str:
    if v is None:
        return "sem base comparável"
    sinal = "+" if v >= 0 else ""
    return f"{sinal}{_fmt_pct(v)}"


def _pct(inicio: float, fim: float) -> float | None:
    if abs(inicio) < 1e-12:
        return None
    return 100 * (fim - inicio) / abs(inicio)


def _rotulo(coluna: str) -> str:
    nomes = {
        "receita_liquida": "receita líquida",
        "vendas_brutas": "vendas brutas",
        "ton_liquida": "volume líquido",
        "frete_por_ton": "frete por tonelada",
        "frete_sobre_receita": "frete sobre receita",
        "margem_proxy_pct": "margem proxy %",
        "custo_por_ton": "custo por tonelada",
        "spread_por_ton": "spread por tonelada",
        "vlrtot_positivados": "receita dos positivados",
        "perc_positivados_geral": "participação dos positivados",
        "taxa_recompra_pct": "taxa de recompra",
        "sem_recompra_pct": "sem recompra",
        "retencao_pct": "retenção",
        "diff_pct": "divergência %",
    }
    return nomes.get(coluna, coluna.replace("_", " ").replace("pct", "%"))


def _normalizar(texto: str) -> str:
    mapa = str.maketrans("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
    return texto.translate(mapa).lower().replace("—", "-").strip()
