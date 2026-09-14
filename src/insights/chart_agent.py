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
    # --- VISÃO GERAL & DESEMPENHO MACRO ---
    "receita_volume": GraphSpec(
        "Monitorar o ritmo conjunto de faturamento financeiro (R$) e tonelagem física expedida (t). Revela a dinâmica de repasse de preços e a qualidade do crescimento da moagem.",
        "A linha representa a Receita Líquida (R$) e as barras representam o Volume (t). Se a receita sobe mais rápido que o volume, houve ganho de PMV (repasse de preços); se o volume cresce mas a receita estagna, o moinho está concedendo descontos excessivos ou vendendo produtos de menor valor agregado (ex.: farelo vs. farinhas especiais).",
        ("receita_liquida", "ton_liquida"),
    ),
    "pmv": GraphSpec(
        "Acompanhar o Preço Médio de Venda por tonelada (R$/t) consolidado da empresa ao longo dos meses. É o principal termômetro de rentabilidade e poder de precificação do moinho.",
        "O eixo vertical mostra o PMV em R$/t faturado. Quedas persistentes de PMV indicam pressão concorrencial de outros moinhos ou mudança no mix para farinhas comuns/farelo. Subidas de PMV devem ser comparadas com o custo de reposição do trigo em grão.",
        ("pmv",),
    ),
    "mix_volume": GraphSpec(
        "Analisar como as diferentes famílias de produtos (Farinhas Industriais 25/50kg, Granel, Pré-Misturas, Doméstica e Farelo) disputam a capacidade instalada de moagem.",
        "A área 100% empilhada mostra a fatia relativa de cada categoria no volume total moído. Uma fábrica eficiente busca maximizar a participação de farinhas nobres e pré-misturas de alto valor, mantendo farinhas industriais para volume base e diluição do custo fixo de moagem.",
        ("ton_liquida",),
    ),
    "mix_receita": GraphSpec(
        "Avaliar a composição do faturamento financeiro por categoria de produto, medindo a dependência da receita em relação a cada família de farinhas.",
        "A área 100% empilhada expressa a participação percentual de cada categoria no faturamento em R$. Permite verificar se o crescimento financeiro está sendo puxado por produtos nobres ou se a receita está excessivamente vulnerável a commodities de margem estreita.",
        ("receita_liquida",),
    ),
    "variacao_classificacao": GraphSpec(
        "Decompor a variação da receita contra o período anterior entre Efeito Volume (vendeu mais ou menos sacas) e Efeito Preço (vendeu mais caro ou mais barato por saca).",
        "Gráfico Waterfall (cascata): barras verdes para cima aumentam a receita; barras vermelhas para baixo reduzem. A barra final consolida o resultado líquido. Permite identificar se uma família de farinhas cresceu por esforço comercial em novas padarias ou por reajuste de tabela.",
        ("variacao", "efeito_volume", "efeito_preco"),
    ),

    # --- GESTÃO DO MIX & DIÁRIO ---
    "receita_diaria": GraphSpec(
        "Acompanhar a curva de faturamento diário ao longo do mês corrente para diagnosticar a regularidade de compras das padarias e distribuidores.",
        "O eixo horizontal mostra os dias do mês e o vertical o faturamento em R$. Concentração excessiva de faturamento nos últimos 5 dias úteis ('efeito final de mês') aponta retenção de pedidos por RCAs e gera gargalos na frota de expedição e carregamento.",
        ("receita_liquida",),
    ),
    "delta_mix": GraphSpec(
        "Medir o ganho ou perda de participação de mercado interno (em pontos percentuais de share de volume) de cada linha de produto entre dois períodos comparados.",
        "Barras positivas indicam famílias de produtos que expandiram sua relevância na moagem; barras negativas mostram perda de espaço. Ideal para validar se estratégias de lançamento (ex.: pré-misturas especiais) estão ganhando tração real.",
        ("delta_share_pp",),
    ),
    "orcado_realizado": GraphSpec(
        "Confrontar o faturamento real realizado contra a meta orçada da diretoria comercial por categoria de produto.",
        "Barras emparelhadas comparam Orçado (azul) vs. Realizado (amarelo) mês a mês. Variações negativas demandam intervenção imediata da gerência comercial regional na respectiva linha de produtos.",
        ("REALIZADO", "ORÇADO"),
    ),

    # --- VENDAS & POLÍTICA COMERCIAL ---
    "vendas_devolucoes": GraphSpec(
        "Monitorar o volume financeiro e físico de devoluções e recusas de carga em confronto com as vendas brutas faturadas.",
        "A linha azul representa Vendas Brutas e as barras vermelhas mostram Devoluções. No setor de farinha de trigo, devoluções elevadas apontam problemas graves: sacaria rasgada no transporte, umidade/infestação no lote, atraso de entrega em padarias ou desvio de especificação técnica (teor de cinzas/glúten).",
        ("vendas_brutas", "devolucoes"),
    ),
    "pmv_desconto": GraphSpec(
        "Cruzar o Preço Médio de Venda (R$/t) praticado com o volume total de descontos comerciais concedidos pela equipe de vendas.",
        "A linha mostra a trajetória do PMV e as barras mostram o valor de descontos concedidos. Se os descontos aumentam enquanto o PMV despenca, a equipe comercial está sacrificando margem da empresa para bater metas volumétricas.",
        ("pmv", "desconto"),
    ),
    "dispersao_vendas": GraphSpec(
        "Mapear cada transação comercial por volume faturado e preço unitário para auditar a consistência da política de preços do moinho.",
        "Cada ponto é uma venda. Revela dispersões injustificadas: se clientes pequenos compram farinha mais barato que grandes indústrias consumidoras de volume, a tabela de preços está descontrolada.",
        ("ton_liquida", "pmv"),
    ),

    # --- RCAs & GESTÃO DA FORÇA DE VENDAS ---
    "quadrante_vendedores": GraphSpec(
        "Segmentar os representantes comerciais (RCAs) em quatro quadrantes de eficiência, cruzando volume financeiro gerado contra a margem ou PMV praticado.",
        "As linhas tracejadas representam as medianas da equipe. O quadrante superior direito reúne os RCAs 'Campeões' (alto volume e alta rentabilidade). O inferior direito aponta 'Tiradores de Pedido' (alto volume com margem destruída por desconto). O superior esquerdo indica 'Especialistas de Nicho'.",
        ("receita_liquida", "margem_proxy_pct"),
    ),
    "evolucao_vendedores": GraphSpec(
        "Rastrear a série histórica de faturamento dos principais RCAs para avaliar estabilidade, sazonalidade e risco de perda de carteira.",
        "Linhas temporais individuais mostram a consistência de cada vendedor. Quedas contínuas em um RCA apontam perda de clientes para concorrentes regionais ou desmotivação do representante.",
        ("receita_liquida",),
    ),
    "concentracao_carteira": GraphSpec(
        "Avaliar o grau de dependência da carteira de cada RCA em relação aos seus maiores clientes compradores.",
        "Barras indicam a fatia do faturamento gerada pelos 3 maiores clientes do RCA. Vendedores com mais de 70% de concentração em 1 ou 2 clientes representam alto risco operacional para o moinho.",
        ("participacao_top3",),
    ),

    # --- CLIENTES, COORTES & SAÚDE DA BASE ---
    "movimento_base": GraphSpec(
        "Acompanhar a saúde da base ativa de padarias e indústrias compradoras: Clientes Ativos Recorrentes, Novos Entrantes e Clientes Reativados.",
        "Barras empilhadas mostram a composição da base mês a mês. Se a base cresce apenas por novos clientes mas a taxa de inativação (churn) é alta, o moinho tem um 'balde furado' comercial.",
        ("ativos", "novos", "reativados"),
    ),
    "matriz_clientes": GraphSpec(
        "Priorizar a carteira de clientes cruzando Participação no Faturamento (% Share) contra Taxa de Crescimento/Queda de Compras.",
        "Eixo X: Tamanho do cliente. Eixo Y: Variação percentual de compras. Clientes no quadrante inferior direito (grandes padarias comprando menos) exigem visita técnica e comercial imediata da gerência.",
        ("participacao_pct", "variacao_pct", "valor_b"),
    ),
    "rfm_scatter": GraphSpec(
        "Segmentar os clientes pelo modelo RFM (Recência da última compra, Frequência de pedidos e Valor financeiro total acumulado).",
        "Eixo X: Dias sem comprar (Recência). Eixo Y: Quantidade de meses com compras (Frequência). Tamanho da bolha: Faturamento. Separa clientes fiéis, contas em risco de abandono e compradores eventuais.",
        ("recencia_dias", "frequencia_meses", "receita", "score_total"),
    ),
    "cross_sell": GraphSpec(
        "Mapear o potencial de ampliação de catálogo (cross-sell) em clientes que atualmente compram apenas um único tipo de produto.",
        "Identifica clientes industriais e padarias de alto volume que compram apenas Farinha Comum, abrindo oportunidade para os RCAs ofertarem Pré-Misturas, Farinhas Integrais ou Farelo de Trigo.",
        ("produtos", "receita_liquida", "ton_liquida"),
    ),
    "positivados_mes": GraphSpec(
        "Medir a taxa de abertura de novas contas comerciais (primeira compra histórica no Moinho) em cada mês.",
        "Cada barra representa a safra (coorte) de novos clientes conquistados. Permite avaliar a efetividade de campanhas de prospecção e expansão de território.",
        ("positivados",),
    ),
    "matriz_retencao": GraphSpec(
        "Matriz de Sobrevivência de Coortes: mede que percentual dos clientes recém-abertos continuam comprando no 2º, 3º, 6º e 12º mês após a primeira compra.",
        "Heatmap onde as linhas são as safras de entrada e as colunas são os meses de vida. Cores mais quentes na diagonal indicam clientes fidelizados; desbotamento rápido aponta problemas no primeiro pedido ou ataque da concorrência.",
        ("retencao_pct",),
    ),
    "taxa_recompra": GraphSpec(
        "Avaliar a velocidade e fidelidade de recompra das padarias e indústrias recém-conquistadas.",
        "Mede o percentual de clientes de cada safra que efetuaram uma 2ª compra em até 30, 60 ou 90 dias. No mercado de farinha, quem não recompra no segundo mês raramente volta.",
        ("taxa_recompra_pct",),
    ),
    "sem_recompra": GraphSpec(
        "Identificar safras de clientes que compraram apenas uma vez e nunca mais voltaram ('one-shot buyers').",
        "Barras altas sinalizam problemas de experiência do cliente: produto com desempenho ruim na masseira, atraso no prazo de entrega ou concessão pontual de preço sem continuidade de relacionamento.",
        ("sem_recompra_pct",),
    ),

    # --- CUSTOS & MARGEM PROXY ---
    "comparar_custos": GraphSpec(
        "Confrontar a trajetória do PMV da farinha contra os diferentes conceitos de custo da empresa (CUSGER, CUSVARIAVEL, CUSTOPROD).",
        "Linhas temporais lado a lado mostram a evolução do custo por tonelada frente à receita. Revela a sensibilidade da margem da moagem a variações nos insumos e energia.",
        ("pmv", "cusger", "cusvariavel"),
    ),
    "custo_pmv_produto": GraphSpec(
        "Cruzar Custo Unitário por Tonelada (R$/t) contra PMV (R$/t) SKU a SKU para auditar o spread de cada produto do portfólio.",
        "Pontos posicionados acima da linha de custo representam produtos saudáveis; produtos abaixo ou muito próximos da linha operam no prejuízo ou margem perigosamente comprimida.",
        ("custo_por_ton", "pmv", "margem_proxy_pct"),
    ),
    "spread": GraphSpec(
        "Monitorar o Spread Unitário (Preço Médio de Venda menos Custo por Tonelada em R$/t) mês a mês.",
        "Barras verdes mostram folga financeira por tonelada moída; barras em declínio acendem alerta para reajuste de tabela ou revisão de contratos de fornecimento.",
        ("spread_por_ton",),
    ),
    "margem_pct": GraphSpec(
        "Acompanhar a Margem Proxy percentual calculada sobre a receita líquida de farinha ao longo do tempo.",
        "A curva percentual expressa a rentabilidade média da operação comercial sob a base de custo selecionada no filtro lateral.",
        ("margem_proxy_pct",),
    ),

    # --- LOGÍSTICA & FRETES ---
    "frete_mensal": GraphSpec(
        "Acompanhar o valor total de frete alocado às entregas de farinha e o custo logístico médio por tonelada transportada (R$/t).",
        "As barras mostram o desembolso total com transportadoras e a linha vermelha expressa o Frete R$/t. Subidas no R$/t sem aumento proporcional de volume indicam envio de cargas fracionadas ou rotas ineficientes.",
        ("frete", "frete_por_ton"),
    ),
    "frete_receita": GraphSpec(
        "Medir o impacto percentual das despesas de transporte rodoviário sobre o faturamento líquido da empresa (% Frete/Receita).",
        "O frete é uma das maiores linhas de custo da moagem (normalmente entre 7% e 14% da receita). Variações para cima reduzem diretamente a margem operacional líquida do Moinho.",
        ("frete_sobre_receita",),
    ),
    "rotas_caras": GraphSpec(
        "Identificar os pares de Origem-Destino e municípios com o maior custo de frete por tonelada (R$/t) pago a terceiros.",
        "Barras em ordem decrescente destacam as rotas que mais encarecem a entrega da saca de farinha, orientando a renegociação de tabelas de frete ou revisão da política FOB/CIF.",
        ("frete_por_ton",),
    ),
    "rotas_frete": GraphSpec(
        "Listar as rotas e destinos que concentram o maior valor absoluto em Reais (R$) gasto com frete.",
        "Permite focar as negociações com transportadores nos trajetos de maior volume financeiro da malha logística.",
        ("frete",),
    ),
    "dispersao_carga": GraphSpec(
        "Avaliar a penalidade de custo de entregas fracionadas: cruza o peso da carga faturada contra o frete unitário por tonelada (R$/t).",
        "Pontos no canto superior esquerdo (cargas de 1 a 5 toneladas pagando alto R$/t) comprovam a ineficiência de entregas pequenas e justificam a exigência de pedido mínimo para frete CIF.",
        ("ton", "frete_por_ton", "frete"),
    ),

    # --- MATÉRIA-PRIMA: TRIGO EM GRÃO ---
    "series_trigo": GraphSpec(
        "Analisar o ciclo de repasse de custos: correlaciona o preço de compra do trigo em grão (R$/t) com os custos de produção e o PMV praticado na saca de farinha.",
        "Permite diagnosticar a defasagem temporal (lag de 30 a 90 dias) necessária para que altas ou baixas no mercado de commodities de trigo sejam absorvidas no preço final de venda.",
        ("trigo_preco_medio", "pmv", "cusger_por_ton"),
    ),
    "base_100": GraphSpec(
        "Comparar a velocidade relativa de variação entre o Preço do Trigo, Custo de Moagem e Preço da Farinha com base normalizada em 100.",
        "Todas as séries iniciam em 100 no primeiro mês. Se a linha do trigo sobe 20% e a da farinha sobe apenas 5%, o moinho está absorvendo o custo e comprimindo sua margem.",
        (),
    ),
    "compra_trigo": GraphSpec(
        "Acompanhar as compras mensais de trigo em grão (toneladas) para garantir o abastecimento contínuo da moagem.",
        "Picos de compras indicam momentos de estocagem estratégica aproveitando janelas de preços favoráveis na safra nacional ou importada.",
        ("trigo_ton_comprada",),
    ),
    "estoque_trigo": GraphSpec(
        "Monitorar o volume físico de trigo em grão armazenado nos silos da planta industrial.",
        "Garante visibilidade sobre a autonomia de moagem (dias de estoque) para evitar paradas não planejadas da fábrica.",
        ("trigo_ton_estoque",),
    ),

    # --- POTENCIAL DE MERCADO & EXPANSÃO EM MINAS GERAIS (ESTUDO ESTRATÉGICO) ---
    "c2_quadrante_rca": GraphSpec(
        "Avaliar a produtividade real de cada RCA: confronta o Potencial Econômico do Território recebido (demanda estimada em t/mês) contra a Venda Real entregue (t/mês).",
        "Eixo X: Potencial total do território em t/mês. Eixo Y: Venda média realizada em t/mês. Tamanho da bolha: Qtd de cidades atribuídas na planilha. Cor: % de ativação de cidades. Vendedores acima da diagonal extraem alta fatia do território; abaixo da diagonal revelam carteiras inchadas e subaproveitadas.",
        ("teto_t_mes", "venda_t_mes", "cidades_atribuidas", "ativacao_pct"),
    ),
    "c2_territorio": GraphSpec(
        "Mapear a intensidade de cobertura pretendida pela empresa em cada município de MG com base na planilha de representação comercial.",
        "Cores mais escuras indicam municípios com múltiplos RCAs cadastrados; áreas em cinza claro evidenciam municípios sem nenhum responsável formal designado.",
        ("qtd_representantes",),
    ),
    "pareto_cidades_mg": GraphSpec(
        "Medir o grau de concentração geográfica das vendas de farinha entre os 853 municípios de Minas Gerais.",
        "As barras mostram o volume vendido por município e a linha vermelha acumula o percentual. Evidencia que a maior parte das toneladas está concentrada em poucos centros urbanos e que o interior permanece inexplorado.",
        ("ton_farinha",),
    ),
    "c3_potencial": GraphSpec(
        "Estimar a demanda total de consumo de farinha de trigo (t/mês) de cada cidade mineira baseada no cadastro oficial de empresas do IBGE/CEMPRE.",
        "Calcula o consumo econômico real multiplicando a contagem de padarias, confeitarias, fábricas de massas e atacados pelos coeficientes de consumo observados na operação do Moinho.",
        ("teto_t_mes",),
    ),
    "c3_teto_segmentos": GraphSpec(
        "Identificar quais segmentos produtivos geram maior demanda de farinha no estado de MG.",
        "Compara o volume capturável entre Panificação Tradicional (sacaria), Indústria de Biscoitos/Massas (granel/sacos) e Atacados/Distribuidores (food service) para direcionar o foco do portfólio fabril.",
        ("teto_t_mes", "estabelecimentos"),
    ),
    "white_space_mapa": GraphSpec(
        "Classificar os 853 municípios de MG nos 4 quadrantes estratégicos da Matriz Potencial × Presença de Vendas.",
        "Separa o estado em: White Space Prioritário (Alto Potencial, Baixa Presença - Alvo de Expansão), Território Consolidado (Alto Potencial, Alta Venda - Defesa de Carteira), Mercado de Nicho e Baixa Prioridade.",
        ("quadrante", "teto_t_mes", "venda_t_mes"),
    ),
    "cidades_prioritarias": GraphSpec(
        "Ranquear as 15 cidades com maior volume absoluto de espaço não atendido (White Space) em Minas Gerais.",
        "Lista os municípios prioritários onde a diferença entre o mercado consumidor existente e a venda atual do Moinho é máxima, orientando a abertura imediata de novas rotas comerciais.",
        ("espaco_t_mes", "teto_t_mes", "venda_t_mes"),
    ),
    "reconciliacao_mensal": GraphSpec(
        "Conferir a aderência e reconciliação mensal entre o modelo de dados analítico e os relatórios gerenciais da empresa.",
        "Linha de divergência percentual (diff %). Picos fora da margem de tolerância exigem auditoria antes da apresentação de números à diretoria.",
        ("diff_pct",),
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



TITULOS_SECOES: dict[str, str] = {
    # --- VISÃO GERAL ---
    "receita e volume": (
        "**🎯 Racional do Moinho:** Confronta o faturamento bruto em R$ com a tonelagem de farinha e subprodutos entregues.\n\n"
        "**📊 Como Ler:** Linha = Receita Líquida (R$); Barras = Volume (t). Se a receita sobe descolada do volume, o moinho teve ganho de PMV (reajuste de preço de saca). Se o volume sobe e a receita cai, houve queima de preço por descontos ou escoamento de farelo/farinhas de baixo valor."
    ),
    "pmv mensal": (
        "**🎯 Racional do Moinho:** Preço Médio de Venda por tonelada (R$/t) da farinha. É o indicador vital da saúde financeira da moagem.\n\n"
        "**📊 Como Ler:** Acompanhe a trajetória mensal frente ao custo do trigo em grão. Quedas contínuas em meses de safra apontam incapacidade de repassar custos ou perda de competitividade frente a outros moinhos."
    ),
    "mix por classificacao": (
        "**🎯 Racional do Moinho:** Como as famílias de produto (Farinha Panificação 25/50kg, Granel, Pré-Misturas, Doméstica e Farelo) dividem a capacidade de moagem da planta.\n\n"
        "**📊 Como Ler:** Área 100% empilhada. O objetivo da gestão é ampliar o espaço de Farinhas Especiais e Pré-Misturas (maior margem) sem perder a base de farinhas industriais que garante a diluição do custo fixo da fábrica."
    ),
    "maiores variacoes vs. periodo anterior": (
        "**🎯 Racional do Moinho:** Decomposição da variação da receita entre Efeito Volume (vendeu mais sacas) e Efeito Preço (vendeu saca mais cara).\n\n"
        "**📊 Como Ler:** Gráfico Cascata. Barras verdes aumentam a receita; barras vermelhas reduzem. Revela se o crescimento do período veio de esforço comercial de positivação ou de repasse inflacionário de tabela."
    ),

    # --- POTENCIAL DE MERCADO MG (ESTUDO ESTRATÉGICO) ---
    "as tres camadas, lado a lado": (
        "**🎯 Racional do Moinho:** Visão tridimensional integrada do estado de Minas Gerais.\n\n"
        "**📊 Como Ler:**\n"
        "• Camada 1 (Verde): Venda Real observada (onde o Moinho entrega farinha hoje).\n"
        "• Camada 2 (Roxo): Território Declarado dos RCAs (onde a empresa acha que tem cobertura comercial).\n"
        "• Camada 3 (Laranja): Potencial de Mercado (onde estão as padarias, confeitarias e indústrias cadastradas no IBGE)."
    ),
    "concentracao: quanto do negocio depende de quao poucas cidades": (
        "**🎯 Racional do Moinho:** Curva de Pareto municipal da farinha de trigo em MG.\n\n"
        "**📊 Como Ler:** As barras mostram as toneladas vendidas por cidade em ordem decrescente; a linha mostra o percentual acumulado. Identifica quantas poucas cidades concentram 80% da farinha do moinho e expõe a dependência territorial da operação."
    ),
    "camada 2 · territorio declarado dos representantes": (
        "**🎯 Racional do Moinho:** Malha de cobertura pretendida com base na planilha de representação comercial.\n\n"
        "**📊 Como Ler:** Representa a intenção de atendimento comercial. Municípios em roxo escuro possuem múltiplos RCAs cadastrados (risco de canibalização); municípios cinzas não possuem nenhum vendedor responsável designado."
    ),
    "territorio recebido x resultado obtido": (
        "**🎯 Racional do Moinho:** Quadrante de produtividade real do RCA no mercado de farinha.\n\n"
        "**📊 Como Ler:**\n"
        "• Eixo X: Potencial estimado de farinha nas cidades do RCA (t/mês).\n"
        "• Eixo Y: Venda média mensal entregue (t/mês).\n"
        "• Tamanho da bolha: Qtd de cidades atribuídas.\n"
        "• Cor: % de cidades ativadas com compra.\n"
        "• Vendedores ACIMA da diagonal são altamente eficientes na conversão da carteira; ABAIXO da diagonal possuem territórios inchados e subaproveitados."
    ),
    "lacunas entre territorio e realidade": (
        "**🎯 Racional do Moinho:** Diagnóstico de desalinhamento entre o cadastro comercial e as entregas reais de farinha.\n\n"
        "**📊 Como Ler:**\n"
        "• Aba Órfãos: Municípios com padarias ativas, sem venda do Moinho e sem RCA designado (White Space puro para contratação de representantes).\n"
        "• Aba Venda sem Dono: Municípios com faturamento ativo onde nenhum RCA declarou atender a praça (vendas diretas da mesa ou RCA vendendo fora da sua rota).\n"
        "• Aba Atribuídos sem Venda: Municípios na carteira do RCA onde não houve 1 saca de farinha vendida (território travado para cobrança de positivação)."
    ),
    "segmentos: onde esta o volume e por qual canal ele se alcanca": (
        "**🎯 Racional do Moinho:** Estratificação da demanda de farinha de MG pelos canais de consumo.\n\n"
        "**📊 Como Ler:** Compara o volume demandado entre Panificação Tradicional (sacaria 25/50kg), Indústrias de Biscoitos/Massas (granel/sacos) e Atacados/Distribuidores (food service) para orientar o foco da produção e embalagem."
    ),
    "as 15 cidades de maior espaco nao atendido": (
        "**🎯 Racional do Moinho:** Ranking dos maiores alvos comerciais em potencial de farinha não capturado em MG.\n\n"
        "**📊 Como Ler:** Lista os municípios onde a lacuna entre o consumo estimado das padarias e as vendas atuais do Moinho é maior, orientando a expansão imediata de rotas e abertura de novos clientes."
    ),
    "as quatro regioes que concentram o espaco": (
        "**🎯 Racional do Moinho:** Agrupamento regional do potencial de farinha em MG por Regiões Intermediárias do IBGE.\n\n"
        "**📊 Como Ler:** Identifica as macrorregiões do estado que concentram a maior oportunidade em volume de toneladas/mês para direcionar investimentos em centros de distribuição e logística."
    ),

    # --- VENDAS, PREÇOS & DESCONTOS ---
    "vendas x devolucoes": (
        "**🎯 Racional do Moinho:** Auditoria de recusas e retornos de mercadoria na entrega de farinha.\n\n"
        "**📊 Como Ler:** Linha = Vendas Brutas (R$); Barras Vermelhas = Devoluções. Devoluções elevadas indicam falhas graves: sacaria rasgada na carga/descarga, umidade/infestação no lote, atraso de entrega em padarias ou lote fora da especificação técnica de panificação (W/glúten/cinzas)."
    ),
    "pmv e desconto": (
        "**🎯 Racional do Moinho:** Avalia se a força de vendas está sustentando o preço de tabela ou 'queimando margem' com concessão de descontos.\n\n"
        "**📊 Como Ler:** Linha = PMV (R$/t); Barras = Descontos (R$). Se os descontos sobem enquanto o PMV despenca, a equipe comercial está sacrificando a rentabilidade do moinho para bater metas volumétricas de sacas."
    ),
    "dispersao de preco": (
        "**🎯 Racional do Moinho:** Consistência da política comercial e precificação por cliente/transação.\n\n"
        "**📊 Como Ler:** Cada ponto é uma venda de farinha. Revela distorções graves: se padarias pequenas estão pagando preço unitário menor do que grandes compradores industriais de volume, a tabela de preços do moinho está descalibrada."
    ),

    # --- RCAs & REPRESENTANTES COMERCIAIS ---
    "scorecard por vendedor": (
        "**🎯 Racional do Moinho:** Painel executivo consolidado de produtividade comercial por RCA.\n\n"
        "**📊 Como Ler:** Avalie em conjunto Receita, Volume (t), PMV (R$/t), Quantidade de Clientes Ativos e Devoluções para separar vendedores de alta performance e valor daqueles focados apenas em commodities de margem baixa."
    ),
    "quadrante de vendedores": (
        "**🎯 Racional do Moinho:** Segmentação estratégica da força de vendas em 4 quadrantes de rentabilidade e volume.\n\n"
        "**📊 Como Ler:** As linhas tracejadas dividem a equipe pelas medianas. Identifica os 'Vendedores Campeões' (alto volume e alta margem/PMV), 'Tiradores de Pedido' (alto volume com margem destruída) e 'Vendedores de Nicho'."
    ),

    # --- CLIENTES & COORTES ---
    "matriz de clientes": (
        "**🎯 Racional do Moinho:** Priorização da carteira de padarias e indústrias por Tamanho e Tendência de Compra.\n\n"
        "**📊 Como Ler:** Clientes no quadrante inferior direito (grandes compradores de farinha com compras em queda) exigem intervenção imediata da gerência comercial para evitar a perda da conta para a concorrência."
    ),
    "segmentacao rfm": (
        "**🎯 Racional do Moinho:** Segmentação comportamental da carteira por Recência, Frequência e Valor Financeiro.\n\n"
        "**📊 Como Ler:** Identifica contas leais de recompra semanal (padarias ativas), clientes com risco iminente de perda (recência alta) e compradores esporádicos de preço."
    ),
    "amplitude de mix e cross-sell": (
        "**🎯 Racional do Moinho:** Oportunidades de diversificação de portfólio no mesmo cliente comprador.\n\n"
        "**📊 Como Ler:** Identifica padarias de alto consumo que compram apenas Farinha Industrial Comum, abrindo espaço para os RCAs ofertarem Pré-Misturas (pão francês, pão de queijo, bolos) e Farinhas Especiais."
    ),

    # --- CUSTOS, FRETES & TRIGO ---
    "comparacao de conceitos de custo": (
        "**🎯 Racional do Moinho:** Confronto entre o preço de venda da farinha e os conceitos de custo da fábrica (CUSGER, CUSVARIAVEL, CUSTOPROD).\n\n"
        "**📊 Como Ler:** Mostra a folga financeira e a sensibilidade da margem da moagem a variações nos custos de energia, embalagens e insumos industriais."
    ),
    "custo x pmv por produto": (
        "**🎯 Racional do Moinho:** Auditoria de rentabilidade SKU a SKU do catálogo de farinhas.\n\n"
        "**📊 Como Ler:** Produtos acima da linha geram margem saudável; produtos abaixo ou muito próximos da linha operam no prejuízo operacional."
    ),
    "frete mensal": (
        "**🎯 Racional do Moinho:** Acompanhamento do custo logístico total e do valor pago por tonelada transportada (R$/t).\n\n"
        "**📊 Como Ler:** O frete consome de 7% a 14% do faturamento do moinho. Aumentos no R$/t sem aumento de volume indicam envio de cargas fracionadas ou rotas ineficientes."
    ),
    "rotas mais caras": (
        "**🎯 Racional do Moinho:** Identificação das rotas de transporte rodoviário com o maior custo por tonelada.\n\n"
        "**📊 Como Ler:** Destaca trajetos e destinos que mais encarecem a entrega da saca de farinha, direcionando renegociações com transportadores ou exigência de frete FOB."
    ),
    "trigo, custos e pmv": (
        "**🎯 Racional do Moinho:** Dinâmica de repasse da commodity: correlaciona o preço do trigo em grão com o custo e o PMV da farinha.\n\n"
        "**📊 Como Ler:** Permite medir o tempo de defasagem (lag de 30 a 90 dias) necessário para que altas na matéria-prima sejam absorvidas no preço final de venda nas padarias."
    ),
    "matriz potencial x venda": (
        "**🎯 Racional do Moinho:** Confronta a Demanda Potencial estimada (IBGE/CEMPRE) contra as Vendas Reais do Moinho em cada município de MG.\n\n"
        "**📊 Como Ler:**\n"
        "• Eixo X: Consumo estimado de farinha da cidade (t/mês).\n"
        "• Eixo Y: Volume faturado pelo Moinho (t/mês).\n"
        "• Tamanho da bolha: Qtd de estabelecimentos consumidores.\n"
        "• Cor: % de penetração da base.\n"
        "• Canto INFERIOR DIREITO: Cidades de altíssimo consumo de farinha onde o Moinho quase não vende — o principal bolsão de White Space de MG."
    ),
    "mapa de white space de minas gerais": (
        "**🎯 Racional do Moinho:** Classificação territorial estratégica dos 853 municípios de Minas Gerais nos 4 quadrantes de atratividade.\n\n"
        "**📊 Como Ler:**\n"
        "• Vermelho/Laranja: White Space Prioritário (alto potencial de consumo, baixa venda do Moinho — alvo imediato de expansão).\n"
        "• Verde: Território Consolidado (alto potencial, alta venda — foco em defesa e aumento de mix).\n"
        "• Azul: Mercado Maduro/Nicho (baixo potencial, alta venda).\n"
        "• Cinza: Baixo potencial ou sem estabelecimentos consumidores mapeados."
    ),
    "espaco por regiao": (
        "**🎯 Racional do Moinho:** Distribuição do volume de farinha não capturado (t/mês) por Região Intermediária do IBGE.\n\n"
        "**📊 Como Ler:** Barras mais longas indicam macrorregiões onde a lacuna entre a demanda total das padarias e as vendas atuais do Moinho é maior, orientando onde abrir novos canais ou ampliar a equipe de RCAs."
    ),
    "prioridades municipio a municipio": (
        "**🎯 Racional do Moinho:** Matriz detalhada município a município para execução do plano de expansão comercial.\n\n"
        "**📊 Como Ler:** Permite filtrar por quadrante estratégico para obter a lista exata de cidades com maior população, estabelecimentos de panificação e espaço em toneladas/mês para a abordagem dos representantes."
    ),
    "ranking por uf": (
        "**🎯 Racional do Moinho:** Ranking de faturamento e volume físico de farinha expedida por Estado (UF).\n\n"
        "**📊 Como Ler:** Permite mensurar a dependência do Moinho em relação a Minas Gerais versus a penetração em estados vizinhos (SP, RJ, ES, BA)."
    ),
    "ranking municipal": (
        "**🎯 Racional do Moinho:** Ranking dos municípios que lideram o volume de farinha faturada pelo Moinho em MG.\n\n"
        "**📊 Como Ler:** Ordena as cidades de maior expedição física, separando praças consolidadas de cidades com volume residual."
    ),
    "por regiao intermediaria (ibge)": (
        "**🎯 Racional do Moinho:** Consolidação das vendas de farinha pelas 13 Regiões Geográficas Intermediárias de Minas Gerais.\n\n"
        "**📊 Como Ler:** Avalia o equilíbrio da presença comercial da fábrica entre as macrorregiões (Central/BH, Triângulo, Sul de Minas, Zona da Mata, Norte, etc.)."
    ),
}


def explicacao_grafico(nome: str = "", titulo: str = "") -> str:
    """
    Retorna uma explicação didática, executiva e completa do racional por trás do gráfico ou subgráfico.
    Usada para alimentar o tooltip de ajuda '?' nos títulos de gráficos e seções.
    """
    # 1. Busca por título de seção exato ou aproximado no catálogo de inteligência de mercado
    if titulo:
        norm_t = _normalizar(titulo)
        for chave_secao, texto_explicativo in TITULOS_SECOES.items():
            if _normalizar(chave_secao) in norm_t or norm_t in _normalizar(chave_secao):
                return texto_explicativo

    # 2. Busca em EXATOS
    spec = None
    if nome and nome in EXATOS:
        spec = EXATOS[nome]
    elif titulo:
        norm_t = _normalizar(titulo)
        for chave, s in EXATOS.items():
            if _normalizar(chave) in norm_t or norm_t in _normalizar(chave):
                spec = s
                break
        if not spec:
            for prefixo, s in PREFIXOS:
                p_norm = prefixo.replace("_", " ").strip()
                if p_norm and (p_norm in norm_t or norm_t.startswith(p_norm)):
                    spec = s
                    break

    if not spec and nome:
        spec = _spec(nome, None)

    if not spec:
        label = titulo or nome or "indicadores"
        return (
            f"**🎯 Racional do Moinho:**\nMonitora a distribuição e evolução comercial de {label} no segmento de farinhas.\n\n"
            f"**📊 Como Ler:**\nCompare as barras, linhas ou categorias para identificar concentração, dispersão de preços ou oportunidades de positivação regional."
        )

    return (
        f"**🎯 Racional do Moinho:**\n{spec.objetivo}\n\n"
        f"**📊 Como Ler & Interpretar:**\n{spec.como_ler}"
    )


def ajuda_indicador(titulo: str) -> str | None:
    """Ajuda contextual, didática e explicativa para cartões e KPIs."""
    t = _normalizar(titulo)

    # Potencial MG e Territórios
    if "municipios de mg atendidos" in t:
        return "Quantidade de municípios em Minas Gerais com pelo menos 1 nota fiscal faturada na janela. Mede a amplitude geográfica da presença comercial do Moinho."
    if "venda de farinha" in t:
        return "Média mensal de farinha de trigo (em toneladas/mês) efetivamente faturada e entregue no estado. Base: NF-e do ERP Sankhya."
    if "mercado enderecavel" in t or "enderecavel" in t:
        return "Demanda total estimada de farinha de trigo (t/mês) consumida pelas padarias, indústrias e atacados de MG. Base: CEMPRE/IBGE calibrado com dados reais de consumo."
    if "espaco nao atendido" in t or "espaco" in t:
        return "Diferença matemática entre o mercado endereçável e o volume que o Moinho já vende (White Space). Representa o potencial de crescimento ainda inexplorado."
    if "populacao sem nenhuma venda" in t:
        return "População total residente nos municípios de MG onde o Moinho não realizou nenhuma venda na janela analisada."
    if "clientes ativos em mg" in t:
        return "Número de compradores com faturamento no estado no período. Mede a base viva de clientes."
    if "estabelecimentos consumidores" in t:
        return "Total de empresas ativas em MG pertencentes aos CNAEs consumidores de farinha (Padarias, Biscoitos, Massas, Atacado). Fonte: IBGE."
    if "venda e sem rca" in t or "sem rca responsavel" in t or "sem dono" in t:
        return "Cidades com faturamento ativo onde nenhum RCA declarou a cidade em sua planilha territorial. Indica venda direta de fábrica, canal mesa ou desatualização cadastral."
    if "rca atribuido e sem venda" in t or "territorio sem venda" in t or "inativo" in t:
        return "Cidades atribuídas formalmente a um RCA na planilha, mas onde não houve nenhuma venda na janela. Indica território inativo para cobrança de ativação."
    if "municipios com rca" in t or "com territorio" in t:
        return "Municípios de MG que possuem pelo menos 1 representante comercial designado pela planilha de territórios da empresa."
    if "sem rca e sem venda" in t:
        return "Cidades onde a empresa não possui RCA designado e não realiza vendas (White Space puro para novas contratações ou rotas)."

    # Faturamento e Vendas
    if "receita liquida" in t:
        return "Faturamento líquido no grão de item (VLRTOT menos devoluções e abatimentos). Mede o valor financeiro real retido pela empresa."
    if "vendas brutas" in t:
        return "Faturamento faturado bruto antes de abater devoluções. Permite avaliar o volume original faturado antes de retornos."
    if "receita total" in t or "receita" in t:
        return "Volume financeiro total observado no recorte selecionado. Analise junto com toneladas e clientes para avaliar a qualidade do faturamento."
    if "devolu" in t:
        return "Valor financeiro ou físico de itens devolvidos pelo cliente. Preserva o sinal negativo original da transação fiscal."
    if "volume" in t or "tonelada" in t:
        return "Volume físico de farinha e subprodutos em toneladas líquidas (TONLIQ). Devoluções reduzem a tonelagem proporcionalmente."
    if t == "pmv" or "pmv " in t or "pmv medio" in t:
        return "Preço Médio de Venda por tonelada (R$/t): Receita Líquida dividida pelo Volume em toneladas (exclui bonificações sem valor)."

    # Clientes e Coortes
    if "clientes ativos" in t or t == "clientes":
        return "Contagem de CNPJs/CPFs distintos com compras no recorte. Mede a ativação real da carteira."
    if "clientes novos" in t or "positivado" in t:
        return "Clientes que realizaram sua primeira compra histórica na empresa neste período. É a porta de entrada de novas safras (coortes)."
    if "documentos" in t:
        return "Quantidade de notas fiscais (NUNOTA) emitidas. Mede a densidade operacional de faturamento."
    if "produtos" in t:
        return "Quantidade de SKUs distintos faturados. Avalia a amplitude e dispersão do catálogo no cliente ou região."
    if "desconto" in t:
        return "Soma dos descontos comerciais concedidos (VLRDESC). Avalia a pressão sobre o preço de tabela."

    # Logística e Frete
    if "frete total" in t:
        return "Valor total faturado pelos transportadores nos CT-e emitidos. Pode incluir fretes ainda não vinculados a NF-e."
    if "frete alocado" in t:
        return "Valor de frete rateado e vinculado diretamente às notas fiscais de venda por tonelada entregue."
    if "nao alocado" in t:
        return "Parcela do frete de transporte que não encontrou vínculo automático com nota fiscal de venda."
    if "sem nf" in t:
        return "Percentual de conhecimentos de frete (CT-e) sem chave de nota fiscal de venda identificada na base."
    if "sem ordem" in t:
        return "Percentual de CT-e sem ordem de carga vinculada."
    if t == "ct e" or "ct-e" in titulo.lower():
        return "Quantidade de Conhecimentos de Transporte Eletrônico (CT-e) no período."
    if "rotas" in t:
        return "Quantidade de pares distintos de Origem-Destino atendidos pela malha logística da empresa."
    if "r$/t mediano" in t:
        return "Custo mediano de frete por tonelada transportada. A mediana reduz a distorção causada por fretes atípicos de cargas fracionadas."

    # Custos e Margens
    if "custo" in t and "medio" in t:
        return "Custo unitário médio por tonelada na base contábil/gerencial selecionada (ex.: CUSGER, CUSVARIAVEL)."
    if "custo" in t:
        return "Custo total estimado dos produtos faturados na base selecionada. Atenção: conceito de custo em homologação gerencial."
    if "margem proxy" in t:
        return "Margem estimada calculada como Receita Líquida menos o Custo da base selecionada. Trata-se de margem proxy gerencial, não contábil."
    if "spread" in t:
        return "Diferença unitária entre o Preço Médio de Venda (R$/t) e o Custo por tonelada (R$/t). Mede a rentabilidade bruta por tonelada."

    # Carteira e RCAs
    if "vendedores com movimento" in t:
        return "Quantidade de representantes ou vendedores comerciais que emitiram pedidos faturados no período."
    if "maior vendedor" in t or "maior cliente" in t:
        return "Percentual de participação que o principal vendedor ou cliente representa sobre o total do faturamento (medida de risco de concentração)."
    if "top 5" in t:
        return "Percentual do faturamento total que está concentrado nas mãos dos 5 maiores vendedores ou clientes."
    if "recompra" in t:
        return "Percentual de clientes de uma coorte que efetuaram nova compra dentro da janela avaliada (fidelização)."
    if "recencia" in t:
        return "Número de dias corridos desde a última compra realizada pelo cliente. Quanto menor, mais quente e ativo o relacionamento."
    if "frequencia" in t:
        return "Quantidade de meses distintos em que o cliente realizou compras dentro do ano/período."

    # Geral
    if "ticket" in t:
        return "Valor médio faturado por pedido ou nota fiscal (Receita total ÷ Documentos emitidos)."
    if "linhas carregadas" in t:
        return "Volume de registros processados e auditados pelo pipeline de dados analítico."
    if "ultima carga" in t:
        return "Carimbo de data/hora da última atualização bem-sucedida da base de dados."

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
