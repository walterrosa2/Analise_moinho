# Dúvidas Abertas de Negócio

Registro das decisões que **não** foram tomadas em silêncio. Cada uma tem: o que foi observado,
o default adotado (sempre configurável), o impacto de errar, e quem decide.

Regra da plataforma: enquanto uma pergunta estiver aberta, a métrica dependente fica marcada
`PROVISIONAL` na tela de Qualidade.

---

## Q-01 · Códigos de vendedor que são canais, não pessoas — **ALTO IMPACTO**

**Observado:** 5 dos 34 códigos com movimento aparentam ser canais de venda, não representantes:

| CODVEND | Apelido | TipoVend | Receita | % |
|---|---|---|---|---|
| 457 | V DIRETA FARELO | R - Representante | R$ 53.318.456,57 | 10,29% |
| 44 | TELEMK / BALCAO | S - Supervisor | R$ 680.370,90 | 0,13% |
| 6 | COML CAIAPONIA | R - Representante | R$ 2.124.800,50 | 0,41% |
| 467 | TITAN REPRESENT | R - Representante | R$ 384.734,11 | 0,07% |
| 382 | VDA SUBPRODUTO | R - Representante | R$ 177.413,56 | 0,03% |

**Default adotado:** `papel_analitico = NAO_CLASSIFICADO` em `config/seller_roles.yaml`, com o
motivo registrado. Não são contados como RCA em rankings de produtividade, e aparecem à parte.

**Impacto de errar:** tratar "V DIRETA FARELO" como RCA cria um representante fictício com 10% da
receita e distorce todo o comparativo de produtividade.

**Decide:** consultor de gestão comercial + diretoria comercial do Moinho.

---

## Q-02 · `CODVEND = 0` — MÉDIO

**Observado:** 522 linhas, R$ 54.270,27, 13 clientes, sem correspondência no cadastro.

**Default:** membro `NAO_IDENTIFICADO` na dimensão; incluído nos totais da empresa, excluído dos
rankings por vendedor (e o fato é exibido).

**Decide:** TI do Moinho (é código de sistema? venda sem vendedor atribuído?).

---

## Q-03 · Semântica de `ORC/ANT` no arquivo 161 OUTROS — MÉDIO

**Observado:** coluna com 396 valores distintos, um por `ANO+MES+DESCRICAO`. O rótulo admite
"Orçado" ou "Ano Anterior" — significados opostos para análise de desempenho.

**Default:** coluna carregada com o nome original (`orc_ant`), marcada
`pending_business_validation`. Nenhuma análise de "orçado × realizado" usa esse campo até a
definição; a página de Gestão Diária usa o `TIPO = 'ORÇADO'` do arquivo 161 principal, que é
inequívoco.

**Decide:** controladoria.

---

## Q-04 · Conceito de custo para margem — **ALTO IMPACTO**

**Observado:** seis conceitos coexistem (`CUSMED`, `CUSMEDICM`, `CUSSEMICM`, `CUSREP`, `CUSGER`,
`CUSVARIAVEL`) sem definição econômica homologada.

**Default:** nenhum é eleito. A UI obriga a escolha e rotula o resultado como
**"Margem Proxy — Base &lt;CUSTO&gt;"**, com aviso permanente na página de Custos. O modo
"Comparar todos" mostra a dispersão entre conceitos.

**Decide:** controladoria do Moinho.

---

## Q-05 · Data de referência para o custo — MÉDIO

**Observado:** o item tem `DTNEG`, `DTFATUR` e `DTENTSAI`; o custo tem `DTATUAL`.

**Default:** `DTFATUR` (`.env: COST_REFERENCE_DATE_FIELD`), conforme sugere a especificação.

**Impacto:** em produto com custo volátil, trocar a data desloca a margem proxy. `cost_age_days`
permite medir a sensibilidade.

**Decide:** controladoria.

---

## Q-06 · `CODLOCAL = 0` na tabela de custos — BAIXO

**Observado:** a tabela de custos tem `CODLOCAL ∈ {0, 106001…107001}`; as vendas usam apenas
`106001…107001`. O que é o local 0?

**Default:** cascata do as-of join (RN-07) — tenta local exato, depois empresa, depois produto —
com `cost_match_status` registrando qual nível resolveu.

**Decide:** TI/controladoria.

---

## Q-07 · Modalidade de frete `T` e `R` — BAIXO

**Observado:** 6 linhas com `T` (sem descrição na origem) e 1 com `R - Transp. Próprio Remetente`.

**Default:** normalizados e mantidos como categorias próprias; `T` fica com rótulo
"T — não documentado".

**Decide:** logística.

---

## Q-08 · CT-e sem NF-e correspondente (4,54%) — MÉDIO

**Observado:** 1.844 das 40.645 chaves NF-e citadas nos CT-e não existem na base de vendas.
A amostra inclui chave de 2021 (`3121030106458…`), anterior à janela da base.

**Hipótese** (não confirmada): frete de notas fora do período extraído.

**Default:** `match_status = SEM_VINCULO`; frete correspondente **não** é distribuído e entra no
indicador de "% não alocado".

**Decide:** TI do Moinho (ampliar a extração resolveria?).

---

## Q-09 · Operação `4103 LANCTO FRETE S/ COMPRA INSUMOS/REMESSAS` — BAIXO

**Observado:** 4 CT-e dessa operação não são frete de venda.

**Default:** carregados, marcados `is_frete_venda = FALSE`, fora do custo logístico de venda.

**Decide:** logística/controladoria.

---

## Q-10 · Cobertura territorial incompleta no mapa de regiões — MÉDIO

**Observado:** 12 códigos que vendem não constam no arquivo de região comercial
(`0, 6, 17, 24, 44, 49, 382, 446, 456, 457, 467, 470`) — entre eles o 17 (5,96% da receita)
e o 24 (2,36%). O arquivo também traz sujeira: `ESTADO = 'Califórnia, EUA'` e `'San José, Costa Rica'`.

**Default:** a região comercial vem primeiro do movimento (`CODREG`/`NOMEREG`, sempre presente);
o arquivo é fonte complementar de nomenclatura. Linhas inconsistentes são sinalizadas, não descartadas.

**Decide:** consultor comercial + área comercial do Moinho.

---

## Q-11 · Bonificações e amostras no PMV — MÉDIO

**Observado:** 1.564 linhas com tonelagem e receita zero (RN-04).

**Default:** excluídas do PMV; incluídas no volume total. A UI informa a exclusão e permite inverter.

**Decide:** consultor comercial.

---

## Q-12 · Reconciliação 161 × modelo: períodos diferentes — MÉDIO

**Observado:** o 161 cobre 2020–2026; a base transacional, 2023–2026. Além disso, o 161 agrega por
classificação (`FARINHAS`, `FARELO`, `MISTURAS`, `BOLO`) e a base transacional traz `CODPROD`,
sem um campo de classificação nativo.

**Default:** o mapa `CODPROD → classificação` fica em `config/product_classification.yaml`,
versionado, derivado do grupo de produto e da descrição, com cada produto exibindo a origem da
classificação. A reconciliação roda só na janela comum.

**Decide:** consultor comercial homologa o mapa produto → classificação.

---

## Q-13 · `Vr ICMS` e `Vr Comissão` do 161 OUTROS não são reproduzíveis pelo transacional — MÉDIO

**Observado** (jan–mar/2025):

| Mês | `Vr ICMS` (161 OUTROS) | `SUM(VLRICMS)` do modelo | `Vr Comissão` (161) | `SUM(VLRCOM)` do modelo |
|---|---|---|---|---|
| 2025-01 | R$ 215.286,83 | R$ 798.898,85 | R$ 124.831,47 | ~R$ 1,1 mi |
| 2025-02 | R$ 219.207,48 | R$ 800.865,91 | R$ 119.467,65 | — |
| 2025-03 | R$ 233.636,32 | R$ 784.163,71 | R$ 123.167,05 | — |

O ICMS do gerencial é ~27% do ICMS destacado nas notas. A hipótese mais provável é que
`Vr ICMS` seja **ICMS a recolher** (débito menos crédito de entrada), não o ICMS destacado —
mas a base transacional atual não contém créditos de entrada, então o modelo **não consegue**
reproduzir esse número. Comissão apresenta divergência análoga.

**Default:** as duas métricas ficam `DIVERGENTE` na tela de Reconciliação com esta explicação
anexada. Nenhum ajuste é feito para forçar o encaixe.

**O que destravaria:** extração de apuração de ICMS e do relatório de comissões liberadas
(`130`/`131` do inventário Sankhya, já catalogados).

**Decide:** controladoria.

---

## Q-14 · Divergência residual por classificação no 161 — BAIXO (causa isolada)

**Observado:** a reconciliação mensal **sem** quebra por classificação fecha em **86/86 pontos
dentro de 0,5%, com divergência média de 0,053%**. Quebrando por classificação, cerca de metade
dos pontos fica fora da tolerância, com divergência média de ~2,3%.

**Conclusão:** o pipeline reproduz o gerencial. A divergência restante vem **exclusivamente** da
regra produto → classificação (Q-12), que ainda é `PROVISIONAL`.

**Decide:** homologação do mapa de classificação (Q-12) resolve os dois itens.

---

## Q-15 · Unidade e outliers do custo — **ALTO IMPACTO** (tratado, aguarda confirmação)

### Parte A — unidade do custo (resolvido por evidência)

O custo de `fact_custo_pa` está na **unidade de venda** (FD, SC, CX, KG, PT), a mesma de
`VLRUNIT` — **não** por tonelada:

| CODPROD | Produto | `VLRUNIT` médio | `CUSGER` mediano |
|---|---|---|---|
| 20059 | FAR.LUNAR PREMIUM 25KG | R$ 91,52 | R$ 47,49 |
| 20024 | FAR.LUNAR PLUS 25KG | R$ 80,67 | R$ 50,05 |
| 20007 | FAR.LUNAR PP 1KG | R$ 32,62 | R$ 22,36 |
| 20029 | FARELO IDEAL 40KG | R$ 72,84 | R$ 58,83 |

A fórmula correta é `custo_total = QTD × custo_unitário`. A fórmula inicial
(`TONLIQ × custo`) produzia margem proxy de **98,7%**, economicamente impossível.

### Parte B — outliers na fonte (tratado, não corrigido)

A fonte de custo tem valores extremos pontuais, do mesmo produto:

| CODPROD | Produto | mín. `CUSGER` | máx. `CUSGER` | mediana |
|---|---|---|---|---|
| 20036 | FAR.LUNAR 25KG | R$ 0,96 | **R$ 341.322,41** | R$ 47,08 |
| 20048 | P.M.LUNAR MIX PREM 25KG | R$ 24,16 | **R$ 332.804,49** | R$ 50,47 |
| 20128 | FAR.TIA NENA 25KG | **−R$ 0,66** | **R$ 341.323,81** | R$ 48,38 |

**Tratamento** (a especificação proíbe corrigir ou excluir dado da origem):

1. O dado bruto permanece intacto em `raw.*` e `analytics.fact_custo_pa`.
2. Cada item recebe a flag `custo_outlier` — custo aplicado acima de 5× a mediana do próprio
   produto, ou não positivo (critério estatístico, não econômico).
3. Os agregados de custo excluem os outliers e **informam quantas linhas ficaram de fora**.
4. A margem compara receita e custo da **mesma população** de linhas (`receita_com_custo`).

**Resultado após o tratamento** — margem proxy estável e plausível:

| Ano | Receita comparável | Custo (CUSGER) | Margem proxy | Linhas excluídas |
|---|---|---|---|---|
| 2023 | R$ 141,34 mi | R$ 103,75 mi | 26,60% | 571 (0,98%) |
| 2024 | R$ 149,76 mi | R$ 108,02 mi | 27,87% | 460 (0,81%) |
| 2025 | R$ 144,69 mi | R$ 104,94 mi | 27,47% | 185 (0,34%) |
| 2026 | R$ 80,19 mi | R$ 59,29 mi | 26,06% | 30 (0,09%) |

**O que ainda precisa de confirmação:** a Controladoria deve validar (a) que a unidade do custo é
mesmo a de venda e (b) que os extremos são erro de cadastro no ERP, não um conceito de custo
diferente aplicado em datas específicas.

**Decide:** controladoria + TI do Moinho.
