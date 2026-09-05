"""
Potencial de Mercado — Minas Gerais.

Responde a pergunta que o ranking de vendas nao responde: *onde o Moinho
DEVERIA vender*. Tres camadas sobrepostas no mesmo mapa municipal:

    CAMADA 1  venda por cidade de MG              (o que existe hoje)
    CAMADA 2  territorio declarado dos RCAs       (quem responde por onde)
    CAMADA 3  mercado potencial de farinha        (o que poderia existir)

A sobreposicao das tres produz a matriz de White Space, e dela sai a leitura
de expansao para o proprietario.

Fronteira metodologica desta pagina: as camadas 1 e 2 sao FATO (documento
fiscal e arquivo de territorio). A camada 3 e ESTIMATIVA construida sobre
dados publicos do IBGE e sobre o consumo observado dos proprios clientes.
A pagina nunca mistura as duas naturezas sem dizer qual esta usando.
"""
from __future__ import annotations

import plotly.graph_objects as go
import polars as pl
import streamlit as st

from app.components import ui
from app.state.session import barra_lateral
from src.repositories import geo

st.title("Potencial de Mercado — Minas Gerais")
barra_lateral()

CFG = geo.config()
JANELA_PADRAO = geo.janela_padrao()


# ---------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner="Carregando as três camadas…")
def _carregar(janela: int) -> pl.DataFrame:
    return geo.municipios(janela_meses=janela)


@st.cache_data(ttl=900, show_spinner=False)
def _representantes() -> pl.DataFrame:
    return geo.cobertura_por_representante()


@st.cache_data(ttl=900, show_spinner=False)
def _segmentos() -> pl.DataFrame:
    return geo.segmentos_mercado()


@st.cache_data(ttl=900, show_spinner=False)
def _pareamento() -> pl.DataFrame:
    return geo.qualidade_pareamento()


@st.cache_resource(show_spinner=False)
def _malha() -> dict | None:
    return geo.geojson_municipios()


def mapa(
    df: pl.DataFrame,
    metrica: str,
    titulo: str,
    escala: str = "Teal",
    altura: int = 520,
    discreto: bool = False,
) -> go.Figure | None:
    """
    Choropleth municipal de MG sobre a malha oficial do IBGE.

    `discreto=True` pinta por categoria (os quadrantes de White Space), usando
    a cor declarada em config/mercado_mg.yaml. Devolve None se a malha nao foi
    baixada — a pagina entao cai para o ranking em barras, com os mesmos numeros.
    """
    malha = _malha()
    if malha is None:
        return None

    dados = df.filter(pl.col(metrica).is_not_null()) if not discreto else df
    if dados.height == 0:
        return None

    locais = [str(c) for c in dados["cod_ibge"].to_list()]
    nomes = dados["municipio"].to_list()

    if discreto:
        codigos = sorted(dados["quadrante"].unique().to_list())
        indice = {c: i for i, c in enumerate(codigos)}
        cores = [
            dados.filter(pl.col("quadrante") == c)["quadrante_cor"][0] for c in codigos
        ]
        rotulos = [
            dados.filter(pl.col("quadrante") == c)["quadrante_rotulo"][0] for c in codigos
        ]
        z = [indice[c] for c in dados["quadrante"].to_list()]
        n = max(len(codigos) - 1, 1)
        colorscale = []
        for i, cor in enumerate(cores):
            colorscale.append([i / len(cores), cor])
            colorscale.append([(i + 1) / len(cores), cor])
        fig = go.Figure(go.Choropleth(
            geojson=malha, locations=locais, z=z,
            featureidkey="properties.codarea",
            colorscale=colorscale, zmin=-0.5, zmax=n + 0.5,
            marker_line_color="rgba(255,255,255,0.45)", marker_line_width=0.3,
            colorbar=dict(
                tickvals=list(range(len(codigos))), ticktext=rotulos,
                thickness=14, len=0.75, title="",
            ),
            text=[f"{nome}<br>{q}" for nome, q in
                  zip(nomes, dados["quadrante_rotulo"].to_list(), strict=True)],
            hovertemplate="%{text}<extra></extra>",
        ))
    else:
        valores = [float(v or 0) for v in dados[metrica].to_list()]
        fig = go.Figure(go.Choropleth(
            geojson=malha, locations=locais, z=valores,
            featureidkey="properties.codarea",
            colorscale=escala,
            marker_line_color="rgba(255,255,255,0.45)", marker_line_width=0.3,
            colorbar=dict(thickness=14, len=0.75, title=""),
            text=nomes,
            hovertemplate="%{text}<br>%{z:,.2f}<extra></extra>",
        ))

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        title=titulo, height=altura, margin=dict(l=0, r=0, t=44, b=0),
        paper_bgcolor="rgba(0,0,0,0)", geo=dict(bgcolor="rgba(0,0,0,0)"),
        separators=",.",
    )
    return fig


def mapa_ou_ranking(
    df: pl.DataFrame, metrica: str, titulo: str, nome_export: str,
    escala: str = "Teal", discreto: bool = False, altura: int = 520,
) -> None:
    fig = mapa(df, metrica, titulo, escala=escala, discreto=discreto, altura=altura)
    colunas = ["municipio", "regiao_intermediaria", metrica]
    if discreto:
        colunas = ["municipio", "regiao_intermediaria", "quadrante_rotulo",
                   "teto_t_mes", "venda_t_mes", "espaco_t_mes"]
    if fig is not None:
        ui.grafico(fig, df.select(colunas).sort(colunas[-1], descending=True).head(80),
                   nome_export)
        return
    st.warning(
        "A malha municipal do IBGE ainda não foi baixada "
        "(`py scripts/build_mercado_mg.py`). Mostrando o ranking equivalente.",
        icon="🗺️",
    )
    topo = df.sort(metrica, descending=True).head(25)
    ui.grafico(ui.barra(topo, "municipio", metrica, titulo, horizontal=True, altura=560),
               topo.select(colunas), nome_export)


# ---------------------------------------------------------------------
# Controles da página
# ---------------------------------------------------------------------
with st.expander("Parâmetros desta análise", expanded=False):
    c1, c2, c3 = st.columns(3)
    janela = c1.select_slider(
        "Janela de venda considerada", options=[6, 12, 24, 36], value=JANELA_PADRAO,
        help="Meses contados a partir do último mês com movimento.",
    )
    p_pot = c2.slider(
        "Corte de potencial alto (percentil)", 0.50, 0.95,
        float(CFG["white_space"]["percentil_potencial_alto"]), 0.05,
    )
    p_ven = c3.slider(
        "Corte de venda alta (percentil)", 0.50, 0.95,
        float(CFG["white_space"]["percentil_venda_alta"]), 0.05,
        help="Calculado apenas entre municípios que vendem — venda zero é sempre baixa.",
    )
    st.caption(
        f"Escopo de produto: {', '.join(CFG['classificacoes_no_escopo'])}. "
        "FARELO fica fora — é cadeia de ração animal, não de panificação. "
        f"Parâmetros do modelo em `config/mercado_mg.yaml` (status {CFG['status']})."
    )

base = _carregar(janela)
df = geo.classificar(base, percentil_potencial=p_pot, percentil_venda=p_ven)
r = geo.resumo_estado(df)
com_venda = df.filter(pl.col("tem_venda")).sort("ton_farinha", descending=True)

abas = st.tabs([
    "Panorama",
    "1 · Vendas por cidade",
    "2 · Territórios dos RCAs",
    "3 · Potencial de farinha",
    "Sobreposição · White Space",
    "Decisão de expansão",
])

# =====================================================================
# PANORAMA
# =====================================================================
with abas[0]:
    c = st.columns(4)
    ui.cartao(c[0], "Municípios de MG atendidos",
              f"{r['com_venda']} de {r['municipios']}",
              ajuda=f"{ui.percentual(r['cobertura_pct'])} do estado")
    ui.cartao(c[1], "Venda de farinha", f"{ui.numero(r['venda_t_mes'], 0)} t/mês",
              ajuda=f"janela de {janela} meses")
    ui.cartao(c[2], "Mercado endereçável estimado",
              f"{ui.numero(r['enderecavel_t_mes'], 0)} t/mês",
              ajuda=f"share do Moinho: {ui.percentual(r['share_enderecavel_pct'])}")
    ui.cartao(c[3], "Espaço não atendido", f"{ui.numero(r['espaco_t_mes'], 0)} t/mês",
              ajuda=f"+{ui.percentual(r['crescimento_possivel_pct'])} sobre a venda atual")

    c = st.columns(4)
    ui.cartao(c[0], "População sem nenhuma venda",
              ui.numero(r["populacao_sem_venda"], 0, compacto=True),
              ajuda=f"{r['sem_venda']} municípios")
    ui.cartao(c[1], "Clientes ativos em MG", ui.inteiro(r["clientes_ativos"]))
    ui.cartao(c[2], "Estabelecimentos consumidores", ui.inteiro(r["estabelecimentos"]),
              ajuda="CEMPRE/IBGE, CNAEs do escopo")
    ui.cartao(c[3], "Cidades com venda e sem RCA responsável",
              ui.inteiro(r["venda_sem_territorio"]),
              ajuda=f"{r['territorio_sem_venda']} com RCA e sem venda")

    st.info(
        "**Como ler esta página.** As camadas 1 e 2 são *fato*: saem do documento fiscal e "
        "do arquivo de território. A camada 3 é *estimativa* — combina o cadastro de "
        "empresas do IBGE com o consumo real observado nos clientes do próprio Moinho. "
        "Onde o número é estimado, a página diz.",
        icon="🧭",
    )

    ui.secao("As três camadas, lado a lado",
             "O mesmo estado visto por venda, por cobertura comercial e por mercado.")
    col1, col2, col3 = st.columns(3)
    with col1:
        fig = mapa(df, "venda_t_mes", "1 · Venda (t/mês)", escala="Teal", altura=330)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
    with col2:
        fig = mapa(df, "qtd_representantes", "2 · RCAs por cidade",
                   escala="Purples", altura=330)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
    with col3:
        fig = mapa(df, "teto_t_mes", "3 · Potencial (t/mês)", escala="Oranges", altura=330)
        if fig:
            st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})

    if _malha() is None:
        st.warning(
            "Malha municipal ausente: rode `py scripts/build_mercado_mg.py` para "
            "habilitar os mapas. Todas as tabelas e rankings funcionam sem ela.",
            icon="🗺️",
        )

    ui.secao("Concentração: quanto do negócio depende de quão poucas cidades")
    if com_venda.height:
        ui.grafico(
            ui.pareto(com_venda.head(30), "municipio", "ton_farinha",
                      "Pareto das cidades por tonelada de farinha", altura=420),
            com_venda.select("municipio", "regiao_intermediaria", "ton_farinha",
                             "clientes_ativos").head(30),
            "pareto_cidades_mg",
        )

# =====================================================================
# CAMADA 1 — VENDAS POR CIDADE
# =====================================================================
with abas[1]:
    ui.secao(
        "Camada 1 · Onde o Moinho vende hoje em Minas",
        "Geografia real do cliente (município de entrega), não a região comercial "
        "interna. Fonte: item de nota fiscal.",
    )

    metrica = st.radio(
        "Métrica no mapa",
        ["venda_t_mes", "receita_farinha", "clientes_ativos", "pmv", "frete_por_ton"],
        format_func=lambda m: {
            "venda_t_mes": "Toneladas/mês", "receita_farinha": "Receita",
            "clientes_ativos": "Clientes ativos", "pmv": "PMV (R$/t)",
            "frete_por_ton": "Frete (R$/t)",
        }[m],
        horizontal=True, key="c1_metrica",
    )
    mapa_ou_ranking(df, metrica, f"Camada 1 — {metrica}", f"c1_{metrica}")

    col1, col2 = st.columns([3, 2])
    with col1:
        ui.secao("Ranking municipal")
        ui.tabela(
            com_venda.select(
                "municipio", "regiao_intermediaria", "ton_farinha", "venda_t_mes",
                "receita_farinha", "pmv", "clientes_ativos", "meses_com_venda",
                "frete_por_ton", "ultimo_mes",
            ),
            "vendas_municipio_mg", altura=440, chave="c1_rank",
        )
    with col2:
        ui.secao("Por região intermediária (IBGE)")
        regioes = geo.por_regiao(df)
        ui.grafico(
            ui.barra(regioes.sort("venda_t_mes", descending=True),
                     "regiao_intermediaria", "venda_t_mes",
                     "Toneladas/mês por região", horizontal=True, altura=440),
            regioes.select("regiao_intermediaria", "venda_t_mes", "municipios_com_venda",
                           "municipios", "clientes_ativos"),
            "c1_regioes",
        )

    if com_venda.height:
        top1 = com_venda.head(1)
        parte = 100 * float(top1["ton_farinha"][0] or 0) / float(df["ton_farinha"].sum() or 1)
        st.warning(
            f"**Concentração extrema.** {top1['municipio'][0]} responde por "
            f"{ui.percentual(parte)} da tonelagem de farinha do estado com apenas "
            f"{int(top1['clientes_ativos'][0])} cliente(s) ativo(s). Uma cidade cujo volume "
            "depende de pouquíssimos CNPJs é receita concentrada, não presença territorial.",
            icon="⚠️",
        )

# =====================================================================
# CAMADA 2 — TERRITÓRIOS DOS RCAs
# =====================================================================
with abas[2]:
    ui.secao(
        "Camada 2 · Território declarado dos representantes",
        "Fonte: arquivo “REGIÃO COMERCIAL POR REPRESENTANTE”. É uma *intenção de "
        "cobertura* — não prova que houve venda.",
    )

    c = st.columns(4)
    ui.cartao(c[0], "Municípios com RCA atribuído", ui.inteiro(r["com_territorio"]),
              ajuda=f"de {r['municipios']} municípios de MG")
    ui.cartao(c[1], "Sem RCA e sem venda",
              ui.inteiro(int(df.filter(~pl.col("tem_venda") & ~pl.col("tem_territorio")).height)))
    ui.cartao(c[2], "Venda sem RCA responsável", ui.inteiro(r["venda_sem_territorio"]))
    ui.cartao(c[3], "RCA atribuído e sem venda", ui.inteiro(r["territorio_sem_venda"]))

    mapa_ou_ranking(df, "qtd_representantes", "Camada 2 — representantes por município",
                    "c2_territorio", escala="Purples")

    ui.secao(
        "Território recebido × resultado obtido",
        "A pergunta do estudo de mercado: um RCA com menos toneladas pode estar "
        "performando melhor, se o território que recebeu for menor.",
    )
    reps = _representantes()
    if reps.height:
        ui.tabela(
            reps.select("representante", "cidades_atribuidas", "cidades_com_venda",
                        "ativacao_pct", "venda_t_mes", "teto_t_mes", "captura_pct",
                        "populacao", "estabelecimentos", "fontes"),
            "territorio_por_rca", altura=420, chave="c2_reps",
        )
        ui.grafico(
            ui.dispersao(
                reps.filter(pl.col("teto_t_mes") > 0),
                "teto_t_mes", "venda_t_mes", tamanho="cidades_atribuidas",
                cor="ativacao_pct", rotulo="representante",
                titulo="Potencial do território × venda realizada (cor: % de cidades ativadas)",
                altura=480,
            ),
            reps.select("representante", "teto_t_mes", "venda_t_mes", "cidades_atribuidas",
                        "ativacao_pct"),
            "c2_quadrante_rca",
            ajuda="Abaixo da diagonal: território grande com pouca venda extraída.",
        )

    ui.secao("Lacunas entre território e realidade")
    lac = geo.lacunas_territoriais(df)
    sub = st.tabs([
        f"Órfãos ({lac['orfaos'].height})",
        f"Venda sem dono ({lac['sem_dono'].height})",
        f"Atribuídos sem venda ({lac['inativos'].height})",
    ])
    with sub[0]:
        st.caption("Mercado mapeado, nenhuma venda e nenhum RCA responsável. "
                   "É onde a expansão não tem sequer um dono definido.")
        ui.tabela(
            lac["orfaos"].select("municipio", "regiao_intermediaria", "populacao",
                                 "estabelecimentos", "estab_panificacao", "teto_t_mes"),
            "orfaos_mg", altura=360, chave="c2_orfaos",
        )
    with sub[1]:
        st.caption("Há faturamento, mas nenhum representante declara atender a cidade.")
        ui.tabela(
            lac["sem_dono"].select("municipio", "regiao_intermediaria", "venda_t_mes",
                                   "clientes_ativos", "teto_t_mes"),
            "venda_sem_dono_mg", altura=360, chave="c2_semdono",
        )
    with sub[2]:
        st.caption("O RCA declara a cidade no território, existe mercado, e não houve venda "
                   "na janela.")
        ui.tabela(
            lac["inativos"].select("municipio", "regiao_intermediaria", "representantes",
                                   "populacao", "estabelecimentos", "teto_t_mes"),
            "territorio_inativo_mg", altura=360, chave="c2_inativos",
        )

    st.info(
        "As duas abas do arquivo de território divergem entre si (cidades e representantes "
        "diferentes). Ambas foram preservadas com a coluna `fonte` em vez de escolher uma "
        "silenciosamente — a conciliação é decisão comercial, não de engenharia de dados.",
        icon="📄",
    )

# =====================================================================
# CAMADA 3 — POTENCIAL DE FARINHA
# =====================================================================
with abas[3]:
    ui.secao(
        "Camada 3 · Quanto mercado de farinha existe em cada município",
        "Traduz o relatório de pesquisa em número: potencial econômico por cidade, "
        "não contagem de estabelecimentos.",
    )

    st.markdown(
        "O método segue a recomendação central do estudo: em vez de perguntar quanto "
        "*uma padaria consome*, mede-se quanto **as padarias que já compram do Moinho "
        "efetivamente compram**, e aplica-se esse consumo ao universo de empresas que o "
        "IBGE registra em cada município."
    )

    seg = _segmentos()
    c = st.columns(4)
    ui.cartao(c[0], "Estabelecimentos mapeados", ui.inteiro(r["estabelecimentos"]),
              ajuda="CEMPRE/IBGE — empresas formais atuantes")
    ui.cartao(c[1], "Mercado endereçável",
              f"{ui.numero(r['enderecavel_t_mes'], 0)} t/mês",
              ajuda=f"{ui.numero(r['enderecavel_t_mes'] * 12, 0, compacto=True)} t/ano")
    ui.cartao(c[2], "Teto realista do Moinho",
              f"{ui.numero(r['teto_t_mes'], 0)} t/mês",
              ajuda="endereçável × probabilidade de captura")
    ui.cartao(c[3], "Share endereçável atual",
              ui.percentual(r["share_enderecavel_pct"]))

    mapa_ou_ranking(df, "teto_t_mes", "Camada 3 — potencial capturável (t/mês)",
                    "c3_potencial", escala="Oranges")

    ui.secao("Segmentos: onde está o volume e por qual canal ele se alcança")
    ui.tabela(
        seg.select("rotulo", "cnae", "papel", "canal", "estabelecimentos",
                   "municipios_presentes", "consumo_t_mes", "origem_consumo",
                   "clientes_amostra", "prob_captura", "enderecavel_t_mes", "teto_t_mes"),
        "segmentos_mercado_mg", altura=340, chave="c3_seg",
    )
    col1, col2 = st.columns(2)
    with col1:
        ui.grafico(
            ui.barra(seg.sort("teto_t_mes", descending=True), "rotulo", "teto_t_mes",
                     "Potencial capturável por segmento (t/mês)", horizontal=True, altura=380),
            seg.select("rotulo", "teto_t_mes", "estabelecimentos"), "c3_seg_potencial",
        )
    with col2:
        ui.grafico(
            ui.barra(seg.sort("estabelecimentos", descending=True), "rotulo",
                     "estabelecimentos", "Universo de estabelecimentos",
                     horizontal=True, altura=380),
            seg.select("rotulo", "estabelecimentos", "municipios_presentes"),
            "c3_seg_universo",
        )

    with st.expander("Como o potencial foi calculado — e o que ele não é"):
        st.markdown(
            f"""
**Fórmula por município e segmento**

`potencial = unidades locais (CEMPRE) × consumo mediano observado × fator de porte`
e `potencial capturável = potencial × probabilidade de captura`.

- **Consumo mediano observado** — mediana de t/mês dos clientes reais do Moinho no
  mesmo segmento, na janela de {janela} meses. Segmentos com menos de
  {CFG['modelo']['minimo_clientes_amostra']} clientes na amostra caem para um valor
  derivado da intensidade relativa e são marcados como `FALLBACK` na tabela acima.
- **Fator de porte** — o CEMPRE publica pessoal ocupado por município e CNAE.
  Cidades cujos estabelecimentos são maiores que a média estadual do segmento
  recebem fator maior que 1, limitado entre
  {CFG['modelo']['ajuste_porte']['fator_minimo']} e
  {CFG['modelo']['ajuste_porte']['fator_maximo']}.
- **Probabilidade de captura** — a fatia do mercado do município que um moinho
  regional realisticamente disputa. É um parâmetro de negócio, editável em
  `config/mercado_mg.yaml`, **ainda não homologado**.

**O que este número não é**

Não é consumo total de farinha do município, não é meta de venda e não é
participação de mercado. É um denominador comparável entre 853 municípios, que
serve para ordenar prioridade — não para prometer tonelada.

**Por que os totais divergem de outras fontes**

O CEMPRE conta empresas formais atuantes. A base aberta do CNPJ e os números da
ABIP citados no relatório usam definições diferentes e incluem MEI, por isso
chegam a ordens de grandeza maiores. Somar ou comparar diretamente as fontes
produziria número sem significado; aqui a fonte é única e declarada.
"""
        )

    with st.expander("Rastreabilidade do pareamento de cidades"):
        st.caption(
            "Toda cidade foi ligada ao código IBGE por um método explícito. O que não "
            "pareou com segurança ficou sem município — uma lacuna visível vale mais que "
            "um município errado no mapa."
        )
        ui.tabela(_pareamento(), "pareamento_cidades", altura=300, chave="c3_pareamento")

# =====================================================================
# SOBREPOSIÇÃO — WHITE SPACE
# =====================================================================
with abas[4]:
    ui.secao(
        "As três camadas sobrepostas",
        "Cada município classificado pelo cruzamento entre o potencial estimado e a "
        "venda realizada.",
    )

    resumo_q = (
        df.group_by("quadrante_rotulo", "quadrante_cor", "quadrante_acao")
        .agg(
            pl.len().alias("municipios"),
            pl.col("populacao").sum().alias("populacao"),
            pl.col("venda_t_mes").sum().alias("venda_t_mes"),
            pl.col("teto_t_mes").sum().alias("teto_t_mes"),
            pl.col("espaco_t_mes").sum().alias("espaco_t_mes"),
            pl.col("clientes_ativos").sum().alias("clientes_ativos"),
        )
        .sort("espaco_t_mes", descending=True)
    )

    cols = st.columns(len(resumo_q))
    for i, linha in enumerate(resumo_q.iter_rows(named=True)):
        ui.cartao(
            cols[i], linha["quadrante_rotulo"], f"{linha['municipios']} municípios",
            ajuda=f"{ui.numero(linha['espaco_t_mes'], 0)} t/mês de espaço · "
                  f"{linha['quadrante_acao']}",
        )

    mapa_ou_ranking(df, "quadrante", "Mapa de White Space de Minas Gerais",
                    "white_space_mg", discreto=True, altura=560)

    col1, col2 = st.columns([3, 2])
    with col1:
        alvo = df.filter(pl.col("teto_t_mes") > 0)
        ui.grafico(
            ui.dispersao(
                alvo, "teto_t_mes", "venda_t_mes", tamanho="estabelecimentos",
                cor="penetracao_pct",
                rotulo=None,
                titulo="Matriz potencial × venda (cada ponto é um município)",
                altura=480,
            ),
            alvo.select("municipio", "teto_t_mes", "venda_t_mes", "estabelecimentos",
                        "penetracao_pct", "quadrante_rotulo")
                .sort("teto_t_mes", descending=True).head(60),
            "matriz_white_space",
            ajuda="Canto inferior direito: muito mercado, pouca venda — o White Space.",
        )
    with col2:
        ui.secao("Espaço por região")
        regioes = geo.por_regiao(df)
        ui.grafico(
            ui.barra(regioes.head(13), "regiao_intermediaria", "espaco_t_mes",
                     "Espaço não atendido (t/mês)", horizontal=True, altura=480),
            regioes.select("regiao_intermediaria", "espaco_t_mes", "venda_t_mes",
                           "municipios_com_venda", "municipios", "cobertura_pct"),
            "espaco_por_regiao",
        )

    ui.secao("Prioridades município a município")
    escolha = st.multiselect(
        "Filtrar por quadrante",
        options=resumo_q["quadrante_rotulo"].to_list(),
        default=[q for q in resumo_q["quadrante_rotulo"].to_list() if q == "White Space"],
        key="ws_filtro",
    )
    tabela = df.filter(pl.col("quadrante_rotulo").is_in(escolha)) if escolha else df
    ui.tabela(
        tabela.sort("espaco_t_mes", descending=True).select(
            "municipio", "regiao_intermediaria", "quadrante_rotulo", "populacao",
            "estabelecimentos", "estab_panificacao", "estab_distribuidores",
            "teto_t_mes", "venda_t_mes", "espaco_t_mes", "captura_pct",
            "penetracao_pct", "clientes_ativos", "qtd_representantes", "representantes",
        ),
        "white_space_municipios", altura=460, chave="ws_tabela",
    )

# =====================================================================
# DECISÃO DE EXPANSÃO
# =====================================================================
with abas[5]:
    regioes = geo.por_regiao(df)
    top_espaco = regioes.head(4)
    ws = df.filter(pl.col("quadrante") == "ALTO_BAIXA").sort("espaco_t_mes", descending=True)
    fortalezas = df.filter(pl.col("quadrante") == "ALTO_ALTA")

    ui.secao("Leitura para a decisão do proprietário")

    concentracao = (
        100 * float(fortalezas["venda_t_mes"].sum() or 0) / float(r["venda_t_mes"] or 1)
    )
    espaco_top4 = float(top_espaco["espaco_t_mes"].sum() or 0)
    parte_top4 = 100 * espaco_top4 / float(r["espaco_t_mes"] or 1)

    c = st.columns(3)
    ui.cartao(c[0], "Venda concentrada nas fortalezas", ui.percentual(concentracao),
              ajuda=f"{fortalezas.height} municípios de {r['municipios']}")
    ui.cartao(c[1], "Espaço nas 4 regiões prioritárias",
              f"{ui.numero(espaco_top4, 0)} t/mês",
              ajuda=f"{ui.percentual(parte_top4)} de todo o espaço do estado")
    ui.cartao(c[2], "Crescimento possível sem sair de MG",
              f"+{ui.percentual(r['crescimento_possivel_pct'])}",
              ajuda="sobre a venda atual de farinha")

    st.markdown(
        f"""
#### O que os dados dizem

**1. O Moinho é forte onde já está, e quase ausente onde o mercado está.**
{fortalezas.height} municípios concentram {ui.percentual(concentracao)} da venda de
farinha. Ao mesmo tempo, {r['sem_venda']} dos {r['municipios']} municípios de Minas não
tiveram uma única venda na janela de {janela} meses — território que abriga
{ui.numero(r['populacao_sem_venda'], 0, compacto=True)} habitantes.

**2. A expansão não exige sair de Minas.**
O espaço não atendido dentro do próprio estado é de
{ui.numero(r['espaco_t_mes'], 0)} t/mês, equivalente a
**+{ui.percentual(r['crescimento_possivel_pct'])}** sobre a venda atual de farinha —
e {ui.percentual(parte_top4)} dele está em apenas quatro regiões.

**3. O padrão geográfico é claro.**
A força está no Triângulo e Alto Paranaíba, onde a operação nasceu e a logística é
curta. O espaço está no eixo Sul/Sudeste e na Região Metropolitana de Belo Horizonte —
mercados grandes onde a presença atual é simbólica.

**4. Capilaridade e volume pedem canais diferentes.**
O universo é dominado por estabelecimentos pequenos. Atacar essa cauda com venda
direta destrói margem por frete e pedido pequeno; o relatório de pesquisa é explícito
ao tratar o distribuidor como *instrumento de cobertura territorial*, e não como um
intermediário dispensável.
"""
    )

    ui.secao("As quatro regiões que concentram o espaço")
    ui.tabela(
        top_espaco.select("regiao_intermediaria", "municipios", "municipios_com_venda",
                          "cobertura_pct", "populacao", "estabelecimentos",
                          "clientes_ativos", "venda_t_mes", "teto_t_mes", "espaco_t_mes"),
        "regioes_prioritarias", altura=200, chave="dec_regioes",
    )

    ui.secao("As 15 cidades de maior espaço não atendido")
    ui.tabela(
        ws.head(15).select("municipio", "regiao_intermediaria", "populacao",
                           "estabelecimentos", "estab_panificacao", "estab_distribuidores",
                           "espaco_t_mes", "venda_t_mes", "clientes_ativos",
                           "representantes"),
        "cidades_prioritarias", altura=400, chave="dec_cidades",
    )

    st.markdown(
        """
#### Três decisões que este mapa coloca na mesa

**Decisão 1 — Onde colocar o próximo representante.**
Hoje o território dos RCAs foi herdado, não desenhado: há cidades com venda e sem
responsável, e regiões inteiras de alto potencial com um único representante. A aba
*Territórios* mostra, por RCA, o tamanho do mercado recebido contra o resultado
extraído — a base objetiva para redesenhar a divisão.

**Decisão 2 — Distribuidor como estratégia, não como acaso.**
As cidades de White Space têm muitos estabelecimentos pequenos. Escolher, região por
região, um distribuidor com capilaridade custa menos que abrir rota própria — e é o
único caminho economicamente viável para a cauda longa.

**Decisão 3 — Reduzir a dependência de pouquíssimas contas.**
A tonelagem do estado depende de um número muito pequeno de CNPJs. Crescer nas regiões
de White Space não é apenas oportunidade de receita: é redução de risco de
concentração.
"""
    )

    st.warning(
        "**O que ainda falta para transformar isto em meta.** O potencial usa o cadastro "
        "de empresas do IBGE, que não distingue uma padaria artesanal de uma central de "
        "produção, e a probabilidade de captura ainda não foi homologada pela área "
        "comercial. Antes de virar orçamento, o passo seguinte é cruzar CNPJ dos clientes "
        "atuais com a base da Receita Federal para calibrar consumo por porte real, como "
        "recomenda o relatório de pesquisa.",
        icon="⚠️",
    )
