# Handoff entre agentes — Visao_moinho

Histórico em ordem inversa (mais recente no topo). Complementa
`knowledge/sessions.md`, que é gerado automaticamente e **não deve ser editado à mão**.

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
