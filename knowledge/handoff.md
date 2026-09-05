# Handoff entre agentes — Visao_moinho

Histórico em ordem inversa (mais recente no topo). Complementa
`knowledge/sessions.md`, que é gerado automaticamente e **não deve ser editado à mão**.

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
