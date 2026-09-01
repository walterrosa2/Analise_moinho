# Verificações Cruzadas (Fase 0)

> Gerado por `scripts/deep_checks.py`. Cada resposta abaixo determina
> uma decisão de modelagem registrada em `docs/business_rules.md`.

## 1. Base de vendas — carregando...

- Linhas: **204.037** | Colunas: **55**

## 1. `TIPMOV` × sinal das medidas

| TIPMOV | Linhas | VLRTOT<0 | VLRTOT>0 | TONLIQ<0 | Σ VLRTOT | Σ TONLIQ |
|---|---|---|---|---|---|---|
| `D` | 23.137 | 23.137 | 0 | 23.137 | -7.188.133.12 | -2.312.960 |
| `V` | 180.900 | 0 | 179.336 | 0 | 525.543.817.38 | 201.102.991 |

### Operações (`CODTIPOPER` / `DESCROPER`) por TIPMOV

| TIPMOV | CODTIPOPER | DESCROPER | Linhas | Σ VLRTOT |
|---|---|---|---|---|
| D | 2200 | DEV. VENDA COM ICMS - NFE TERCEIROS | 20.725 | -4.318.458.17 |
| D | 2209 | DEV. VENDA - NFE EMIS PROP (COM NF REF.) | 2.397 | -2.827.518.65 |
| D | 2252 | DEV. BONIF DOACAO BRINDE - NFE EMIS TERC | 8 | -41.515.10 |
| D | 2251 | DEV. BONIF DOACAO BRINDE - NFE EMIS PROP | 4 | -134.80 |
| D | 2207 | STATUS - DENEGADA | 3 | -506.40 |
| V | 3100 | VENDA COMERCIALIZAÇÃO - NFE | 175.122 | 520.023.893.34 |
| V | 3101 | VENDA CONSUMIDOR - NFC-E | 3.862 | 740.181.09 |
| V | 3107 | SAIDA BONIFICAÇÃO | 997 | 0.00 |
| V | 3102 | SAIDA AMOSTRA. DOACAO OU BRINDE | 567 | 0.00 |
| V | 3103 | VENDA REMETIDA P/ INDUSTRIALIZAÇÃO | 338 | 4.758.123.93 |
| V | 3401 | NF COMPLEMENTAR VALOR - VENDA | 13 | 21.177.67 |
| V | 3120 | SIMPLES FATURAMENTO VENDA ENTREGA FUTURA | 1 | 441.35 |

## 2. `CIF_FOB` — domínio inconsistente

| Valor bruto | Linhas |
|---|---|
| `C - CIF - Contratação do Frete por conta do Remetente` | 158.655 |
| `S` | 22.713 |
| `F - FOB - Contratação do Frete por conta do Destinatário` | 18.373 |
| `S - Sem Frete` | 3.871 |
| `F` | 217 |
| `C` | 201 |
| `T` | 6 |
| `R - Transp. Próprio Remetente` | 1 |

> Necessária normalização para `C` / `F` / `R` / `S` / `T` (a primeira letra é o código; o restante é descrição).

## 3. `VLRNOTA` no grão de item (por que é proibido somar)

- Notas com mais de 1 item: **41.116** de 87.274
- Notas em que `VLRNOTA` varia entre os itens: **0**
- Σ `VLRTOT` (itens. CORRETO): **R$ 518.355.684.26**
- Σ `VLRNOTA` no grão de item (ERRADO): **R$ 2.185.853.640.62**
- Σ `VLRNOTA` deduplicado por NUNOTA: **R$ 538.524.255.15**
- **Inflação se somar VLRNOTA por item: 321.7%**

### `VLRFRETE_ORDEMCARGA` no grão de item

- Σ por item (ERRADO): **R$ 564.113.037.16**
- Σ deduplicado por ORDEMCARGA: **R$ 29.874.498.13**
- **Inflação: 1.788.3%**

## 4. Vendedores: cadastro × movimento

- Cadastro (`Vendedor_Supervisor`): **458** códigos
- Com movimento na base de vendas: **34** códigos
- Movimentam mas NÃO estão no cadastro: **[0]**
- Cadastrados sem nenhuma venda: **425**

### Todos os vendedores com movimento (ordenados por receita)

| CODVEND | Apelido | TipoVend | Ativo | Linhas | Receita | % | Clientes | Toneladas |
|---|---|---|---|---|---|---|---|---|
| 4 | LUIZ C RUFINO | S - Supervisor | S | 22.541 | 170.285.719.43 | 32.85% | 97 | 66.573.9 |
| 457 | V DIRETA FARELO | R - Representante | S | 2.867 | 53.318.456.57 | 10.29% | 114 | 47.322.8 |
| 455 | LEONEL SOARES | R - Representante | S | 11.577 | 37.871.235.18 | 7.31% | 147 | 11.187.8 |
| 17 | MARCEL ZANATTA | R - Representante | S | 11.585 | 30.912.890.38 | 5.96% | 63 | 8.944.6 |
| 29 | MATHEUS (MG) | R - Representante | S | 32.218 | 24.139.112.21 | 4.66% | 266 | 7.031.6 |
| 9 | IVANI PINHEIRO | R - Representante | S | 5.125 | 22.800.184.98 | 4.40% | 62 | 5.710.0 |
| 447 | ITAMAR CARVALHO | R - Representante | S | 8.292 | 18.725.786.35 | 3.61% | 117 | 5.813.9 |
| 18 | ANT C CUNHA | R - Representante | S | 7.916 | 17.138.867.33 | 3.31% | 94 | 6.038.2 |
| 443 | MAX MAHLOW | S - Supervisor | S | 2.457 | 16.824.999.01 | 3.25% | 20 | 5.318.7 |
| 16 | CLAUDIO (GO) | R - Representante | S | 3.243 | 13.394.633.33 | 2.58% | 10 | 2.718.4 |
| 24 | SERGIO EDUARDO | R - Representante | S | 21.440 | 12.228.818.89 | 2.36% | 253 | 3.555.6 |
| 35 | CASSIANO PAULA | R - Representante | S | 11.315 | 10.359.400.85 | 2.00% | 88 | 2.864.2 |
| 441 | FERNANDO CASTIL | R - Representante | S | 2.177 | 9.545.023.58 | 1.84% | 9 | 1.457.3 |
| 404 | MARIANO BARROS | R - Representante | S | 1.301 | 9.342.222.39 | 1.80% | 32 | 2.918.8 |
| 7 | ADAO GUSMAO | R - Representante | S | 5.685 | 9.226.743.86 | 1.78% | 50 | 2.923.5 |
| 31 | MURILO MARTINS | R - Representante | S | 5.877 | 9.191.323.18 | 1.77% | 113 | 2.360.1 |
| 15 | CARLOS MALAQUIA | R - Representante | S | 3.309 | 8.681.299.51 | 1.67% | 75 | 2.317.6 |
| 8 | JOSE RODRIGUES | R - Representante | S | 8.907 | 6.973.705.28 | 1.35% | 117 | 2.042.3 |
| 49 | MARCELO EDUARDO | R - Representante | S | 10.433 | 6.915.784.31 | 1.33% | 154 | 1.919.1 |
| 33 | JULIO ULBRICHT | R - Representante | S | 2.952 | 6.775.392.87 | 1.31% | 30 | 1.996.6 |
| 5 | JERONIMO ALVES | R - Representante | S | 12.118 | 5.833.950.43 | 1.13% | 120 | 1.687.4 |
| 456 | PAULO SERGIO | R - Representante | N | 1.577 | 3.773.603.43 | 0.73% | 36 | 1.207.2 |
| 39 | JOHN KENNEDY | R - Representante | S | 1.271 | 3.714.767.43 | 0.72% | 7 | 1.164.4 |
| 472 | ADENILSON | R - Representante | S | 736 | 2.179.298.89 | 0.42% | 23 | 700.1 |
| 6 | COML CAIAPONIA | R - Representante | S | 585 | 2.124.800.50 | 0.41% | 5 | 599.0 |
| 466 | JANETE  MIRANDA | R - Representante | S | 445 | 1.805.579.34 | 0.35% | 22 | 569.2 |
| 28 | FRANCISCO PAULA | R - Representante | S | 870 | 1.608.790.94 | 0.31% | 19 | 476.1 |
| 470 | TULIO PERPETUO | R - Representante | N | 160 | 751.669.66 | 0.15% | 4 | 249.5 |
| 44 | TELEMK / BALCAO | S - Supervisor | S | 4.040 | 680.370.90 | 0.13% | 153 | 256.8 |
| 476 | SAMUEL | R - Representante | S | 38 | 614.096.50 | 0.12% | 4 | 300.6 |
| 467 | TITAN REPRESENT | R - Representante | S | 212 | 384.734.11 | 0.07% | 4 | 122.6 |
| 382 | VDA SUBPRODUTO | R - Representante | S | 243 | 177.413.56 | 0.03% | 6 | 417.3 |
| 0 | — | — | — | 522 | 54.270.27 | 0.01% | 13 | 24.7 |
| 446 | MURILO PRUDENTE | S - Supervisor | S | 3 | 738.80 | 0.00% | 2 | 0.2 |

### `CODSUPERVISOR`

| CODSUPERVISOR | Linhas | Receita |
|---|---|---|
| 4 | 156.250 | 356.463.165.84 |
| 443 | 32.321 | 164.079.634.08 |
| 999 | 272 | 179.997.37 |
| NULO | 15.194 | -2.367.113.03 |

## 5. Custos PA — cobertura dos produtos vendidos

- Produtos distintos vendidos: **100**
- Produtos distintos na tabela de custo: **101**
- Vendidos SEM nenhum custo cadastrado: **0** → []

### Datas de custo (`DTATUAL`)

- Tipo lido: `Datetime(time_unit='ms', time_zone=None)`
- Amostra: [datetime.datetime(2023, 1, 2, 0, 0), datetime.datetime(2023, 1, 5, 0, 0), datetime.datetime(2023, 1, 11, 0, 0)]
- Datas distintas: **1.085**
- CODEMP na tabela de custo: [1.0, 2.0, 4.0, 6.0]
- CODLOCAL na tabela de custo: [0.0, 106001.0, 106002.0, 106003.0, 106004.0, 106006.0, 106007.0, 107001.0]
- CODLOCALORIG nas vendas: ['106001', '106002', '106003', '106004', '106006', '106007', '107001']

## 6. CT-e × NF-e (bridge)

- Linhas de CT-e: **32.789**
- Sem `CHAVES_NFE_VENDA`: **4.203** (12.82%)
- Sem `ORDEMCARGA` válida (nulo ou 0): **18.325** (55.89%)
- Vínculos CT-e→NF-e após explosão por `;`: **41.037**
- Chaves NF-e distintas citadas nos CT-e: **40.645**
- Dessas. encontradas na base de vendas: **38.801** (95.46%)
- Não encontradas: **1.844**
- Amostra não encontrada: ['31210301064584000121550000001948511559606065', '31230101064584000121550000002341161896900678', '31230101064584000121550000002341171480258602']

### Operações de CT-e

| CODTIPOPER | DESCROPER | Linhas |
|---|---|---|
| 2107 | AQUISIÇÃO FRETE VENDAS - CTE | 31.646 |
| 2162 | SERVIÇO FRETE NF PRESTACAO DE SERVICO | 1.135 |
| 3111 | ENTRADA CTE ANULADO | 4 |
| 4103 | LANCTO FRETE S/ COMPRA INSUMOS/REMESSAS | 4 |

## 7. Positivados — explosão de `PARC_POSITIVADOS`

- Meses: **67**
- Meses em que a explosão diverge de `QTD_POSITIVADOS`: **0**

### Meses de implantação do ERP (fora do padrão)

| ANO | MES | QTD_POSITIVADOS |
|---|---|---|
| 2021 | 2 | 729 |
| 2021 | 3 | 274 |
| 2021 | 4 | 103 |
| 2021 | 5 | 68 |
| 2021 | 6 | 48 |
| 2021 | 7 | 43 |
| 2021 | 8 | 43 |
| 2021 | 9 | 39 |

- Clientes distintos positivados: **2.871**
- Presentes na base de vendas 2023+: **2.233** (77.8%)
> Positivados cobrem 2021+; a base de vendas começa em 2023. A diferença é esperada, não é erro.

## 8. Região comercial por representante (arquivo extra, fora da especificação)

- Aba `REPRESENTANTE`: 394 linhas, **23** códigos de representante
- Códigos: [4, 5, 7, 8, 9, 15, 16, 18, 28, 29, 31, 33, 35, 39, 404, 441, 443, 447, 455, 466, 472, 476, 479]
- Desses, com movimento nas vendas: **22** → [4, 5, 7, 8, 9, 15, 16, 18, 28, 29, 31, 33, 35, 39, 404, 441, 443, 447, 455, 466, 472, 476]
- No arquivo mas sem venda: [479]
- Vendem mas não estão nesse arquivo: [0, 6, 17, 24, 44, 49, 382, 446, 456, 457, 467, 470]

- Aba `GERAL`: 218 linhas — mapa CIDADE → REGIÃO COMERCIAL → REPRESENTANTE
- Regiões comerciais nomeadas (35): ['Alto Paranaiba', 'Alto Teles Pires', 'Campinas e Regiao (RMC)', 'Canarana', 'Central / Metalurgica', 'Cuiaba', 'Entorno do DF', 'Grande Goiania', 'Irece', 'Ji-Parana', 'Macae', 'Nordeste Paulista (Ribeirao Preto/Franca)', 'Noroeste / Paracatu', 'Noroeste Paulista (Sao Jose do Rio Preto)', 'Norte Araguaia', 'Oeste / Aragarcas', 'Oeste Paulista (Presidente Prudente)', 'Plano Piloto', 'Porto Velho', 'Primavera do Leste', 'RMBH', 'Rondonopolis', 'Sinop', 'Sorocaba e Regiao', 'Sul Goiano', 'Sul de Minas', 'Tangara da Serra', 'Triangulo Goiano / Sudoeste', 'Triangulo Mineiro', 'Vale do Aco / Rio Doce', 'Vale do Jequitinhonha / Norte', 'Vale do Mucuri', 'Vale do Ribeira', 'Vilhena', 'Zona da Mata']

## 9. Cobertura temporal real

- `DTNEG` vendas: **2022-09-08 00:00:00** a **2026-07-31 00:00:00**
> A especificação declara 01/2023–07/2026; há registros anteriores a 2023 (a filtragem deve ser explícita, nunca silenciosa).
- Linhas com `DTNEG` < 2023-01-01: **15**