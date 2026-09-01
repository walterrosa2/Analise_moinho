# Feature Specification: Plataforma Analítica do Diagnóstico Comercial — Moinho Sete Irmãos

- **Versão:** 1.0
- **Data:** 2026-09-01
- **Fonte normativa:** `ESPECIFICACAO_TECNICA_PLATAFORMA_ANALITICA_MOINHO.md` (47 seções)
- **Evidência de Fase 0:** `docs/source_profile.md` + `artifacts/deep_checks.md` (leitura real dos 8 arquivos)

---

## 1. Objetivo

Construir um **laboratório de diagnóstico empresarial** — não um conjunto fixo de dashboards — que
permita a dois consultores de gestão partirem de uma pergunta executiva e chegarem ao documento
fiscal que a originou, com rastreabilidade e reconciliação em cada passo.

Princípio central:

> Dados brutos → reconciliação → modelo analítico confiável → exploração → drill-down → insight → hipótese → nova investigação.

---

## 2. User Stories

### Épico A — Confiança no dado

- **A1.** Como consultor de dados, quero que toda carga seja idempotente e rastreada por hash de
  arquivo, para reexecutar o pipeline sem medo de duplicar dados.
- **A2.** Como consultor, quero uma tela de Qualidade e Reconciliação, para saber **antes** de
  apresentar um número se ele é confiável.
- **A3.** Como consultor, quero ver o percentual de frete não alocado e de CT-e sem NF-e vinculada,
  para nunca apresentar um custo logístico como se fosse completo.
- **A4.** Como consultor, quero que cada métrica exiba seu status (`PROVISIONAL`, `RECONCILIADA`,
  `HOMOLOGADA`) e sua fórmula, para explicar ao cliente de onde o número veio.

### Épico B — Exploração e drill-down

- **B1.** Como consultor comercial, quero filtros globais consistentes (período, empresa,
  classificação, produto, UF, região, vendedor, tipo de vendedor) aplicados a todas as páginas.
- **B2.** Como consultor, quero navegar `Empresa → classificação → produto → região → RCA → cliente
  → NF → item` com breadcrumb e botão "voltar nível".
- **B3.** Como consultor, quero comparar dois períodos (MoM, YoY, período livre) em qualquer visão.
- **B4.** Como consultor, quero exportar tabela (CSV/XLSX), gráfico (PNG) e os dados que geraram
  o gráfico, com o nome do arquivo carimbado (`view_YYYYMMDD_HHMM`).

### Épico C — Perguntas do diagnóstico

- **C1.** Como consultor, quero medir a concentração das grandes contas na liderança versus RCAs,
  para transformar percepção em fato. *(Evidência Fase 0: o CODVEND 4, tipo "S - Supervisor",
  concentra 32,85% da receita com 97 clientes.)*
- **C2.** Como consultor, quero comparar seis conceitos de custo contra o PMV sem que a plataforma
  eleja um "custo oficial".
- **C3.** Como consultor, quero analisar frete R$/t por rota, transportador, cliente e RCA,
  sabendo que o rateio de CT-e multi-NF é explícito.
- **C4.** Como consultor, quero coortes de positivados com recompra 30/60/90/180/365 dias,
  isolando o período de implantação do ERP.
- **C5.** Como consultor, quero correlacionar preço do trigo × custo PA × PMV com defasagem de
  0 a 6 meses, rotulado como exploratório e nunca como causal.
- **C6.** Como consultor, quero decompor uma variação de receita em efeito volume, efeito preço
  e efeito mix.

### Épico D — Autonomia do consultor

- **D1.** Como consultor sem SQL, quero montar uma visão nova escolhendo dimensões, métricas,
  gráfico, Top N e comparação temporal, sem alterar código.
- **D2.** Como consultor, quero salvar, duplicar e reabrir visões.
- **D3.** Como consultor, quero insights quantitativos automáticos, cada um com botão
  "Ver evidência" que abre a tabela que o originou.

---

## 3. Acceptance Criteria

Espelham a seção 41 da especificação técnica. Cada item é verificável por teste automatizado
(`tests/`) ou por inspeção da tela indicada.

| # | Critério | Verificação |
|---|---|---|
| AC-01 | Todos os 8 arquivos carregados por pipeline, sem passo manual | `pytest tests/test_ingestion.py` |
| AC-02 | Camada RAW preservada, sem conversão de valor | `tests/test_raw_fidelity.py` |
| AC-03 | Segunda carga do mesmo arquivo não duplica dados (idempotência por hash) | `tests/test_idempotencia.py` |
| AC-04 | `NUNOTA + SEQUENCIA` é PK de `fact_venda_item` (204.037 linhas, 0 duplicadas) | `tests/test_grao.py` |
| AC-05 | `VLRNOTA` e `VLRFRETE_ORDEMCARGA` residem apenas no grão de documento | `tests/test_regras_seguranca.py` |
| AC-06 | CT-e ↔ NF-e modelado por `bridge_cte_nfe` com peso de rateio explícito | `tests/test_bridge_cte.py` |
| AC-07 | Positivados explodidos: soma por mês = `QTD_POSITIVADOS` da fonte | `tests/test_positivados.py` |
| AC-08 | Seis bases de custo disponíveis e alternáveis na UI | Página Custos |
| AC-09 | As-of join de custos registra `cost_match_date`, `cost_age_days`, `cost_match_status` | `tests/test_asof_custos.py` |
| AC-10 | Filtros globais funcionam em todas as páginas | Página Visão Geral |
| AC-11 | Drill-down chega ao item/NF | Página Vendas |
| AC-12 | Visão regional separa REGIÃO COMERCIAL de GEOGRAFIA REAL | Página Regional |
| AC-13 | Vendas da liderança × RCA comparáveis | Página RCAs |
| AC-14 | Coortes de positivados disponíveis | Página Positivados |
| AC-15 | Período de implantação do ERP sinalizado e desligável | Página Positivados |
| AC-16 | Dashboard logístico com R$/t | Página Logística |
| AC-17 | % de frete não alocado visível | Página Logística |
| AC-18 | Reconciliação com o 161 visível | Página Qualidade |
| AC-19 | Usuário monta visão nova sem alterar código | Página Explorador |
| AC-20 | Usuário salva visão (`app.saved_views`) | Página Explorador |
| AC-21 | Exportação de tabela e gráfico com nome carimbado | Qualquer página |
| AC-22 | Insights com link para evidência | Página Visão Geral |
| AC-23 | Fórmulas documentadas no registro de métricas | Página Qualidade → Métricas |

---

## 4. Edge Cases (todos confirmados na Fase 0, não hipotéticos)

| # | Caso | Tratamento |
|---|---|---|
| EC-01 | Somar `VLRNOTA` no grão de item infla a receita em **321,7%** | Medida vive só em `fact_venda_documento`; teste bloqueia regressão |
| EC-02 | Somar `VLRFRETE_ORDEMCARGA` por item infla o frete em **1.788,3%** | Idem; deduplicação por `ORDEMCARGA` |
| EC-03 | `CIF_FOB` tem 8 grafias para 5 códigos (`C`, `C - CIF - …`, `F`, `F - FOB…`, `R`, `S`, `S - Sem Frete`, `T`) | Normalizar pela primeira letra; guardar valor bruto na RAW |
| EC-04 | 23.137 linhas (11,3%) são devoluções (`TIPMOV='D'`), 100% com valores negativos | Preservar o sinal; nunca usar `ABS()` |
| EC-05 | Operações `3107 SAIDA BONIFICAÇÃO` e `3102 AMOSTRA/DOAÇÃO` têm tonelagem mas `VLRTOT = 0` | Flag `is_sem_receita`; PMV as exclui por padrão (configurável) — senão o preço médio é subestimado |
| EC-06 | Números decimais chegam como texto pt-BR (`'1,9389'`, `'108,58'`) em `PERCCOM`, `VLRCOM`, `VLRUNIT`, `ACORDO` | Parser pt-BR dedicado no staging |
| EC-07 | Literal `'NULL'` como texto em `CIDORIGEM`, `UFORIGEM`, `CODTRIB`, `SERIENOTA`, `NOTAS_VENDA`, `PERC_ATING_VLR`… | Conversão para NULL real, sem preencher com zero |
| EC-08 | Campos texto com espaços à direita (`'UBERLANDIA          '`) | `TRIM` no staging; RAW intacta |
| EC-09 | 12,82% dos CT-e não têm `CHAVES_NFE_VENDA`; 55,89% não têm `ORDEMCARGA` válida | `match_status = SEM_VINCULO`; % exibido na UI |
| EC-10 | 4,54% das chaves NF-e citadas nos CT-e não existem na base de vendas | `match_status = SEM_VINCULO`; nunca descartar silenciosamente |
| EC-11 | Um CT-e cobre várias NF-e (41.037 vínculos para 32.789 CT-e) | Rateio `TON_WEIGHT`, gravado em `allocation_method` |
| EC-12 | `CHAVECTE` ausente em 1.134 CT-e (3,46%); `NUNOTA` repete 4 vezes | Surrogate key `frete_id`; nunca PK natural |
| EC-13 | 425 dos 458 vendedores cadastrados nunca venderam; só 34 têm movimento | Dimensão preserva o histórico; flag de atividade observada |
| EC-14 | `CODVEND = 0` movimenta R$ 54.270 e não existe no cadastro | Membro "não identificado" na dimensão, visível na tela de Qualidade |
| EC-15 | `CODSUPERVISOR` nulo em 7,45% das linhas (receita negativa: são devoluções) | NULL preservado |
| EC-16 | 15 linhas com `DTNEG` anterior a 2023 (mín. 2022-09-08), fora da janela declarada | Carregadas e sinalizadas; filtro sempre explícito |
| EC-17 | Fev/2021 tem 729 positivados (implantação do ERP) vs. mediana ~40 | `periodo_implantacao_erp = true`; análises começam em 2021-05 por padrão |
| EC-18 | Planilha de trigo tem cabeçalho de duas linhas e células mescladas; períodos reais são Compra Jan/24–Jul/26 e Estoque Jan/25–Jul/26 | Parser posicional dedicado; período real documentado |
| EC-19 | O inventário de fontes contém **senhas em texto claro** | Coluna de credenciais nunca é lida, nem para RAW; ver `docs/decisions.md` ADR-005 |
| EC-20 | 2 linhas de custo com `CUSREP`/`CUSGER`/`CUSVARIAVEL` negativos | Carregadas; sinalizadas como anomalia na tela de Qualidade |
| EC-21 | Arquivo `REGIÃO COMERCIAL POR REPRESENTANTE` não está na especificação, mas mapeia 35 regiões comerciais e 23 códigos de representante | Fonte adicional documentada; alimenta a dimensão territorial |
| EC-22 | `CODLOCAL = 0` existe na tabela de custo, mas as vendas usam `106001…107001` | As-of join com fallback hierárquico e status registrado |

---

## 5. Fora de escopo (seção 42 da especificação)

Forecast por IA, recomendação de preço, potencial de mercado externo, otimização de rotas, CRM,
integração online com Sankhya, ETL em tempo real, recomendação de desligamento de RCA, margem
oficial sem validação da Controladoria, causalidade trigo→qualidade.

A arquitetura, porém, é preparada para recebê-los (camada de serviços separada da UI).

---

## 6. Restrições invioláveis

1. Os arquivos originais nunca são modificados (leitura em cópia própria, `data/input/`).
2. Nenhum dado é excluído para "bater" com relatório gerencial; divergência é explicada.
3. Nenhum custo é eleito oficial; o termo é **Margem Proxy — Base <CUSTO>**.
4. Correlação nunca é apresentada como causalidade.
5. Baixa venda nunca é chamada de baixo potencial de mercado.
6. Papel de vendedor nunca é inferido pelo nome — vem de `config/seller_roles.yaml`.
7. NULL nunca é preenchido com zero indiscriminadamente.
8. Credenciais nunca entram no banco, no log ou na tela.
9. CNPJ/CPF entra no DW apenas como hash.
