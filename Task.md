# Task — Análise Geográfica de Potencial de Mercado (MG)

Legenda: `[x]` concluído · `[ ]` pendente

## Fontes externas (IBGE)

- [x] Localizar o agregado do IBGE que publica empresas por **município e classe CNAE**
      (9528 — CEMPRE, referência 2024; os agregados com CNAE detalhada só chegam a UF).
- [x] Cliente HTTP com gzip, timeout e retry com backoff (`src/ingestion/mercado_ibge.py`).
- [x] Baixar 853 municípios de MG com hierarquia regional oficial.
- [x] Baixar população residente do Censo 2022 (20.539.989 habitantes).
- [x] Baixar unidades locais e pessoal ocupado dos 8 segmentos CNAE do escopo.
- [x] Baixar a malha municipal (GeoJSON) para o mapa.
- [x] Cache em parquet; sem rede, o pipeline segue com o cache.

## Modelo de dados

- [x] Migration `007_mercado_geografico_mg.sql`: 5 tabelas + 2 materialized views.
- [x] `dim_municipio_mg` — os 853 municípios, o denominador de toda cobertura.
- [x] `map_cidade_ibge` — pareamento auditável grafia → código IBGE, com método por linha.
- [x] `fact_mercado_cnae` — estabelecimentos e porte por município e segmento.
- [x] `dim_territorio_rca` — as duas abas do arquivo de território, ambas preservadas.
- [x] `fact_potencial_municipio` — potencial estimado em t/mês.
- [x] `mv_vendas_municipio_mg` e `mv_mercado_municipio_mg`.

## Staging

- [x] Normalização de nome de cidade (acento, pontuação, sufixo de UF, prefixo de código).
- [x] Pareamento em 4 níveis: `EXATO` → `SEM_CONECTIVOS` → `APROXIMADO` → `AMBIGUO`/`NAO_ENCONTRADO`.
- [x] Endurecer o pareamento após 4 falsos positivos (Goiânia→Goianá, Anápolis→Canápolis,
      Iraí→Miraí): exigir primeiro token igual e margem de desempate.
- [x] Resolver sigilo estatístico do IBGE sem disfarçar estimativa de dado publicado.
- [x] Calcular consumo mediano observado por segmento nos clientes reais do Moinho.
- [x] Calcular potencial com fator de porte limitado entre 0,5 e 2,5.

## Aplicação

- [x] `src/repositories/geo.py` — única camada com SQL da nova área.
- [x] Classificação de White Space por percentis configuráveis na tela.
- [x] Página `p13_potencial_mg.py` com 6 abas: Panorama, Camadas 1/2/3, Sobreposição, Decisão.
- [x] Mapa choropleth municipal com queda para ranking em barras quando a malha falta.
- [x] Registro em `app/main.py` e nas etapas de `scripts/run_pipeline.py`.
- [x] `scripts/build_mercado_mg.py` para reconstruir só o mercado.

## Configuração e documentação

- [x] `config/mercado_mg.yaml` — CNAEs, intensidades, probabilidades, cortes, URLs.
- [x] Cores dos quadrantes validadas para daltonismo nos temas claro e escuro.
- [x] `docs/data_lineage.md` — linhagem da camada e tabela fato × estimativa.
- [x] `docs/open_questions.md` — Q-16 (probabilidade de captura não homologada).
- [x] `PRD.md` e `Walkthrough.md`.
- [x] Relatório executivo publicado para o proprietário.

## Testes

- [x] 15 testes puros de normalização e pareamento (rodam sem banco).
- [x] 9 testes de integração da camada carregada.
- [x] Teste que a venda do mapa bate com o fato de venda em MG (divergência < 0,01%).
- [x] Teste que o repositório reproduz a materialized view na janela padrão.
- [x] Teste que município sem venda nunca é classificado como venda alta.

## Validação

| Comando | Resultado |
|---|---|
| `ruff check src app tests scripts` | **All checks passed** |
| `pytest tests/test_mercado_mg.py` | **24 passaram** |
| `pytest` (suíte completa) | **99 passaram**, 0 falhas |
| `pytest tests/test_paginas.py -k "p13 or main"` | **2 passaram** (renderização real) |

## Pendente (fora do escopo desta entrega)

- [ ] Homologar as probabilidades de captura com a direção comercial (Q-16).
- [ ] Cruzar CNPJ dos clientes com a base aberta da Receita Federal para calibrar
      consumo por porte real, em vez de perfil comercial.
- [ ] Conciliar as duas abas divergentes do arquivo de território (decisão comercial).
- [ ] Identificar pizzarias dentro do CNAE 56.11-2 por razão social e nome fantasia,
      como recomenda a pesquisa de mercado.
