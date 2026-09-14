# Handoff entre agentes — Visao_moinho

Histórico em ordem inversa (mais recente no topo). Complementa
`knowledge/sessions.md`, que é gerado automaticamente e **não deve ser editado à mão**.

---

## 2026-09-14 08:40 - Antigravity (Gemini 3.7 Flash) - Eliminação Definitiva de "undefined" nos Títulos dos Gráficos (Streamlit Theme)

- **Session ID:** 846d2417-c450-4d2c-beb0-b76a8a47741c
- **Feito:**
  - Descoberta e diagnóstico aprofundado via inspeção Playwright de nós SVG:
    - O Streamlit possui um formatador nativo para `theme="streamlit"` em `st.plotly_chart` que intercepta o nó de título (`gtitle`) do layout Plotly.
    - Quando `title` era omitido ou `None`, o formatador em JavaScript lia `layout.title.text` como `undefined` e o injetava formatado em negrito: `<text class="gtitle"><b><b>undefined</b></b></text>` no topo superior esquerdo de todos os gráficos.
  - Correção implementada em `app/components/ui.py`:
    - No método `_layout`, garantido que `title=dict(text=str(titulo))` seja informado se houver título, ou `title=dict(text="")` explícito com string vazia quando não houver título.
  - Varredura automatizada ponta a ponta com Playwright por todas as 15 páginas da plataforma:
    - `TOTAL DE OCORRENCIAS DE UNDEFINED EM TODA A PLATAFORMA: 0`.
- **Nao feito:** nada pendente.
- **Proximo passo:** uso da plataforma e exibição dos gráficos sem qualquer resíduo visual.
- **Como validar:** executar `scripts/scan_all_pages_clean.py` ou acessar qualquer página da aplicação web.

---

## 2026-09-14 07:50 - Antigravity (Gemini 3.7 Flash) - Eliminação de "undefined" em todos os Gráficos da Plataforma

- **Session ID:** 846d2417-c450-4d2c-beb0-b76a8a47741c
- **Feito:**
  - Diagnóstico da causa raiz da exibição da string `"undefined"` nos tooltips e hovers do Plotly.js:
    1. O modo `hovermode="x unified"` em `app/components/ui.py` gerava cabeçalhos inválidos quando havia múltiplos eixos (`yaxis2`), traces combinados (barras + linhas) ou traces sem nome/formatação explícita.
    2. Traces adicionados manualmente e construtores base não possuíam tags de supressão de caixa secundária `<extra></extra>` nem `hovertemplate` estruturado.
  - Refatoração de `app/components/ui.py`:
    - Atualização do `_layout` com `hovermode="closest"` e remoção de conflitos de eixos secundários.
    - Implementação de mapeamento amigável de nomes de colunas e métricas (`_rotulo_amigavel`).
    - Definição de `hovertemplate` detalhado, formatado em pt-BR e com tag `<extra></extra>` em todos os geradores (`linha`, `barra`, `area_empilhada`, `barras_empilhadas`, `dispersao`, `waterfall`, `heatmap`, `treemap`, `pareto`, `boxplot`).
  - Atualização dos traces manuais nas páginas:
    - `app/pages/p00_visao_geral.py`: Hover explícito no gráfico Receita e Volume (com eixo secundário de Toneladas).
    - `app/pages/p02_gestao_mix.py`: Hover explícito no comparativo Orçado × Realizado.
    - `app/pages/p03_vendas.py`: Hover explícito em Vendas × Devoluções e PMV × Desconto.
    - `app/pages/p04_regional.py`: Inclusão de `text` e `hovertemplate` no mapa coroplético de estados (UFs).
  - Execução e aprovação da suíte de 103 testes no Pytest e 100% de conformidade no linter Ruff.
- **Nao feito:** nada pendente.
- **Proximo passo:** uso e apresentação da plataforma com gráficos limpos e sem qualquer ruído visual.
- **Como validar:** navegar pelas páginas no Streamlit (`http://localhost:8501`) e passar o mouse sobre qualquer gráfico e trace.

---

## 2026-09-14 07:35 - Antigravity (Gemini 3.7 Flash) - Inserção da Logo Oficial na Plataforma

- **Session ID:** 92a17a43-d8a2-4571-89f5-79f3eb718829
- **Feito:**
  - Importação do arquivo de logo oficial `Logo_moinho.jpeg` para `app/assets/logo_moinho.jpeg`.
  - Configuração nativa no Streamlit com `st.logo(str(LOGO_PATH), size="large")` em `app/main.py` para renderização destacada no topo da barra lateral (sidebar) em todas as páginas da plataforma.
  - Atualização da tela de login em `app/components/auth.py` para exibir a logo oficial com layout premium antes da autenticação.
  - Validação visual automatizada via Playwright gerando evidência em `artifacts/valida_logo_sidebar.png`.
- **Nao feito:** nada pendente.
- **Proximo passo:** navegação contínua na plataforma com a identidade visual completa.
- **Como validar:** acessar `http://localhost:8501` ou conferir a captura em `artifacts/valida_logo_sidebar.png`.

---

## 2026-09-14 07:15 - Antigravity (Gemini 3.7 Flash) - Inserção de gráficos da plataforma e notas do orador no PPTX

- **Session ID:** 92a17a43-d8a2-4571-89f5-79f3eb718829
- **Feito:**
  - Análise dos 36 slides da apresentação executiva `2026-09 Alianzo ENTHUS - Proposta Consultoria Comercial - Moinho Sete Irmaos V4.pptx`.
  - Captura automatizada via Playwright em alta resolução (Retina 2x) dos gráficos mais impactantes da plataforma Visão Moinho (Mapa das 3 Camadas de MG, Scorecard de Performance de RCAs e Cockpit Executivo de Gestão Comercial).
  - Backup preventivo criado em `...V4_backup.pptx`.
  - Inserção harmoniosa das imagens nos slides estratégicos: Slide 6 (Potencial MG), Slide 22 (Benchmark RCAs) e Slide 28 (Cockpit Comercial).
  - Inclusão de **Notas do Orador** detalhadas e persuasivas nos slides 4, 6, 22 e 28, com roteiro executivo de apresentação e suporte à tomada de decisão.
- **Nao feito:** nada pendente.
- **Proximo passo:** conduzir a apresentação executiva utilizando os roteiros nas notas do orador.
- **Como validar:** abrir a apresentação no PowerPoint e conferir os slides 4, 6, 22 e 28 com suas respectivas notas do orador.

---

## 2026-09-14 06:55 - Antigravity (Gemini 3.7 Flash) - Auditoria de dados dos slides e geração de imagem

- **Session ID:** 92a17a43-d8a2-4571-89f5-79f3eb718829
- **Feito:**
  - Auditoria completa de todos os números e textos do slide da apresentação contra o PostgreSQL / Data Warehouse (receita líquida de R$ 518,36 mi, volume de 198.790 t, margem proxy de 27,1%, 1.019 clientes em jul/26, PMVs do portfólio, mix do bolo, movimentação da base viva, redução de devoluções em 2026, dados de Leonel Soares e identificação de CR Promoções/Cláudio no codvend 29).
  - Geração de imagem PNG de alta resolução (Retina 2x, 16:9, layout executivo) contendo o quadro de auditoria com as 4 colunas solicitadas (Item do Slide, Dado Auditado na Base, Status, Detalhes da Auditoria).
  - Imagem disponibilizada em `quadro_auditoria_slide.png` e `artifacts/quadro_auditoria_slide.png`.
- **Nao feito:** nada pendente.
- **Proximo passo:** inclusão da imagem no slide de apoio da apresentação.
- **Como validar:** abrir o arquivo `quadro_auditoria_slide.png`.

---

## 2026-09-14 06:40 - Antigravity (Gemini 3.7 Flash) - Saneamento e trava do corte temporal em 2026-07

- **Session ID:** 846d2417-c450-4d2c-beb0-b76a8a47741c
- **Feito:**
  - Diagnóstico da anomalia do mês 08/2026 nos gráficos ("Receita e Volume" colado no zero): eram apenas 10 linhas residuais de devoluções/estornos de 04/08/2026 totalizando -R$ 343,08 sem vendas correspondentes.
  - Implementação da trava de corte oficial em `config/settings.yaml` (`escopo_temporal.fim: "2026-07"`).
  - Filtragem no staging de vendas (`src/staging/sales.py`) e no staging gerencial (`src/staging/managerial.py`) para descartar registros posteriores a 2026-07.
  - Reexecução do pipeline completo (`scripts/run_pipeline.py --forcar`) atualizando todas as 13 materialized views e tabelas analíticas.
  - Atualização dos testes de contagem/receita em `tests/test_regras_negocio.py`.
  - Suíte completa de 103 testes passando (`103 passed`) e `ruff check` limpo.
- **Nao feito:** nada pendente nesta demanda.
- **Proximo passo:** apresentação dos slides com dados homologados até 2026-07.
- **Como validar:**
  ```powershell
  $env:PYTHONPATH = "."; .venv\Scripts\python -m pytest
  .\_start.ps1 -SoApp
  ```

---

## 2026-09-05 11:45 - Claude Code (Opus 5) - Publicação em main e preparo de deploy

- **Feito:** auditoria de deploy (skill `railway-deploy-checklist`, adaptada de
  FastAPI+SQLite para Streamlit+PostgreSQL) e publicação.
  - **Dois defeitos reais encontrados na auditoria:**
    1. `table_exists` consultava `information_schema.tables`, que pelo padrão SQL não
       conhece materialized view — as 13 MVs respondiam "não existe" mesmo carregadas.
       Passou a consultar `pg_class` por `relkind`.
    2. `auto_seed` verificava `staging.fat_vendas`, tabela inexistente neste modelo.
       Somado ao item 1, concluía "banco vazio" com 204 mil linhas e **reprocessava a
       ingestão completa em todo restart do container** — risco de estourar o
       `healthcheckTimeout` de 120s do Railway e entrar em ciclo de restart.
  - Seed agora sai em <1s com banco populado; se a camada de MG faltar num banco já
    carregado, roda só `mercado/geografia/views`.
  - Conferido: `/healthz` responde 200 no Streamlit 1.41.1; `ENV PORT`/`EXPOSE`/
    entrypoint todos em 8501; `.env` fora da imagem; 15 parquets e as 2 malhas
    geográficas entram no container.
- **Publicado:** branch `feat/potencial-mercado-mg` → merge `--no-ff` em `main`.
  `main` = **1c85ef1**, empurrada para `origin`. O Railway faz deploy a partir daí.
- **Variáveis no Railway:** cadastradas pelo usuário antes do merge. A crítica é
  `AUTH_PASSWORD` — sem ela o default do código volta a ser `admin`.
- **Não feito:** não acompanhei o deploy. O Railway CLI está instalado e autenticado
  (`ia@enthusconsulting.com.br`), mas esta pasta não está vinculada a um projeto
  (`railway link` é interativo) e o nome do projeto do Moinho não é óbvio na lista.
  O `gh` CLI não está instalado, então o PR não foi aberto por linha de comando.
- **Próximo passo:** conferir no painel do Railway se o build passou e se o primeiro
  acesso pede a nova senha. Segue valendo a Q-16 (homologar probabilidades de captura).
- **Como validar em produção:** abrir a URL do serviço, logar com `admin` e a senha
  definida, e ir em Comercial → "Potencial de Mercado MG" — o mapa deve desenhar os
  853 municípios.

---

## 2026-09-05 10:30 - Claude Code (Opus 5) - Correção: mapas da página Potencial MG não apareciam

- **Sintoma relatado:** "As três camadas, lado a lado não estão visíveis".
- **Feito:** três defeitos empilhados, todos encontrados abrindo a tela num navegador
  real (Playwright instalado no venv) e lendo o DOM — `AppTest` executa o Python da
  página mas não renderiza o front-end, por isso os 99 testes passavam com a tela
  quebrada.
  1. **`locationmode`**: `go.Choropleth` usa default `ISO-3`. Com GeoJSON próprio, o
     Plotly ignorava `featureidkey` e tentava ler `3100104` como código de país —
     subplot criado, zero polígonos. Corrigido com `locationmode="geojson-id"` em
     `p13_potencial_mg.py` **e** em `p04_regional.py`, que tinha o mesmo padrão.
  2. **Orientação dos anéis**: o d3-geo (motor do Plotly) usa a convenção INVERSA à do
     RFC 7946 — espera exterior HORÁRIO. A malha do IBGE vem anti-horária (correta como
     GeoJSON), e cada município era desenhado como "o planeta menos este município":
     um retângulo sólido cobrindo o painel. `simplificar_malha` agora normaliza.
  3. **`pandas` lazy em thread**: o Plotly importa pandas dentro de `update_layout`;
     duas threads do Streamlit entrando juntas davam
     `partially initialized module 'pandas'` e derrubavam a tela de forma
     intermitente. `import pandas` explícito em `app/components/ui.py`.
- **De quebra:** a malha bruta (1,8 MB) viajava uma vez por figura e o Streamlit
  renderiza todas as abas de uma vez → ~11 MB por carga. Agora é baixada em qualidade
  mínima e simplificada por Douglas-Peucker em duas resoluções (`detalhe` 398 KB,
  `leve` 236 KB), ~2,3 MB por carga.
- **Verificado no navegador:** 853 polígonos em todos os mapas do p13 e 13 no p04.
  `ruff` limpo; **103 testes** passando (4 novos de regressão).
- **Não feito:** o relatório publicado (artifact) não foi regerado — ele desenha o
  próprio SVG e nunca dependeu do Plotly, então não foi afetado.
- **Próximo passo:** nada pendente nesta frente. Segue valendo a Q-16 (homologar as
  probabilidades de captura).
- **Como validar:**
  ```powershell
  py -m pytest tests/test_mercado_mg.py     # 28 testes
  .\_start.ps1 -SoApp                       # Comercial → "Potencial de Mercado MG"
  ```
- **Cuidado ao mexer:** não remover o `import pandas` de `app/components/ui.py` por
  parecer sem uso (há teste), e não trocar a orientação dos anéis em
  `simplificar_malha` — os dois derrubam os mapas de forma silenciosa.

---

## 2026-09-05 09:40 - Claude Code (Opus 5) - Análise geográfica de potencial de mercado MG

- **Feito:**
  - Nova camada geográfica de mercado para Minas Gerais, com três camadas sobrepostas
    (venda por cidade · território dos RCAs · mercado potencial de farinha) e a matriz
    de White Space que sai da sobreposição.
  - Descoberta da fonte que viabilizou a camada 3: agregado **9528 do CEMPRE/IBGE**, o
    único que publica unidades locais e pessoal ocupado por **município × classe CNAE**
    (os demais agregados com CNAE detalhada param no nível de UF). Referência 2024.
  - `src/ingestion/mercado_ibge.py` (IBGE com retry/cache), `src/staging/geografia.py`,
    `src/repositories/geo.py`, `migrations/007_mercado_geografico_mg.sql`,
    `config/mercado_mg.yaml`, `scripts/build_mercado_mg.py`,
    `app/pages/p13_potencial_mg.py` (6 abas), integração em `run_pipeline.py`.
  - `tests/test_mercado_mg.py` com 24 testes. Suíte completa: **99 passaram**.
    `ruff check`: limpo.
  - Relatório executivo publicado para o proprietário:
    https://claude.ai/code/artifact/9d607426-2cb7-4f3c-9e35-b5070d089b32
  - Docs: PRD.md, Task.md, Walkthrough.md reescritos; `docs/data_lineage.md` e
    `docs/open_questions.md` (Q-16) acrescidos; README atualizado.

- **Números que saíram** (janela de 12 meses até 2026-08, escopo FARINHAS/MISTURAS/BOLO):
  120 de 853 municípios com venda · 2.877 t/mês vendidas · 19.186 t/mês endereçáveis
  (share de 15,0%) · **1.775 t/mês de espaço não atendido (+61,7%)** · 219 municípios
  em White Space · 32 municípios concentram 92% da venda · Belo Horizonte, Varginha,
  Juiz de Fora e Pouso Alegre concentram 76% do espaço.

- **Dois erros encontrados e corrigidos durante a construção** (ambos com teste agora):
  1. O pareamento por similaridade simples levou `GOIÂNIA`→*Goianá*, `ANÁPOLIS`→
     *Canápolis* e `IRAÍ`→*Miraí* — cidades de fora de MG pintadas no mapa de MG.
     Passou a exigir primeiro token idêntico e a recusar empates técnicos.
  2. O corte de percentil de venda calculado sobre os 853 municípios caía em zero (733
     não vendem) e classificava todo o estado como "venda alta", deixando o White Space
     com 2 municípios. Passou a ser calculado só entre os que vendem; venda zero é
     sempre venda baixa. White Space foi de 2 para 219.

- **Não feito:**
  - Probabilidades de captura por segmento **não homologadas** pela área comercial
    (Q-16). Três segmentos (massas, pratos prontos, atacado de alimentos) usam consumo
    de `FALLBACK` por terem menos de 5 clientes na amostra.
  - Cruzamento do CNPJ dos clientes com a base aberta da Receita Federal, que é o que
    permitiria calibrar consumo por porte real em vez de perfil comercial.
  - Conciliação das duas abas divergentes do arquivo de território (decisão comercial,
    não de ETL — ambas ficaram preservadas com a coluna `fonte`).
  - Identificação de pizzarias dentro do CNAE 56.11-2 por razão social/nome fantasia.

- **Próximo passo:** levar a tabela de probabilidade de captura (Q-16 em
  `docs/open_questions.md`) para validação da direção comercial. Enquanto ela não for
  homologada, o potencial ordena prioridade entre municípios mas não vira orçamento.

- **Como validar:**
  ```powershell
  py scripts/build_mercado_mg.py     # espera: 853 municípios, 150/150 cidades de cliente
  py -m pytest tests/test_mercado_mg.py    # 24 testes
  py -m pytest                              # 99 testes
  .\_start.ps1 -SoApp                       # Comercial → "Potencial de Mercado MG"
  ```

- **Cuidado ao mexer:** `analytics.map_cidade_ibge` é o ponto de integração de tudo.
  Afrouxar o limiar de pareamento volta a colocar cidade de outro estado no mapa de
  Minas — os testes `test_cidade_de_outro_estado_nao_e_forcada_para_mg` e
  `test_grafia_ambigua_nao_escolhe_sozinha` existem exatamente para isso.
