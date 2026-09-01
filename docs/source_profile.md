# Perfil Real das Fontes (`docs/source_profile.md`)

> Gerado automaticamente por `scripts/profile_sources.py`.
> **Evidência > suposição**: este documento reflete a leitura real dos arquivos,
> não o que a especificação técnica presume.

- Gerado em: `2026-09-01T20:02:27.543204+00:00`
- Diretório: `E:\Backup_HD_Walter\Moinho\Dados\Visao_moinho\data\input`
- Arquivos analisados: **8**

---

## Sumário

| Arquivo | Abas | Total linhas |
|---|---|---|
| `161 - Gestão Diária Comercial (OUTROS) V1.xlsx` | 1 | 396 |
| `161 - Gestão Diária Comercial V1.xlsx` | 1 | 1.545 |
| `CTE Venda 012023 - 072026 V1.xlsx` | 3 | 32.789 |
| `Inventário de Dados relatórios Sankhya e outros - Sanathielle.xlsx` | 2 | 42 |
| `POSITIVADOS V1.xlsx` | 2 | 525 |
| `REGIÃO COMERCIAL POR REPRESENTANTE -SANATHIELLE.xlsx` | 2 | 612 |
| `Relatorio Compra de Trigo - Max.xlsx` | 2 | 57 |
| `VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx` | 3 | 233.630 |

---

## Arquivo: `161 - Gestão Diária Comercial (OUTROS) V1.xlsx`

- Tamanho: 0.02 MB
- SHA-256: `17e19354cc72b2dca630cfa598358520e08d1b66459c261002cfa96d2e26eb8e`
- Abas encontradas: 'Planilha1'

### Aba: `Planilha1`

**396 linhas x 6 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `ANO + MES + DESCRICAO` | 396 | 396 | SIM | 0 |
| `ANO + MES` | 396 | 66 | **NAO** | 330 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `ANO` | Float64 | 0.0% | 6 | `2021.0`, `2022.0`, `2023.0`, `2024.0`, `2025.0`, `2026.0` | 2.021.00 | 2.026.00 |
| 2 | `MES` | Float64 | 0.0% | 12 | `1.0`, `2.0`, `3.0`, `4.0`, `5.0`, `6.0`, `7.0`, `8.0`, `9.0`, `10.0`, `11.0`, `12.0` | 1.00 | 12.00 |
| 3 | `DESCRICAO` | String | 0.0% | 6 | `Frete CIF`, `Frete FOB`, `Vr Acordos`, `Vr Comissão`, `Vr ICMS`, `Vr Sub.Tributária` |  |  |
| 4 | `ORC/ANT` | String | 0.0% | 396 | `3787896.42`, `6017485.99`, `9709058.25` |  |  |
| 5 | `ATUAL` | String | 0.0% | 350 | `294.40`, `312665.49`, `110251.43` |  |  |
| 6 | `%VAR` | String | 0.0% | 257 | `0.01`, `5.20`, `1.14` |  |  |

---

## Arquivo: `161 - Gestão Diária Comercial V1.xlsx`

- Tamanho: 0.10 MB
- SHA-256: `b1f1af6b7c056cdc459630f6b53a19bc7b40954f08c073e127e9d55746994b2d`
- Abas encontradas: 'Planilha1'

### Aba: `Planilha1`

**1.545 linhas x 11 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `ANO + MES + TIPO + COD_CLA` | 1.545 | 1.545 | SIM | 0 |
| `ANO + MES` | 1.545 | 68 | **NAO** | 1.477 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `ANO` | Float64 | 0.0% | 7 | `2020.0`, `2021.0`, `2022.0`, `2023.0`, `2024.0`, `2025.0`, `2026.0` | 2.020.00 | 2.026.00 |
| 2 | `MES` | Float64 | 0.0% | 12 | `1.0`, `2.0`, `3.0`, `4.0`, `5.0`, `6.0`, `7.0`, `8.0`, `9.0`, `10.0`, `11.0`, `12.0` | 1.00 | 12.00 |
| 3 | `TIPO` | String | 0.0% | 6 | `CARTEIRA`, `DEVOLUÇÃO`, `ORÇADO`, `REAL.-DEVOLUÇÃO`, `REALIZADO`, `VENDAS` |  |  |
| 4 | `COD_CLA` | Float64 | 0.0% | 4 | `13.0`, `14.0`, `15.0`, `50.0` | 13.00 | 50.00 |
| 5 | `DESC_CLA` | String | 0.0% | 4 | `BOLO`, `FARELO`, `FARINHAS`, `MISTURAS` |  |  |
| 6 | `VALOR` | String | 0.0% | 1.465 | `44981.00`, `977441.53`, `24610.80` |  |  |
| 7 | `PERC_ATING_VLR` | String | 0.0% | 253 | `NULL`, `NULL`, `NULL` |  |  |
| 8 | `TONELADA` | String | 0.0% | 1.411 | `20.00`, `445.11`, `17.57` |  |  |
| 9 | `PERC_ATING_TON` | String | 0.0% | 253 | `NULL`, `NULL`, `NULL` |  |  |
| 10 | `MARKUP` | String | 0.0% | 220 | `NULL`, `NULL`, `NULL` |  |  |
| 11 | `PC_MEDIO` | String | 0.0% | 1.456 | `2249.05`, `2195.98`, `1400.73` |  |  |

---

## Arquivo: `CTE Venda 012023 - 072026 V1.xlsx`

- Tamanho: 2.98 MB
- SHA-256: `9f12f012ff3c94cc8636700e06848cde6f8cbc23eb38be2531306ba40ae8ff69`
- Abas encontradas: 'CTE Venda 012023 - 072026', 'Plan2', 'Plan3'

### Aba: `CTE Venda 012023 - 072026`

**32.789 linhas x 16 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `NUNOTA` | 32.789 | 32.785 | **NAO** | 4 |
| `CHAVECTE` | 32.789 | 31.656 | **NAO** | 1.133 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CODEMP` | String | 0.0% | 4 | `1`, `2`, `4`, `6` |  |  |
| 2 | `NUNOTA` | String | 0.0% | 32.785 | `309717`, `309718`, `309719` |  |  |
| 3 | `NUMNOTA` | String | 0.0% | 32.155 | `1307771`, `83360`, `83361` |  |  |
| 4 | `SERIENOTA` | String | 0.0% | 8 | `0  `, `1  `, `15 `, `2  `, `3  `, `9  `, `900`, `NULL` |  |  |
| 5 | `DTNEG` | String | 0.0% | 929 | `2023-01-02 00:00:00.000`, `2023-01-03 00:00:00.000`, `2023-01-03 00:00:00.000` |  |  |
| 6 | `DTENTSAI` | String | 0.0% | 758 | `2023-01-05 00:00:00.000`, `2023-01-05 00:00:00.000`, `2023-01-05 00:00:00.000` |  |  |
| 7 | `DTFATUR` | String | 0.0% | 1.125 | `2023-01-02 00:00:00.000`, `2023-01-03 00:00:00.000`, `2023-01-03 00:00:00.000` |  |  |
| 8 | `CODTIPOPER` | String | 0.0% | 4 | `2107`, `2162`, `3111`, `4103` |  |  |
| 9 | `DESCROPER` | String | 0.0% | 4 | `AQUISIÇÃO FRETE VENDAS - CTE            `, `ENTRADA CTE ANULADO                     `, `LANCTO FRETE S/ COMPRA INSUMOS/REMESSAS `, `SERVIÇO FRETE NF PRESTACAO DE SERVICO   ` |  |  |
| 10 | `CHAVECTE` | String | 0.0% | 31.656 | `31230104423462000172570020013077711013077715`, `31230101767692000160570010000833601001902183`, `31230101767692000160570010000833611000110892` |  |  |
| 11 | `ORDEMCARGA` | String | 0.0% | 3.494 | `0`, `0`, `0` |  |  |
| 12 | `CODPARC` | String | 0.0% | 46 | `52635`, `24303`, `24303` |  |  |
| 13 | `NOMEPARC` | String | 0.0% | 40 | `POLI LOGISTICA LTDA                     `, `TRANSCONTINENTAL LOGIST TRANSP EIRELI   `, `TRANSCONTINENTAL LOGIST TRANSP EIRELI   ` |  |  |
| 14 | `VLRNOTA` | String | 0.0% | 17.832 | `5600`, `173,54`, `157,24` |  |  |
| 15 | `NOTAS_VENDA` | String | 0.0% | 28.365 | `NULL`, ` 000233885`, ` 000233884` |  |  |
| 16 | `CHAVES_NFE_VENDA` | String | 0.0% | 28.365 | `NULL`, ` 31230101064584000121550000002338851492523288`, ` 31230101064584000121550000002338841252055215` |  |  |

### Aba: `Plan2`

**0 linhas x 0 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|

### Aba: `Plan3`

**0 linhas x 0 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|

---

## Arquivo: `Inventário de Dados relatórios Sankhya e outros - Sanathielle.xlsx`

- Tamanho: 0.02 MB
- SHA-256: `27c3078f8e3fefd880bf77bf965e271bef392a8d30f69c9cf8143a3b91585d22`
- Abas encontradas: 'Sankhya', 'Outras fontes'

### Aba: `Sankhya`

**36 linhas x 3 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `FONTE` | String | 0.0% | 1 | `SANKHYA` |  |  |
| 2 | `LOCALIZAÇÃO` | String | 0.0% | 35 | `130 - COMISSÕES LIBERADAS ANALÍTICO `, `131 - COMISSÕES LIBERADAS SINTÉTICO`, `75 - ACORDO COMERCIAL BAC/BAD` |  |  |
| 3 | `DADOS` | String | 0.0% | 34 | `Arquivo em PDF , detalhando as vendas e % de comissão por RCA`, `Arquivo resumido , vendedor , valor de comissão , cobrança de imposto e líquido. Possível pesquisar por período `, `BAC - Desconto contratual (ex : compra |  |  |

### Aba: `Outras fontes`

**6 linhas x 4 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `FONTE` | String | 0.0% | 6 | `Bluesoft Cosmos`, `CONAB`, `Histórico de cotações do Dolar `, `Infoprice`, `Pograma Feedback`, `SAFRAS & MERCADO ` |  |  |
| 2 | `LOCALIZAÇÃO` | String | 0.0% | 6 | `https://app.infoprice.co/login`, `https://cosmos.bluesoft.com.br/`, `https://plataforma.safras.com.br/pages/login`, `https://programafeedback.primebuilder.com.br/#/auth`, `https://www.bcb.gov.br/estabilidadefinanceira/h |  |  |
| 3 | `Login e Senha` | String | 16.67% | 5 | `Login: trigo@moinhoseteirmaos.com.br senha: lunar1234`, `Login:2447/moinhoseteirmaos Senha:3354`, `Login:mercado@moinhoseteirmaos.com.br Senha:Lunar1234`, `Não se Aplica` |  |  |
| 4 | `DADOS` | String | 0.0% | 6 | `Análises diárias do mercado do trigo `, `Base de dados de monitoramento de preços de mercado e concorrentes.`, `Boletins da safra de grãos realizados mensalmente no dia 14/06`, `Consultar Produtos por Código de Barras ( |  |  |

---

## Arquivo: `POSITIVADOS V1.xlsx`

- Tamanho: 0.07 MB
- SHA-256: `e367ec1f0def45abb617dcb0002a84346808853e43b9b88c7a247bd6e45dc764`
- Abas encontradas: 'parceiros positivados ', 'parceiro x localidade '

### Aba: `parceiros positivados `

**67 linhas x 7 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `ANO + MES` | 67 | 67 | SIM | 0 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `ANO` | Float64 | 0.0% | 6 | `2021.0`, `2022.0`, `2023.0`, `2024.0`, `2025.0`, `2026.0` | 2.021.00 | 2.026.00 |
| 2 | `MES` | Float64 | 0.0% | 12 | `1.0`, `2.0`, `3.0`, `4.0`, `5.0`, `6.0`, `7.0`, `8.0`, `9.0`, `10.0`, `11.0`, `12.0` | 1.00 | 12.00 |
| 3 | `QTD_POSITIVADOS` | Float64 | 0.0% | 36 | `729.0`, `274.0`, `103.0` | 11.00 | 729.00 |
| 4 | `VLRTOT_POSITIVADOS` | String | 0.0% | 67 | `3720801.96`, `1410521.44`, `536032.96` |  |  |
| 5 | `VLRTOT_GERAL` | String | 0.0% | 67 | `9695750.40`, `11459198.43`, `10839299.43` |  |  |
| 6 | `PERC_PROSITIVADOS_X_GERAL_MES` | String | 0.0% | 62 | `38.38`, `12.31`, `4.95` |  |  |
| 7 | `PARC_POSITIVADOS` | String | 0.0% | 67 | `2654, 2941, 3305, 3324, 3758, 10259, 12484, 12533, 12565, 15490, 15875, 16960, 17145, 7751, 20085, 25165, 25667, 26052, 26556, 28277, 28692, 29360, 30366, 33357, 33757, 34376, 39254, 39490, 39675, 40641, 40794, 40809, 4 |  |  |

### Aba: `parceiro x localidade `

**458 linhas x 17 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `CODVEND` | 458 | 458 | SIM | 0 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CODVEND` | Float64 | 0.0% | 458 | `3.0`, `4.0`, `5.0` | 3.00 | 482.00 |
| 2 | `APELIDO_VENDEDOR` | String | 0.0% | 417 | `EDUARDO SOUS`, `LUIZ C RUFINO`, `JERONIMO ALVES` |  |  |
| 3 | `TipoVend` | String | 0.0% | 3 | `R - Representante`, `S - Supervisor`, `V - Vendedor` |  |  |
| 4 | `VENDEDOR_ATIVO` | String | 0.0% | 2 | `N`, `S` |  |  |
| 5 | `CODPARC` | Float64 | 0.0% | 448 | `33722.0`, `45325.0`, `20879.0` | 0.00 | 71.822.00 |
| 6 | `NOMEPARC` | String | 0.0% | 432 | `33722-EDUARDO SOUZA`, `45325-LUIZ CARLOS RUFINO`, `ALVES RIBEIRO REP LTDA UDIA MATRIZ` |  |  |
| 7 | `RAZAO_SOCIAL` | String | 2.4% | 432 | `33722-EDUARDO SOUZA`, `45325-LUIZ CARLOS RUFINO`, `ALVES RIBEIRO REP LTDA UDIA MATRIZ` |  |  |
| 8 | `CNPJ_CPF` | Float64 | 3.06% | 420 | `23892420149.0`, `43662528649.0`, `1507528000114.0` | 1.271.300.00 | 89.823.918.000.578.00 |
| 9 | `EMAIL` | String | 70.52% | 95 | `adaogusmaorepres@hotmail.com`, `jose.rodrigues@yahoo.com`, `jcpinheirinho@terra.com.br` |  |  |
| 10 | `TELEFONE` | String | 0.0% | 316 | `(34)349913781`, `(34)39764699`, `(34)39770604` |  |  |
| 11 | `CEP` | Float64 | 2.62% | 334 | `38400000.0`, `38408106.0`, `38401664.0` | 0.00 | 91.010.001.00 |
| 12 | `NUMERO` | String | 0.0% | 275 | `350`, `191`, `245` |  |  |
| 13 | `COMPLEMENTO` | String | 55.02% | 140 | `GO / MT/ AC ...`, `PROGRESSO`, `QD R 06 LOTE 03 142` |  |  |
| 14 | `CIDADE` | String | 0.0% | 118 | `UBERLANDIA`, `UBERLANDIA`, `UBERLANDIA` |  |  |
| 15 | `ESTADO` | String | 0.0% | 18 | `0`, `AC`, `AL`, `BA`, `DF`, `ES`, `GO`, `MA`, `MG`, `MS`, `MT`, `PE`, `PR`, `RJ`, `RS`, `SC`, `SP`, `TO` |  |  |
| 16 | `CODREGIAO` | Float64 | 0.0% | 87 | `3010502.0`, `3010502.0`, `3010502.0` | 0.00 | 5.040.101.00 |
| 17 | `REGIAO` | String | 0.0% | 87 | `UBERLANDIA`, `UBERLANDIA`, `UBERLANDIA` |  |  |

---

## Arquivo: `REGIÃO COMERCIAL POR REPRESENTANTE -SANATHIELLE.xlsx`

- Tamanho: 0.04 MB
- SHA-256: `c21f348c93ef81a7682fd144acad58aed4f4fa18f30df5a49665129f0416b299`
- Abas encontradas: 'GERAL', 'REPRESENTANTE'

### Aba: `GERAL`

**218 linhas x 5 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CIDADE` | String | 0.0% | 205 | `UBERLANDIA`, `ITUMBIARA`, `UBERABA` |  |  |
| 2 | `REGIÃO COMERCIAL` | String | 23.85% | 36 | `Triangulo Mineiro`, `Sul Goiano`, `Triangulo Mineiro` |  |  |
| 3 | `REPRESENTANTE` | String | 0.46% | 27 | `JERONIMO ALVES`, `MURILO MARTINS`, `ANT C CUNHA` |  |  |
| 4 | `__UNNAMED__3` | String | 82.11% | 8 | `*Exclusivo as lojas Atacadão, Assai, Atacadão dia a dia`, `Aditivo`, `Aditivo CR PROMOÇÃO`, `Contrato`, `Não está no contrato`, `Não tem no contrato`, `retirado do contrato através de aditivo em 11/06/2019` |  |  |
| 5 | `__UNNAMED__4` | String | 96.79% | 8 | `CAMPINAS`, `Distrito Federal / Goiás (Partes): BRASÍLIA (partes), GOIÂNIA (partes)`, `LITORAL SP`, `Mato Grosso: APIACAS, ARAPUTANGA, BARRA DO BUGRES, CACERES, COLIDER, CUIABÁ, DIAMANTINO, GUARANTA DO NORTE, JACIARA, JA |  |  |

### Aba: `REPRESENTANTE`

**394 linhas x 6 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CIDADE` | String | 26.65% | 265 | `Bocaiúva`, `Campo Azul, Minas Gerais`, `Capitão Enéas` |  |  |
| 2 | `ESTADO` | String | 26.9% | 12 | `Califórnia, EUA`, `Distrito Federal`, `Goiás`, `Mato Grosso`, `Minas Gerais`, `Nordeste`, `Rio de Janeiro`, `Rondônia`, `San José, Costa Rica`, `São Paulo`, `Tocantins` |  |  |
| 3 | `CÓDIGO-REPRESENTANTE` | Float64 | 26.65% | 24 | `4.0`, `5.0`, `7.0`, `8.0`, `9.0`, `15.0`, `16.0`, `18.0`, `28.0`, `29.0`, `31.0`, `33.0`, `35.0`, `39.0`, `404.0`, `441.0`, `443.0`, `447.0`, `455.0`, `466.0`, `472.0`, `476.0`, `479.0` | 4.00 | 479.00 |
| 4 | `REPRESENTANTE` | String | 26.65% | 25 | `ADAO GUSMAO`, `ADENILSON`, `ANT C CUNHA`, `CARLOS MALAQUIA`, `CASSIANO PAULA`, `CLAUDIO (GO)`, `FERNANDO CASTIL`, `FRANCISCO FRAMA`, `FRANCISCO PAULA`, `ITAMAR CARVALHO`, `IVANI PINHEIRO`, `JANETE  MIRANDA`, `JERONIMO A |  |  |
| 5 | `Observação ` | String | 50.51% | 5 | `1 cliente específico`, `O Fernando cuida de 1 cliente exclusivo: Diniz e parte de alguns distribuidores em São Paulo. Cidades citadas já tiveram movimentação de venda para esse vendedor antes mas sem atuação hoje em dia |  |  |
| 6 | `Observações patricia` | String | 92.13% | 8 | `*Exclusivo as lojas Atacadão, Assai, Atacadão dia a dia`, `Aditivo`, `Aditivo CR PROMOÇÃO`, `Contrato`, `Não está no contrato`, `Não tem no contrato`, `retirado do contrato através de aditivo em 11/06/2019` |  |  |

---

## Arquivo: `Relatorio Compra de Trigo - Max.xlsx`

- Tamanho: 0.02 MB
- SHA-256: `4884a4c12e099de0e8f01298f825dbd4570a2744d37cf955c16353ad658b1bd8`
- Abas encontradas: 'Compra', 'Estoque'

### Aba: `Compra`

**35 linhas x 9 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `Compra de Trigo _ Jan/24 até Julho/26 ` | String | 8.57% | 33 | `Mês/Ano`, `2024-01-01 00:00:00`, `2024-02-01 00:00:00` |  |  |
| 2 | `__UNNAMED__1` | String | 5.71% | 34 | `Ton Comprada `, `Trigo`, `5733.29611` |  |  |
| 3 | `__UNNAMED__2` | String | 80.0% | 8 | `120.9401`, `196.34`, `218.94`, `254`, `54.78`, `80.71`, `Triticale` |  |  |
| 4 | `__UNNAMED__3` | String | 8.57% | 33 | `Soma`, `5733.29611`, `6443.82316` |  |  |
| 5 | `__UNNAMED__4` | Null | 100.0% | 1 |  |  |  |
| 6 | `__UNNAMED__5` | String | 5.71% | 34 | `Vlr Comprado - R$`, `Trigo`, `7894677.226` |  |  |
| 7 | `__UNNAMED__6` | String | 80.0% | 8 | `117916.5975`, `245110`, `245375.2142292`, `267022.41`, `71214.01`, `96165.965`, `Triticale` |  |  |
| 8 | `__UNNAMED__7` | String | 8.57% | 33 | `Soma`, `7894677.226`, `8878416.580304362` |  |  |
| 9 | `__UNNAMED__8` | String | 8.57% | 33 | `PREÇO MÉDIO`, `1376.987525942`, `1377.818161649` |  |  |

### Aba: `Estoque`

**22 linhas x 3 colunas**

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `Estoque de Trigo _ Jan/25 até Julho/26 ` | String | 9.09% | 21 | `2025-01-01 00:00:00`, `2025-02-01 00:00:00`, `2025-03-01 00:00:00`, `2025-04-01 00:00:00`, `2025-05-01 00:00:00`, `2025-06-01 00:00:00`, `2025-07-01 00:00:00`, `2025-08-01 00:00:00`, `2025-09-01 00:00:00`, `2025-10-01 0 |  |  |
| 2 | `__UNNAMED__1` | String | 9.09% | 21 | `10415`, `10440`, `11179`, `11457`, `12395`, `12485`, `12964`, `13092`, `13193`, `13493`, `13787`, `14579`, `14835`, `17506`, `17689`, `6186`, `7204`, `8261`, `9389`, `Ton ` |  |  |
| 3 | `__UNNAMED__2` | String | 9.09% | 21 | `1414.55`, `1419.89`, `1421.59`, `1434.08`, `1437.9`, `1448.27`, `1458.48`, `1487.86`, `1490.19`, `1502.73`, `1516.03`, `1531.67`, `1555.66`, `1564.41`, `1574.5`, `1582.77`, `1600.92`, `1616.4`, `1622.65`, `PREÇO MEDIO` |  |  |

---

## Arquivo: `VENDAS-DEV-RCA-CUSTOS 012023-072026 V1.xlsx`

- Tamanho: 72.30 MB
- SHA-256: `9ea2fda7d5a3ecfe3f7d33410642d4bb438e5e07212dc1d1f39fec3ec7ac9eae`
- Abas encontradas: 'Dados Vend_Dev 012023-072026', 'Vendedor_Supervisor', 'Custos PA 012023 - 072026'

### Aba: `Dados Vend_Dev 012023-072026`

**204.037 linhas x 55 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `NUNOTA + SEQUENCIA` | 204.037 | 204.037 | SIM | 0 |
| `NUNOTA` | 204.037 | 87.274 | **NAO** | 116.763 |
| `CODVEND` | 204.037 | 34 | **NAO** | 204.003 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CODEMP` | String | 0.0% | 4 | `1`, `2`, `4`, `6` |  |  |
| 2 | `NUNOTA` | Float64 | 0.0% | 87.274 | `308513.0`, `308514.0`, `308533.0` | 308.513.00 | 829.017.00 |
| 3 | `NUMNOTA` | Float64 | 0.0% | 86.511 | `233834.0`, `233835.0`, `233836.0` | 0.00 | 52.329.759.00 |
| 4 | `CHAVENFE` | String | 0.0% | 87.271 | `31230101064584000121550000002338341051256653`, `31230101064584000121550000002338351637304423`, `31230101064584000121550000002338361667316036` |  |  |
| 5 | `DTNEG` | Datetime(time_unit='ms', time_zone=None) | 0.0% | 1.018 | `2023-01-02 00:00:00`, `2023-01-02 00:00:00`, `2023-01-02 00:00:00` | 2022-09-08 00:00:00 | 2026-07-31 00:00:00 |
| 6 | `DTFATUR` | String | 0.0% | 82.736 | `2023-01-02 07:52:27.000`, `2023-01-02 07:52:32.000`, `2023-01-02 08:49:27.000` |  |  |
| 7 | `DTENTSAI` | Datetime(time_unit='ms', time_zone=None) | 0.0% | 933 | `2023-01-02 00:00:00`, `2023-01-02 00:00:00`, `2023-01-02 00:00:00` | 2023-01-02 00:00:00 | 2026-07-31 00:00:00 |
| 8 | `CODTIPOPER` | Float64 | 0.0% | 12 | `2200.0`, `2207.0`, `2209.0`, `2251.0`, `2252.0`, `3100.0`, `3101.0`, `3102.0`, `3103.0`, `3107.0`, `3120.0`, `3401.0` | 2.200.00 | 3.401.00 |
| 9 | `DESCROPER` | String | 0.0% | 12 | `DEV. BONIF DOACAO BRINDE - NFE EMIS PROP`, `DEV. BONIF DOACAO BRINDE - NFE EMIS TERC`, `DEV. VENDA - NFE EMIS PROP (COM NF REF.)`, `DEV. VENDA COM ICMS - NFE TERCEIROS     `, `NF COMPLEMENTAR VALOR - VENDA           `,  |  |  |
| 10 | `TIPMOV` | String | 0.0% | 2 | `D`, `V` |  |  |
| 11 | `CIF_FOB` | String | 0.0% | 8 | `C`, `C - CIF - Contratação do Frete por conta do Remetente`, `F`, `F - FOB - Contratação do Frete por conta do Destinatário`, `R - Transp. Próprio Remetente`, `S`, `S - Sem Frete`, `T` |  |  |
| 12 | `VLRNOTA` | Float64 | 0.0% | 36.645 | `1520.12`, `2171.6`, `4433.07` | 0.32 | 206.200.00 |
| 13 | `ACORDO` | String | 0.0% | 8.609 | `0,00`, `0,00`, `0,00` |  |  |
| 14 | `OBSERVACAONOTA` | String | 0.0% | 20.668 | `NULL`, `NULL`, `NULL` |  |  |
| 15 | `CIDORIGEM` | String | 0.0% | 5 | `BRASILIA`, `ITUMBIARA           `, `NULL`, `RIBEIRAO PRETO      `, `UBERLANDIA` |  |  |
| 16 | `CIDDESTINO` | String | 0.0% | 231 | `UBERLANDIA`, `UBERLANDIA`, `UBERLANDIA` |  |  |
| 17 | `UFORIGEM` | String | 0.0% | 5 | `DF`, `GO`, `MG`, `NULL`, `SP` |  |  |
| 18 | `UFDESTINO` | String | 0.0% | 14 | `AC`, `DF`, `GO`, `MG`, `MT`, `NULL`, `PE`, `PR`, `RJ`, `RO`, `RS`, `SC`, `SP`, `TO` |  |  |
| 19 | `VLRFRETE_RATEADO_NOTA` | Float64 | 0.0% | 120.077 | `63.82`, `91.18`, `66.7650183732718` | 0.00 | 25.298.02 |
| 20 | `SEQUENCIA` | Float64 | 0.0% | 58 | `1.0`, `1.0`, `1.0` | 1.00 | 63.00 |
| 21 | `CODPROD` | Float64 | 0.0% | 100 | `20059.0`, `20059.0`, `20048.0` | 20.007.00 | 20.500.00 |
| 22 | `DESCRPROD` | String | 0.0% | 98 | `FAR.LUNAR PREMIUM 25KG TP1              `, `FAR.LUNAR PREMIUM 25KG TP1              `, `P.M.LUNAR MIX PREM 25KG TP1             ` |  |  |
| 23 | `CONTROLE` | String | 0.0% | 11.910 | `80146/21   `, `80146/21   `, `82646/15   ` |  |  |
| 24 | `CODCFO` | String | 0.0% | 20 | `1201`, `1202`, `1410`, `1949`, `2201`, `2202`, `2410`, `2949`, `5101`, `5102`, `5122`, `5401`, `5405`, `5910`, `5922`, `6101`, `6102`, `6108`, `6401`, `6910` |  |  |
| 25 | `CODLOCALORIG` | String | 0.0% | 7 | `106001`, `106002`, `106003`, `106004`, `106006`, `106007`, `107001` |  |  |
| 26 | `CODTRIB` | String | 0.0% | 10 | `0`, `10`, `20`, `40`, `41`, `51`, `60`, `70`, `90`, `NULL` |  |  |
| 27 | `PERCCOM` | String | 0.0% | 1.399 | `2`, `2`, `1,9389` |  |  |
| 28 | `VLRCOM` | String | 0.0% | 34.188 | `30,4024`, `43,432`, `43,848` |  |  |
| 29 | `CODVOL` | String | 0.0% | 5 | `CX`, `FD`, `KG`, `PT`, `SC` |  |  |
| 30 | `QTD` | Float64 | 0.0% | 3.245 | `14.0`, `20.0`, `20.0` | -26.540.00 | 44.720.00 |
| 31 | `VLRUNIT` | String | 0.0% | 4.098 | `108,58`, `108,58`, `109,62` |  |  |
| 32 | `PESOLIQ` | Float64 | 0.0% | 3.931 | `350.0`, `500.0`, `500.0` | -32.500.00 | 44.720.00 |
| 33 | `TONLIQ` | Float64 | 0.0% | 3.931 | `0.35`, `0.5`, `0.5` | -32.50 | 44.72 |
| 34 | `PESOBRUTO` | Float64 | 0.0% | 5.426 | `350.84`, `501.2`, `501.2` | -32.578.00 | 44.720.00 |
| 35 | `TONBRUTO` | Float64 | 0.0% | 5.426 | `0.35084`, `0.5012`, `0.5012` | -32.58 | 44.72 |
| 36 | `VLRTOT` | Float64 | 0.0% | 33.033 | `1520.12`, `2171.6`, `2192.4` | -95.760.00 | 106.402.80 |
| 37 | `VLRDESC` | Float64 | 0.0% | 58 | `0.0`, `0.0`, `0.0` | -178.20 | 7.302.10 |
| 38 | `VLRREPRED` | Float64 | 0.0% | 84 | `0.0`, `0.0`, `0.0` | -1.194.13 | 2.794.50 |
| 39 | `VLRICMS` | Float64 | 0.0% | 26.808 | `106.41`, `152.02`, `153.47` | -6.703.39 | 10.569.24 |
| 40 | `VLRSUBST` | Float64 | 0.0% | 6.669 | `0.0`, `0.0`, `69.07` | -4.053.39 | 8.929.33 |
| 41 | `ORDEMCARGA` | Float64 | 0.0% | 22.564 | `13883.0`, `13883.0`, `13884.0` | 0.00 | 38.054.00 |
| 42 | `CIF_FOB_ORDEMCARGA` | String | 0.0% | 3 | `C - CIF`, `F - FOB`, `NULL` |  |  |
| 43 | `CODPARCTRANSP` | Float64 | 0.0% | 471 | `24303.0`, `24303.0`, `24303.0` | 0.00 | 71.820.00 |
| 44 | `CODREG` | Float64 | 0.0% | 98 | `3010502.0`, `3010502.0`, `3010502.0` | 0.00 | 5.040.101.00 |
| 45 | `NOMEREG` | String | 0.0% | 92 | `UBERLANDIA          `, `UBERLANDIA          `, `UBERLANDIA          ` |  |  |
| 46 | `VLRFRETE_ORDEMCARGA` | Float64 | 22.49% | 2.108 | `155.0`, `155.0`, `135.0` | 0.00 | 44.500.00 |
| 47 | `CODVEND` | Float64 | 0.0% | 34 | `49.0`, `49.0`, `24.0` | 0.00 | 476.00 |
| 48 | `CODSUPERVISOR` | Float64 | 7.45% | 4 | `4.0`, `443.0`, `999.0` | 4.00 | 999.00 |
| 49 | `CODPARC` | Float64 | 0.0% | 2.233 | `64730.0`, `63371.0`, `63959.0` | 808.00 | 99.999.00 |
| 50 | `PARCEIRO` | String | 0.0% | 1.797 | `BABUSKA PANIFD LTDA                     `, `VIA SABOR DELICATESSEN LTDA             `, `CARVALHO SUPERM LTDA                    ` |  |  |
| 51 | `NOMECIDPARC` | String | 0.0% | 228 | `5357-UBERLANDIA`, `5357-UBERLANDIA`, `5357-UBERLANDIA` |  |  |
| 52 | `UFPARC` | String | 0.0% | 13 | `AC`, `DF`, `GO`, `MG`, `MT`, `PE`, `PR`, `RJ`, `RO`, `RS`, `SC`, `SP`, `TO` |  |  |
| 53 | `CGCCPF_PAR` | String | 0.0% | 2.230 | `19.226.696/0001-05`, `05.547.143/0003-01`, `41.684.520/0001-48` |  |  |
| 54 | `PERFILEMPPARC` | String | 0.0% | 43 | `10101001 - Padaria                                                     `, `10101001 - Padaria                                                     `, `10101006 - Supermercado (entre 5 e 49 Checkouts)                      |  |  |
| 55 | `RAMOATIVPARC` | String | 0.31% | 9 | `1 - Atacarejo`, `2 - Atacado/Distribuidor`, `3 - Redes`, `4 - Varejo`, `5 - Indústrias`, `6 - Indústria de Ração`, `7 - Padaria`, `99 - Outros` |  |  |

#### Colunas com valores negativos (indício de devolução/estorno)

- `QTD`: 23.137 negativos
- `PESOLIQ`: 23.137 negativos
- `TONLIQ`: 23.137 negativos
- `PESOBRUTO`: 23.137 negativos
- `TONBRUTO`: 23.137 negativos
- `VLRTOT`: 23.137 negativos
- `VLRDESC`: 13 negativos
- `VLRREPRED`: 2 negativos
- `VLRICMS`: 23.075 negativos
- `VLRSUBST`: 5.325 negativos

### Aba: `Vendedor_Supervisor`

**458 linhas x 17 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `CODVEND` | 458 | 458 | SIM | 0 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CODVEND` | String | 0.0% | 458 | `3`, `4`, `5` |  |  |
| 2 | `APELIDO_VENDEDOR` | String | 0.0% | 417 | `EDUARDO  SOUS  `, `LUIZ C RUFINO  `, `JERONIMO ALVES ` |  |  |
| 3 | `TipoVend` | String | 0.0% | 3 | `R - Representante`, `S - Supervisor`, `V - Vendedor` |  |  |
| 4 | `VENDEDOR_ATIVO` | String | 0.0% | 2 | `N`, `S` |  |  |
| 5 | `CODPARC` | String | 0.0% | 448 | `33722`, `45325`, `20879` |  |  |
| 6 | `NOMEPARC` | String | 0.0% | 432 | `33722-EDUARDO SOUZA                     `, `45325-LUIZ CARLOS RUFINO                `, `ALVES RIBEIRO REP LTDA UDIA MATRIZ      ` |  |  |
| 7 | `RAZAO_SOCIAL` | String | 0.0% | 432 | `33722-EDUARDO SOUZA                     `, `45325-LUIZ CARLOS RUFINO                `, `ALVES RIBEIRO REP LTDA UDIA MATRIZ      ` |  |  |
| 8 | `CNPJ_CPF` | String | 0.0% | 420 | `23892420149   `, `43662528649   `, `01507528000114` |  |  |
| 9 | `EMAIL` | String | 0.0% | 95 | `                                                                                `, `                                                                                `, `                                                    |  |  |
| 10 | `TELEFONE` | String | 0.0% | 316 | `(34)349913781`, `(34)39764699`, `(34)39770604` |  |  |
| 11 | `CEP` | String | 0.0% | 335 | `38400000`, `38408106`, `38401664` |  |  |
| 12 | `NUMERO` | String | 0.0% | 275 | `350   `, `191   `, `245   ` |  |  |
| 13 | `COMPLEMENTO` | String | 0.0% | 141 | `GO / MT/ AC ...               `, `PROGRESSO                     `, `                              ` |  |  |
| 14 | `CIDADE` | String | 0.0% | 118 | `UBERLANDIA`, `UBERLANDIA`, `UBERLANDIA` |  |  |
| 15 | `ESTADO` | String | 0.0% | 18 | `0 `, `AC`, `AL`, `BA`, `DF`, `ES`, `GO`, `MA`, `MG`, `MS`, `MT`, `PE`, `PR`, `RJ`, `RS`, `SC`, `SP`, `TO` |  |  |
| 16 | `CODREGIAO` | String | 0.0% | 87 | `3010502`, `3010502`, `3010502` |  |  |
| 17 | `REGIAO` | String | 0.0% | 87 | `UBERLANDIA          `, `UBERLANDIA          `, `UBERLANDIA          ` |  |  |

### Aba: `Custos PA 012023 - 072026`

**29.135 linhas x 14 colunas**

#### Teste de grão

| Chave candidata | Linhas | Distintas | Único? | Duplicadas |
|---|---|---|---|---|
| `CODPROD + CODEMP + CODLOCAL + DTATUAL` | 29.135 | 29.135 | SIM | 0 |
| `CODPROD + DTATUAL` | 29.135 | 22.209 | **NAO** | 6.926 |

#### Colunas

| # | Coluna | Tipo | % nulo | Distintos | Domínio / amostra | Min | Max |
|---|---|---|---|---|---|---|---|
| 1 | `CODPROD` | Float64 | 0.0% | 101 | `20007.0`, `20007.0`, `20007.0` | 20.007.00 | 20.500.00 |
| 2 | `PRODUTO` | String | 0.0% | 99 | `FAR.LUNAR PP 1KG TP1                    `, `FAR.LUNAR PP 1KG TP1                    `, `FAR.LUNAR PP 1KG TP1                    ` |  |  |
| 3 | `CODGRUPOPROD` | Float64 | 0.0% | 3 | `4001000.0`, `4002000.0`, `4003000.0` | 4.001.000.00 | 4.003.000.00 |
| 4 | `GRUPO_PRODUTO` | String | 0.0% | 3 | `FARELO                        `, `FARINHAS                      `, `MISTURAS                      ` |  |  |
| 5 | `UNIDADE` | String | 0.0% | 5 | `CX`, `FD`, `KG`, `PT`, `SC` |  |  |
| 6 | `CODEMP` | Float64 | 0.0% | 4 | `1.0`, `2.0`, `4.0`, `6.0` | 1.00 | 6.00 |
| 7 | `CODLOCAL` | Float64 | 0.0% | 8 | `0.0`, `106001.0`, `106002.0`, `106003.0`, `106004.0`, `106006.0`, `106007.0`, `107001.0` | 0.00 | 107.001.00 |
| 8 | `DTATUAL` | Datetime(time_unit='ms', time_zone=None) | 0.0% | 1.085 | `2023-01-02 00:00:00`, `2023-01-05 00:00:00`, `2023-01-11 00:00:00` | 2023-01-02 00:00:00 | 2026-07-31 00:00:00 |
| 9 | `CUSMED` | Float64 | 0.0% | 26.690 | `28.8048842337`, `28.8048842337`, `28.703888248` | 0.00 | 341.323.81 |
| 10 | `CUSMEDICM` | Float64 | 0.0% | 26.814 | `29.3188696681`, `29.3188696681`, `29.1815889047` | 0.00 | 11.940.50 |
| 11 | `CUSSEMICM` | Float64 | 0.0% | 26.583 | `28.5725788320088`, `28.5725788320088`, `28.4639496865622` | 0.00 | 4.420.45 |
| 12 | `CUSREP` | Float64 | 0.0% | 13.667 | `28.8048842337`, `28.8048842337`, `26.9483535813` | -0.18 | 344.598.39 |
| 13 | `CUSGER` | Float64 | 0.0% | 23.555 | `28.8048842337`, `28.8048842337`, `26.9483535813` | -0.78 | 341.323.81 |
| 14 | `CUSVARIAVEL` | Float64 | 0.0% | 23.804 | `28.8048842337`, `28.8048842337`, `26.9483535813` | -0.22 | 425.061.12 |

#### Colunas com valores negativos (indício de devolução/estorno)

- `CUSREP`: 2 negativos
- `CUSGER`: 2 negativos
- `CUSVARIAVEL`: 2 negativos

---
