# Regras de Negócio

Toda regra abaixo é **derivada de evidência** (`docs/source_profile.md`, `artifacts/deep_checks.md`)
ou explicitamente marcada como pendente de validação. Nenhuma foi inferida por semelhança de nome.

Status possíveis: `CONFIRMADA` (verificada nos dados) · `CONFIGURAVEL` (default explícito em
`config/`) · `PENDENTE` (aguarda validação do negócio — ver `docs/open_questions.md`).

---

## RN-01 · Grão da venda — CONFIRMADA

`NUNOTA + SEQUENCIA` identifica unicamente o item: 204.037 linhas, 204.037 combinações distintas,
zero duplicadas. `NUNOTA` sozinho repete-se 116.763 vezes (87.274 documentos).

**Implicação:** `fact_venda_item` usa a chave composta; medidas de documento vão para
`fact_venda_documento`.

---

## RN-02 · Proibição de somar medidas de documento no grão de item — CONFIRMADA

| Medida | Soma no grão de item | Soma correta | Distorção |
|---|---|---|---|
| `VLRNOTA` | R$ 2.185.853.640,62 | R$ 538.524.255,15 (dedup. por `NUNOTA`) | **+321,7%** |
| `VLRFRETE_ORDEMCARGA` | R$ 564.113.037,16 | R$ 29.874.498,13 (dedup. por `ORDEMCARGA`) | **+1.788,3%** |

`VLRNOTA` nunca varia entre os itens da mesma nota (0 casos), confirmando que é atributo do documento.

**Implicação:** essas colunas não existem em `fact_venda_item`. O teste
`tests/test_regras_seguranca.py` falha se forem reintroduzidas.

---

## RN-03 · Devolução e sinal — CONFIRMADA

`TIPMOV` tem exatamente dois valores: `V` (180.900 linhas) e `D` (23.137 linhas, 11,3%).
**100% das linhas `D` têm `VLRTOT < 0` e `TONLIQ < 0`** — a origem já traz o sinal.

- Receita líquida = `SUM(VLRTOT)` — sem `ABS`, sem `CASE`.
- Vendas brutas = `SUM(VLRTOT) WHERE NOT is_devolucao`.
- Devoluções = `SUM(VLRTOT) WHERE is_devolucao` (valor negativo, exibido como tal).

Totais da base: vendas R$ 525.543.817,38 · devoluções −R$ 7.188.133,12 · **líquido R$ 518.355.684,26**
(201.102,99 t − 2.312,96 t = 198.790,03 t líquidas).

---

## RN-04 · Operações sem receita — CONFIRMADA, tratamento CONFIGURAVEL

Duas operações movimentam tonelagem com `VLRTOT = 0`:

| CODTIPOPER | DESCROPER | Linhas | Σ VLRTOT |
|---|---|---|---|
| 3107 | SAIDA BONIFICAÇÃO | 997 | 0,00 |
| 3102 | SAIDA AMOSTRA, DOACAO OU BRINDE | 567 | 0,00 |

Incluí-las no PMV rebaixa o preço médio artificialmente (tonelada no denominador, zero no numerador).

**Regra:** `is_sem_receita = TRUE` para essas operações. O PMV **exclui** essas linhas por padrão;
a UI oferece a alternativa e informa quantas linhas foram excluídas.

---

## RN-05 · Modalidade de frete — CONFIRMADA

`CIF_FOB` chega com 8 grafias para 5 códigos. A primeira letra é o código; o restante, descrição.

| Bruto | Normalizado | Linhas |
|---|---|---|
| `C - CIF - Contratação do Frete por conta do Remetente`, `C` | `C` — CIF | 158.856 |
| `S`, `S - Sem Frete` | `S` — Sem frete | 26.584 |
| `F - FOB - Contratação…`, `F` | `F` — FOB | 18.590 |
| `T` | `T` — a validar | 6 |
| `R - Transp. Próprio Remetente` | `R` — Transporte próprio | 1 |

O valor bruto permanece na camada RAW; a normalização acontece no staging.

---

## RN-06 · Papel analítico do vendedor — CONFIGURAVEL, **NÃO HOMOLOGADA**

Dos 458 códigos cadastrados, **apenas 34 têm movimento**. O default vem do campo `TipoVend` do ERP
(dado, não inferência): `S - Supervisor` → `SUPERVISOR`; `R - Representante` → `RCA`;
`V - Vendedor` → `INTERNO`.

**Ressalva registrada:** vários códigos são canais, não pessoas — `457 V DIRETA FARELO` (10,29% da
receita), `44 TELEMK / BALCAO`, `382 VDA SUBPRODUTO`, `6 COML CAIAPONIA`, `467 TITAN REPRESENT`.
Classificá-los como RCA distorceria qualquer ranking de produtividade. A especificação proíbe
inferir papel pelo nome, portanto o arquivo `config/seller_roles.yaml` traz a lista com
`papel: NAO_CLASSIFICADO` e o motivo, aguardando decisão do cliente.

**Concentração observada (fato, não julgamento):** `CODVEND 4` (`S - Supervisor`) responde por
**32,85% da receita** — R$ 170.285.719,43 — atendendo 97 clientes. Somados os quatro supervisores,
**36,23%** da receita não passa por representante.

`CODVEND = 0` (522 linhas, R$ 54.270,27, 13 clientes) não existe no cadastro: entra na dimensão
como membro `NAO_IDENTIFICADO`, exibido na tela de Qualidade.

---

## RN-07 · As-of join de custos — CONFIRMADA (mecânica) / CONFIGURAVEL (data de referência)

Cobertura: **100% dos 100 produtos vendidos têm custo cadastrado** (a tabela de custo tem 101).
`CODPROD+CODEMP+CODLOCAL+DTATUAL` é único (29.135 linhas, 1.085 datas distintas).

Cascata de correspondência, registrando sempre o resultado:

1. `CODPROD + CODEMP + CODLOCAL` com `DTATUAL <= data_referencia` (mais recente)
2. `CODPROD + CODEMP` (a tabela de custo contém `CODLOCAL = 0`, que as vendas não usam)
3. `CODPROD` isolado
4. Nenhum → `cost_match_status = 'SEM_CUSTO'`

Registrados por item: `cost_match_date`, `cost_age_days`, `cost_match_status`.
Data de referência padrão: `DTFATUR` (`.env: COST_REFERENCE_DATE_FIELD`).

**Os seis custos coexistem. Nenhum é "o custo".** Qualquer diferença é
**"Margem Proxy — Base &lt;CUSTO&gt;"**, nunca "margem".

---

## RN-08 · Rateio de frete CT-e → NF-e — CONFIRMADA

Um CT-e cobre várias NF-e: 32.789 CT-e geram **41.037 vínculos** após explodir
`CHAVES_NFE_VENDA` por `;`.

Cobertura real:

- 12,82% dos CT-e (4.203) **não têm** `CHAVES_NFE_VENDA`;
- 55,89% (18.325) não têm `ORDEMCARGA` válida — confirma que ordem de carga **não** serve como
  chave única de relacionamento;
- das 40.645 chaves NF-e citadas, **95,46% encontram** a venda; 4,54% (1.844) não.

Rateio: `frete_NF = VLRNOTA_CTE × TON_NF / TON_total_do_CTE`, `allocation_method = 'TON_WEIGHT'`.
Sem tonelagem disponível → `EQUAL_SPLIT`. Nada é escondido: a UI mostra sempre
**% de frete não alocado** e **% de CT-e sem NF-e**.

**Chave primária:** o surrogate `frete_id`. `CHAVECTE` é única quando presente, mas está
**ausente em 1.134 CT-e (3,46%)**, e `NUNOTA` repete 4 vezes — nenhuma das duas serve como PK.

> Correção de leitura: o profiling inicial apontou "1.133 duplicatas de `CHAVECTE`". Eram o
> literal `'NULL'` contado como valor. Após a conversão para NULL real no staging, **zero**
> chaves repetem. O surrogate continua necessário — pela ausência, não pela repetição.

Operações presentes: `2107 AQUISIÇÃO FRETE VENDAS - CTE` (31.646), `2162 SERVIÇO FRETE NF PRESTAÇÃO`
(1.135), `3111 ENTRADA CTE ANULADO` (4 — sinalizada), `4103 LANCTO FRETE S/ COMPRA` (4 — não é
frete de venda, excluída do custo logístico de venda e registrada).

---

## RN-09 · Positivados — CONFIRMADA

A explosão de `PARC_POSITIVADOS` (lista separada por vírgula) **bate exatamente** com
`QTD_POSITIVADOS` nos 67 meses: zero divergências. Total: 2.871 clientes distintos.

77,8% deles aparecem na base de vendas — a diferença é esperada (positivados cobrem 2021+,
vendas começam em 2023), não é erro.

**Período de implantação do ERP** (`periodo_implantacao_erp = TRUE`): 2021-02 (729), 2021-03 (274),
2021-04 (103) — contra mediana de ~40. Os dados **não são excluídos**; as análises de tendência
começam em `2021-05` por padrão, com caixa de seleção para incluir o período.

---

## RN-10 · Região comercial ≠ geografia real — CONFIRMADA

São duas dimensões distintas e nunca intercambiáveis:

- **Região comercial:** `CODREG`/`NOMEREG` no movimento (98 códigos) e o mapa
  `REGIÃO COMERCIAL POR REPRESENTANTE` com **35 regiões nomeadas** (Triângulo Mineiro, Sul Goiano,
  Sinop, Plano Piloto…).
- **Geografia real do cliente:** `UFPARC` (13 UFs) e `NOMECIDPARC` (228 cidades).

O arquivo de região traz `CÓDIGO-REPRESENTANTE` para 23 representantes; 22 têm movimento.
Doze códigos que vendem não constam nele (`0, 6, 17, 24, 44, 49, 382, 446, 456, 457, 467, 470`) —
lacuna de cobertura territorial exibida na tela de Qualidade.

A plataforma mede **performance interna**. Baixa venda em uma região nunca é rotulada como baixo
potencial de mercado.

---

## RN-11 · Janela temporal — CONFIRMADA

`DTNEG` real vai de **2022-09-08** a **2026-07-31**, embora o arquivo se declare 01/2023–07/2026.
São 15 linhas anteriores a 2023. Elas são carregadas e sinalizadas; qualquer recorte é explícito
na interface, jamais silencioso.

O 161 Gestão Diária cobre 2020–2026 e os positivados 2021–2026: a reconciliação usa apenas a
janela comum e o relatório declara o período comparado.

---

## RN-12 · Tipos e sujeira de origem — CONFIRMADA

| Fenômeno | Onde | Tratamento no staging |
|---|---|---|
| Decimal pt-BR em coluna de texto (`'1,9389'`, `'108,58'`) | `PERCCOM`, `VLRCOM`, `VLRUNIT`, `ACORDO`, `VLRNOTA` do CT-e, 161, positivados | Parser pt-BR dedicado |
| Literal `'NULL'` como texto | `CIDORIGEM`, `UFORIGEM`, `CODTRIB`, `SERIENOTA`, `OBSERVACAONOTA`, `NOTAS_VENDA`, `PERC_ATING_VLR`, `MARKUP` | Convertido a NULL real — **nunca** a zero |
| Espaços à direita | quase todos os campos de texto | `TRIM` |
| Datas como texto | `DTFATUR` (vendas), todas as datas do CT-e | Parse ISO com hora |
| Prefixo de código no nome | `NOMECIDPARC = '5357-UBERLANDIA'`, `RAMOATIVPARC = '4 - Varejo'` | Código e descrição separados |

A camada RAW guarda tudo como texto, exatamente como veio.

---

## RN-13 · Dados pessoais e credenciais — REGRA DE SEGURANÇA

- `CGCCPF_PAR` e `CNPJ_CPF` entram no DW **apenas como SHA-256**. Nenhuma análise exige o documento
  em claro.
- O arquivo `Inventário de Dados…xlsx` contém uma coluna com **senhas em texto claro** de sistemas
  de terceiros. Essa coluna **não é lida** — nem para a camada RAW. O catálogo importa apenas fonte,
  localização e descrição. Ver `docs/decisions.md` (ADR-005).

---

## RN-14 · Anomalias preservadas — CONFIRMADA

Duas linhas de custo têm `CUSREP`, `CUSGER` e `CUSVARIAVEL` negativos. Não são corrigidas nem
removidas: aparecem na tela de Qualidade como anomalia para decisão do negócio.

---

## RN-15 · Semântica de "positivado" — CONFIRMADA

Verificado na carga: `fact_positivado` tem **2.871 vínculos e 2.871 clientes distintos** —
nenhum cliente aparece em dois meses — e a soma bate exatamente com `QTD_POSITIVADOS` da fonte.

**Conclusão:** "positivado" é o **mês da primeira compra do cliente**, não "cliente que comprou
no mês". A tabela é, na prática, o registro de coortes de entrada.

**Implicação:** a análise de coortes usa `fact_positivado` como marco de entrada e busca a
recompra em `fact_venda_item`. Não se deve interpretar `QTD_POSITIVADOS` como "clientes ativos
no mês" — são clientes **novos** no mês.
