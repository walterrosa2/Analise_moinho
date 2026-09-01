# Plataforma Analítica do Diagnóstico Comercial
### Moinho Sete Irmãos

Laboratório de diagnóstico empresarial para os consultores de gestão: parte de uma pergunta
executiva e chega ao documento fiscal que a originou, com reconciliação e rastreabilidade em
cada passo.

> **Dados brutos → reconciliação → modelo analítico confiável → exploração → drill-down →
> insight → hipótese → nova investigação.**

---

## Início rápido

```powershell
.\_start.ps1
```

O script cria o `.env`, prepara o ambiente virtual, sobe o PostgreSQL, executa o pipeline e abre
a aplicação em <http://localhost:8501>.

| Comando | O que faz |
|---|---|
| `.\_start.ps1` | fluxo completo |
| `.\_start.ps1 -SoApp` | só a aplicação (banco já carregado) |
| `.\_start.ps1 -Recarregar` | força recarga de todas as fontes |
| `_start.bat` | equivalente em CMD |

### Passo a passo manual

```bash
copy .env.example .env          # revise a senha do banco
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d postgres
set PYTHONPATH=.
.venv\Scripts\python.exe scripts\run_pipeline.py
.venv\Scripts\python.exe -m streamlit run app\main.py
```

---

## O que está pronto

**Ingestão** — 8 planilhas, 269.138 linhas, carga idempotente por hash SHA-256, em ~80 segundos.
Os arquivos originais nunca são tocados.

**Modelo** — 6 dimensões, 9 fatos, 1 ponte CT-e↔NF-e, 11 materialized views.
`NUNOTA + SEQUENCIA` verificado como grão único das 204.037 linhas de item.

**Confiabilidade** — 23 verificações automáticas de qualidade e 1.064 pontos de reconciliação
contra o relatório gerencial 161. A reconciliação mensal fecha em **43/43 meses dentro de 0,5%**,
com divergência média de **0,05%**.

**Aplicação** — 13 páginas, filtros globais consistentes, drill-down até o item da nota,
exportação carimbada, construtor de visões e insights quantitativos com evidência.

**Testes** — 59 testes, incluindo a renderização real de todas as telas contra o banco carregado.

---

## As páginas

| # | Página | Para quê |
|---|---|---|
| 1 | **Visão Geral** | ponto de entrada: KPIs, séries, insights automáticos |
| 2 | **Qualidade e Reconciliação** | o que é confiável, o que diverge, o que aguarda decisão |
| 3 | **Gestão Diária e Mix** | curvas por classificação, mix 100%, waterfall, orçado × realizado |
| 4 | **Vendas e Devoluções** | drill-down `classificação → produto → região → RCA → cliente → NF → item` |
| 5 | **Regional e Territorial** | mapa, matriz regional, concentração na liderança, cobertura |
| 6 | **RCAs e Vendedores** | scorecard, quadrante, dependência de carteira |
| 7 | **Clientes** | movimento da base, matriz crescimento × contribuição, RFM |
| 8 | **Positivados e Coortes** | entrada de clientes, retenção, recompra 30/60/90/180/365 dias |
| 9 | **Custos** | seis conceitos lado a lado, PMV × custo, dispersão entre bases |
| 10 | **Logística e CT-e** | frete R$/t por rota, transportador e cliente; % não alocado |
| 11 | **Trigo × Custo × PMV** | correlação exploratória com defasagem de 0 a 6 meses |
| 12 | **Explorador** | monta e salva visões novas, sem alterar código |
| 13 | **Admin e Diagnóstico** | estado do banco, cargas, configuração, auditoria |

---

## Arquitetura

```text
Streamlit (app/)          nenhuma linha de SQL nas páginas
      ↓
Serviços e insights (src/analytics, src/insights)
      ↓
Registro de métricas (src/metrics)     fórmula, grão, unidade, status
      ↓
Repositórios (src/repositories)        única camada que escreve SQL
      ↓
PostgreSQL 16             raw · staging · analytics · app
```

A separação permite trocar Streamlit por FastAPI + React sem tocar em regra analítica.

```text
moinho-analytics/
├── app/          interface Streamlit (main + 13 páginas + componentes + estado)
├── src/          ingestão · staging · db · repositórios · métricas · insights · reconciliação
├── config/       contratos de fonte e parâmetros de negócio (nada de hardcode)
├── migrations/   SQL versionado, aplicado por checksum
├── scripts/      profiling, contratos, pipeline, geração de docs
├── docs/         perfil, dicionário, regras, linhagem, decisões, dúvidas em aberto
├── tests/        59 testes
└── data/         input · parquet · exports  (fora do controle de versão)
```

---

## Princípios que o código respeita

Não são slogans: cada um tem teste ou verificação automática associada.

1. **Os arquivos originais nunca são modificados.** O pipeline lê uma cópia própria.
2. **Medida de documento não se soma no grão de item.** Somar `VLRNOTA` por item infla a receita
   em **321,7%**; o frete da carga, em **1.788,3%**. As colunas não existem em `fact_venda_item`.
3. **Devolução mantém o sinal da origem.** Nenhum `ABS()`, nenhum `CASE`.
4. **Nenhum custo é "o custo".** Os seis conceitos coexistem; o resultado é sempre
   **Margem Proxy — Base &lt;CUSTO&gt;**, com aviso permanente.
5. **Nada é ajustado para "bater".** Divergência com o gerencial fica visível e explicada.
6. **O rateio de frete nunca é escondido.** 15,52% do frete não é alocado — e o número aparece
   em toda tela de logística.
7. **Papel de vendedor não é inferido pelo nome.** Vem de `config/seller_roles.yaml`; casos
   ambíguos ficam `NAO_CLASSIFICADO` até o negócio decidir.
8. **Correlação não é causalidade.** A página de trigo diz isso explicitamente.
9. **Baixa venda não é baixo potencial de mercado.** A plataforma mede performance interna.
10. **Credenciais nunca entram no sistema.** A coluna de senhas do inventário é bloqueada na
    leitura — não chega nem à camada RAW.
11. **CNPJ/CPF entra apenas como hash.**
12. **Anomalias históricas são preservadas.** Sinalizadas, nunca excluídas.

---

## O que fazer antes de apresentar números ao cliente

Quatro decisões de negócio estão pendentes e afetam o que a plataforma mostra. Todas estão
documentadas em [`docs/open_questions.md`](docs/open_questions.md):

| # | Pendência | Impacto | Quem decide |
|---|---|---|---|
| Q-01 | Códigos que são canais, não pessoas (`V DIRETA FARELO` = 10,3% da receita) | alto — distorce ranking de RCA | diretoria comercial |
| Q-04 | Qual conceito de custo representa a economia do negócio | alto — muda toda margem | controladoria |
| Q-15 | Unidade do custo e outliers extremos na origem | alto — já tratado, aguarda confirmação | controladoria + TI |
| Q-12 | Homologação do mapa produto → classificação | médio — única causa da divergência residual | consultor comercial |

Enquanto abertas, as métricas dependentes ficam marcadas `PROVISIONAL` na tela de Qualidade.

---

## Comandos úteis

```bash
py scripts/run_pipeline.py                  # carga incremental
py scripts/run_pipeline.py --forcar         # recarga completa
py scripts/run_pipeline.py --etapa views    # só atualizar as views
py scripts/profile_sources.py               # reperfila as fontes
py scripts/gen_docs.py                      # regenera dicionário e reconciliação
pytest                                      # suíte completa
ruff check src/ app/ scripts/ tests/        # lint
docker compose logs -f postgres             # log do banco
```

---

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [`docs/source_profile.md`](docs/source_profile.md) | perfil real das 8 fontes (leitura, não suposição) |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | dicionário gerado do schema do banco |
| [`docs/business_rules.md`](docs/business_rules.md) | 15 regras de negócio, cada uma com evidência |
| [`docs/open_questions.md`](docs/open_questions.md) | 15 dúvidas abertas, com default e impacto |
| [`docs/decisions.md`](docs/decisions.md) | 11 decisões de arquitetura e seus porquês |
| [`docs/data_lineage.md`](docs/data_lineage.md) | de onde vem cada número |
| [`docs/reconciliation.md`](docs/reconciliation.md) | modelo × gerencial, ponto a ponto |
| [`PRD.md`](PRD.md) · [`Walkthrough.md`](Walkthrough.md) | produto e evidências de funcionamento |

---

## Fora do escopo desta entrega

Forecast por IA, recomendação automática de preço, potencial de mercado externo, otimização de
rotas, CRM, integração online com Sankhya, ETL em tempo real, recomendação sobre pessoas, e
margem contábil oficial sem validação da Controladoria.

A arquitetura está preparada para recebê-los — a camada de serviços é independente da interface.
