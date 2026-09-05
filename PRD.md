# PRD — Análise Geográfica de Potencial de Mercado (Minas Gerais)

## Objetivo

Responder à pergunta que o ranking de vendas não responde: **onde o Moinho Sete Irmãos
deveria vender em Minas Gerais**, e não apenas onde vende hoje.

A entrega sobrepõe três camadas sobre o mesmo mapa municipal e produz, da sobreposição,
uma leitura de expansão para a decisão do proprietário.

## Usuários

- **Proprietário e direção do Moinho** — decisão de expansão de mercado, alocação de
  representantes e escolha de canal.
- **Consultores de gestão** — instrumentação do diagnóstico comercial com base
  territorial e externa.
- **Direção comercial** — redesenho da divisão de territórios dos RCAs.

## As três camadas e a análise

| # | Camada | Natureza | Fonte |
|---|---|---|---|
| 1 | Venda por cidade de MG | fato | item de nota fiscal (`fact_venda_item`) |
| 2 | Território declarado dos RCAs | fato (declaração) | `REGIÃO COMERCIAL POR REPRESENTANTE` |
| 3 | Mercado potencial de farinha | estimativa | IBGE (CEMPRE, Censo, Localidades) + consumo observado |
| — | **Sobreposição** | derivada | matriz de White Space por município |

A quarta entrega é a **visão executiva de expansão**, que traduz a sobreposição em três
decisões concretas.

## Requisitos

### R1 — Universo municipal fechado
A análise cobre os **853 municípios de Minas Gerais**, e não apenas os que têm venda.
O município sem nenhuma venda é justamente o que revela o espaço; ele precisa aparecer.

### R2 — Integração por código IBGE, auditável
Três fontes escrevem o nome da cidade de três formas diferentes. O pareamento entre
grafia e código IBGE é um **dado inspecionável** (`analytics.map_cidade_ibge`), com o
método registrado linha a linha. O que não parear com segurança fica sem município —
uma lacuna visível vale mais que um município errado no mapa.

### R3 — Potencial medido pela economia real do Moinho
O consumo por estabelecimento não vem da internet: é a **mediana de toneladas/mês dos
clientes reais do Moinho** no mesmo segmento, aplicada ao universo de empresas que o
IBGE registra em cada município. É o método recomendado pelo relatório de pesquisa
`deep-research-report-potencial-vendas.md`.

### R4 — Escopo de produto correto
O estudo é de **farinha**: `FARINHAS`, `MISTURAS` e `BOLO`. `FARELO` fica de fora — é
cadeia de ração animal, não de panificação, e distorceria tanto a venda quanto o
potencial.

### R5 — Parâmetros de negócio fora do código
Intensidade por segmento, probabilidade de captura, CNAEs, cortes de percentil, janela
de venda e URLs das fontes vivem em `config/mercado_mg.yaml`. Trocar um número lá
recalcula o mapa inteiro sem tocar em código nem em migration.

### R6 — Fronteira entre fato e estimativa sempre explícita
A tela nunca mistura as duas naturezas sem dizer qual está usando. Onde o número é
estimado, a origem (`OBSERVADO` ou `FALLBACK`) e a amostra aparecem.

### R7 — A internet não pode derrubar o pipeline
A camada externa é a única que depende de rede. Sem internet, o pipeline usa o cache e
segue; sem cache, a etapa é pulada e o diagnóstico comercial continua íntegro.

## Restrições

- Os arquivos originais nunca são modificados.
- O CEMPRE conta empresas formais atuantes. A base aberta do CNPJ e os números da ABIP
  usam definições diferentes e incluem MEI; **somar ou comparar as fontes produziria
  número sem significado**. A fonte é única e declarada.
- O potencial ordena prioridade entre municípios (posição relativa). **Não é meta de
  venda, não é consumo total do município e não é participação de mercado.**

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Cidade de outro estado pareada com município de MG por semelhança de grafia | Pareamento exige primeiro token igual e margem de desempate; grafia disputada vira `AMBIGUO` e não recebe município. Coberto por teste. |
| Percentil de venda calculado sobre os 853 cairia em zero (733 não vendem) e promoveria todo município a "venda alta" | O corte de venda é calculado só entre municípios que vendem; venda zero é sempre venda baixa. Coberto por teste. |
| Sigilo estatístico do IBGE no pessoal ocupado interpretado como ausência de empresas | `pessoal_ocupado` permanece `NULL`; o porte estimado vai em coluna separada e nunca se disfarça de dado publicado. |
| Probabilidade de captura tratada como fato | Marcada como `PROVISIONAL` no YAML, registrada em Q-16 e avisada na tela. |
| Duas fontes divergentes para a mesma leitura (MV e repositório) | Teste compara as duas na janela padrão e falha se divergirem. |
