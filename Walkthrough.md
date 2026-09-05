# Walkthrough — Análise Geográfica de Potencial de Mercado (MG)

O que foi construído, onde está no código, e como validar.

---

## 1. O que a entrega responde

Três camadas sobrepostas no mapa dos **853 municípios de Minas Gerais**:

| Camada | Pergunta | Onde |
|---|---|---|
| 1 — Venda | Onde o Moinho vende hoje? | aba *1 · Vendas por cidade* |
| 2 — Território | Quem responde por cada cidade? | aba *2 · Territórios dos RCAs* |
| 3 — Mercado | Quanto mercado de farinha existe ali? | aba *3 · Potencial de farinha* |
| Sobreposição | Onde há mercado e não há venda? | aba *Sobreposição · White Space* |
| Decisão | O que o proprietário faz com isso? | aba *Decisão de expansão* |

---

## 2. O que os dados mostraram

| Indicador | Valor |
|---|---|
| Municípios de MG com venda de farinha (12 meses) | **120 de 853** (14,1%) |
| População em municípios sem nenhuma venda | **8,2 milhões** |
| Venda atual de farinha em MG | **2.877 t/mês** |
| Mercado endereçável estimado | **19.186 t/mês** |
| Share endereçável do Moinho | **15,0%** |
| Espaço não atendido | **1.775 t/mês** (+61,7% sobre a venda atual) |
| Municípios em White Space | **219**, com 7,9 mi de habitantes e 164 t/mês de venda |
| Concentração | **32 municípios** concentram **92%** da venda de farinha |

O padrão geográfico é nítido: a força está no Triângulo e Alto Paranaíba, onde a
operação nasceu; o espaço está no eixo Sul/Sudeste e na Região Metropolitana de Belo
Horizonte. **Belo Horizonte, Varginha, Juiz de Fora e Pouso Alegre** concentram 76% de
todo o espaço do estado.

Contraste que resume a tese: Uberlândia tem **752 clientes ativos** e 2 t/mês de
espaço; Pouso Alegre tem **1 cliente** e 29 t/mês.

---

## 3. Onde está no código

### Ingestão externa — `src/ingestion/mercado_ibge.py`
Quatro fontes públicas do IBGE, com as URLs em `config/mercado_mg.yaml` e nunca no
código: Localidades (853 municípios + hierarquia regional), Censo 2022 (população),
CEMPRE agregado **9528** (unidades locais e pessoal ocupado por município **e classe
CNAE**, referência 2024) e a malha municipal em GeoJSON.

> O 9528 foi a peça difícil: os agregados do CEMPRE com CNAE detalhada param no nível
> de UF. Ele é o que publica CNAE **por município**, e por isso a camada 3 existe.

Sem rede o download não derruba nada: cai no cache em parquet e registra o aviso.

### Modelo — `migrations/007_mercado_geografico_mg.sql`
Cinco tabelas e duas materialized views. A chave de integração é o **código IBGE do
município**; nenhuma junção por texto acontece dentro de consulta da aplicação.

### Staging — `src/staging/geografia.py`
O único julgamento embutido em código é o algoritmo de pareamento de nomes.

**Pareamento em quatro níveis**, do mais seguro ao menos:

| Método | Regra | Resultado |
|---|---|---|
| `EXATO` | idênticas após normalização | 435 grafias |
| `SEM_CONECTIVOS` | após expandir `S.`→`SAO` e remover *de/do/da* | 9 |
| `APROXIMADO` | similaridade ≥ 0,90, **primeiro token igual**, sem empate | 1 |
| `AMBIGUO` / `NAO_ENCONTRADO` | fica sem município, de propósito | 76 |

As **150 cidades com venda em MG parearam sem uso de aproximação**.

> **Um erro que a primeira versão cometeu.** Com um limiar simples de similaridade, o
> pareamento levou `GOIÂNIA`→*Goianá*, `ANÁPOLIS`→*Canápolis* e `IRAÍ`→*Miraí* — três
> cidades de fora de Minas pintadas no mapa de Minas. A correção foi exigir que o
> primeiro token seja idêntico e recusar empates técnicos. Há um teste por caso.

**Potencial** (`calcular_potencial`):

```
potencial      = unidades locais (CEMPRE) × consumo mediano observado × fator de porte
teto realista  = potencial × probabilidade de captura
espaço         = max(teto − venda atual, 0)
```

O consumo mediano vem dos **clientes reais do Moinho** no mesmo segmento. Segmentos com
menos de 5 clientes na amostra caem para `FALLBACK` e são marcados como tal na tela:

| Segmento | Consumo t/mês por unidade | Origem | Amostra |
|---|---:|---|---:|
| Atacado de cereais e farinhas | 2,538 | OBSERVADO | 55 |
| Massas alimentícias | 1,750 | FALLBACK | 4 |
| Alimentos e pratos prontos | 1,050 | FALLBACK | 2 |
| Atacado de alimentos em geral | 1,050 | FALLBACK | 4 |
| Panificação e confeitaria | 0,442 | OBSERVADO | 309 |
| Varejo de padaria | 0,357 | OBSERVADO | 517 |
| Biscoitos e bolachas | 0,251 | OBSERVADO | 6 |
| Food service | 0,225 | OBSERVADO | 166 |

### Repositório — `src/repositories/geo.py`
Única camada com SQL da nova área. A **classificação de White Space mora aqui**, e não
no SQL, porque depende de percentis que o usuário move na tela.

> **Segundo erro corrigido.** O corte de venda calculado sobre os 853 municípios caía em
> zero — 733 não vendem nada — e promovia *todo* município do estado a "venda alta",
> esvaziando o quadrante de White Space (2 municípios). O corte passou a ser calculado
> só entre os que vendem, e venda zero é sempre venda baixa. O White Space foi de 2 para
> 219 municípios. Há teste.

### Página — `app/pages/p13_potencial_mg.py`
Seis abas. Mapa choropleth sobre a malha oficial; sem a malha, cai para o ranking em
barras com os mesmos números. Nenhuma linha de SQL.

---

## 4. Como validar

```powershell
# 1. Construir a base de mercado (única etapa que usa internet)
py scripts/build_mercado_mg.py

# 2. Ou dentro do pipeline completo
py scripts/run_pipeline.py --etapa mercado
py scripts/run_pipeline.py --etapa geografia

# 3. Testes
py -m pytest tests/test_mercado_mg.py -v     # 24 testes
py -m pytest                                  # suíte completa: 99 testes

# 4. Abrir a tela
.\_start.ps1 -SoApp    # menu Comercial → "Potencial de Mercado MG"
```

Resultado esperado do item 1:

```
municipios                   853
cidades [CLIENTE]            150/150 pareadas
cidades [TERRITORIO_REGIAO]  133/205 pareadas
grafias sem municipio        76
linhas mercado x segmento    3038
atribuicoes de territorio    320
potencial capturavel         2531.4 t/mes
```

### Verificações que o teste faz por você

| Teste | O que protege |
|---|---|
| `test_venda_do_mapa_bate_com_o_fato` | tonelagem do mapa = fato de venda em MG (< 0,01%) |
| `test_repositorio_reproduz_a_materialized_view` | as duas fontes não divergem |
| `test_cidade_de_outro_estado_nao_e_forcada_para_mg` | Anápolis/Goiânia não entram no mapa |
| `test_grafia_ambigua_nao_escolhe_sozinha` | `IRAI` não vira *Miraí* no palpite |
| `test_classificacao_cobre_todos_os_municipios` | município sem venda nunca é "venda alta" |
| `test_capturavel_nunca_excede_o_enderecavel` | a probabilidade é fração, não multiplicador |

---

## 5. Riscos e limites declarados

- **O potencial é estimativa, não medida.** Ordena prioridade entre municípios; não é
  meta, não é consumo total do município, não é participação de mercado.
- **A probabilidade de captura não foi homologada** — registrada em Q-16.
- **O CEMPRE não distingue** uma padaria artesanal de uma central de produção. O fator
  de porte (pessoal ocupado) atenua, mas não resolve.
- **Universos não são comparáveis entre fontes.** CEMPRE conta empresas formais
  atuantes; ABIP e a base aberta do CNPJ usam outras definições e incluem MEI.
- **Captura acima de 100%** em Uberlândia e Formiga é esperada: são distribuidores que
  revendem para fora do próprio município. O modelo é municipal; o negócio não é.

---

## 6. Entregável para a decisão

Relatório executivo publicado para o proprietário, com o mapa interativo dos 853
municípios, a matriz de White Space e as três decisões:

**https://claude.ai/code/artifact/9d607426-2cb7-4f3c-9e35-b5070d089b32**
