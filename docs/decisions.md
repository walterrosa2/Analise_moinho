# Registro de Decisões de Arquitetura (ADRs)

Decisões que se afastam do óbvio ou da letra da especificação, com o motivo.
Quem herdar este código não deve precisar adivinhar por que algo é como é.

---

## ADR-001 · PostgreSQL na porta 5434

**Contexto.** A especificação define PostgreSQL em Docker. A máquina de desenvolvimento já roda
dois contêineres Postgres de outro projeto, ocupando 5432 e 5433.

**Decisão.** A porta do host é **5434**, configurável em `.env` (`POSTGRES_PORT`). Dentro da rede
Docker a porta continua sendo 5432.

**Consequência.** O ambiente sobe sem conflito ao lado de outros projetos. Quem usar uma máquina
limpa pode voltar para 5432 alterando uma linha do `.env`.

---

## ADR-002 · Migrations em SQL versionado, não autogeração do Alembic

**Contexto.** A especificação lista Alembic na stack. Alembic brilha quando o schema é derivado de
modelos ORM e as migrations são geradas por diff.

**Decisão.** Migrations são arquivos `.sql` numerados em `migrations/`, aplicados por
`src/db/migrate.py`, com checksum registrado em `app.schema_migrations`.

**Motivo.** Este é um data warehouse: quatro schemas, materialized views, `COMMENT ON COLUMN`
documentando regra de negócio, índices compostos para o as-of join. Nada disso é expresso
naturalmente por modelos ORM, e DDL gerado por diff é ilegível para o consultor que precisa
auditar a regra. O SQL explícito é o próprio documento.

**Consequência.** Alembic continua nas dependências para uso futuro. O runner avisa (sem
reaplicar) quando uma migration já aplicada é alterada — o caminho correto é criar uma nova.

---

## ADR-003 · Camada RAW com DDL gerado do cabeçalho real

**Contexto.** A especificação pede uma tabela RAW por aba. A tentação seria declarar as colunas
antecipadamente, a partir da documentação.

**Decisão.** O ingestor lê o cabeçalho real, gera `CREATE TABLE` com **todas as colunas como TEXT**
e acrescenta os seis metadados de linhagem. Colunas novas viram `ALTER TABLE ADD COLUMN`; colunas
que desaparecem são **mantidas** no schema e reportadas.

**Motivo.** Planilhas mudam. O contrato de dados (`config/sources/*.yaml`) é quem falha
ruidosamente quando uma coluna **obrigatória** some; o resto do layout pode variar sem quebrar a
carga. Guardar tudo como texto preserva a fidelidade: `'NULL'`, `'0,00'` e espaços à direita
chegam ao banco exatamente como estavam.

**Consequência.** Toda conversão acontece no staging, com regras explícitas e testáveis.

---

## ADR-004 · Conversão Decimal → Float64 na fronteira do banco

**Contexto.** `NUMERIC` do PostgreSQL chega ao Python como `decimal.Decimal`, e o polars o mapeia
para o tipo `Decimal`.

**Decisão.** `src/db/engine.read_sql` converte toda coluna Decimal para `Float64` ao devolver o
DataFrame.

**Motivo.** A aritmética de `Decimal` no polars reescala em divisões e agregações. Isso não é
teórico: **o rateio de frete saiu 1e-6 do valor correto** — R$ 25,69 em vez de R$ 25,67 milhões —
até a causa ser localizada. Converter uma vez na fronteira é mais seguro que espalhar casts por
dezenas de consultas.

**Consequência.** Precisão de ponto flutuante de 64 bits, suficiente para valores em reais na casa
dos bilhões. Se algum dia for preciso rigor decimal (fechamento contábil), a conversão deve ser
revista — e o lugar é este único ponto.

---

## ADR-005 · Credenciais bloqueadas na leitura, não filtradas depois

**Contexto.** O arquivo `Inventário de Dados relatórios Sankhya e outros` contém uma coluna
`Login e Senha` com **senhas em texto claro** de sistemas de terceiros (CONAB, Safras & Mercado,
Infoprice, entre outros).

**Decisão.** A coluna é declarada em `colunas_proibidas` no contrato da fonte e **descartada
durante a leitura do Excel**, antes de qualquer processamento. Ela não entra na camada RAW, no
Parquet, no log nem na aplicação. A carga registra um aviso nomeando a coluna bloqueada.

**Motivo.** Filtrar depois de carregar significa que a credencial existiu em disco. A camada RAW
é deliberadamente fiel — a única forma de mantê-la fiel *e* segura é nunca ler o dado.

**Consequência.** O catálogo de fontes importa apenas origem, localização e descrição. Se o cliente
precisar gerir essas credenciais, o lugar é um cofre de segredos, não este banco analítico.

**Verificação:** `tests/test_ingestao.py::test_credenciais_estao_bloqueadas_no_contrato` e
`::test_nenhuma_credencial_no_banco`.

---

## ADR-006 · CNPJ/CPF apenas como hash

**Decisão.** `dim_cliente` guarda `cgccpf_hash` (SHA-256 dos dígitos), nunca o documento em claro.

**Motivo.** Nenhuma análise prevista exige o documento legível: identificação usa `CODPARC`,
e deduplicação por documento funciona igualmente bem com o hash. Guardar o dado pessoal sem
necessidade seria risco gratuito sob a LGPD.

**Consequência.** O documento em claro permanece na camada RAW, que fica fora do repositório e
sob controle de acesso do banco. Se surgir uma necessidade legítima, ele está lá — mas a
exposição é uma decisão consciente, não o padrão.

---

## ADR-007 · Custo aplicado à quantidade, não à tonelagem

**Contexto.** A leitura natural de "custo por tonelada" levou à fórmula `TONLIQ × custo`.

**Decisão.** `custo_total = QTD × custo_unitário`, onde `QTD` está na unidade de venda do produto
(FD, SC, CX, KG, PT).

**Motivo.** O confronto com `VLRUNIT` mostrou que o custo da origem está na **mesma unidade do
preço unitário**: FAR.LUNAR PREMIUM 25KG tem `VLRUNIT` R$ 91,52 e `CUSGER` mediano R$ 47,49.
A fórmula anterior produzia margem proxy de **98,7%**, economicamente impossível para um moinho.
Com a correção, a margem fica em 26%–28% ao ano, estável.

**Consequência.** `custo_por_ton` continua disponível, mas como grandeza **derivada**
(`SUM(QTD × custo) / SUM(TONLIQ)`). Ver Q-15.

---

## ADR-008 · Outliers de custo excluídos do agregado, jamais corrigidos

**Contexto.** A fonte de custo tem valores extremos pontuais: `CUSGER` do mesmo produto varia de
R$ 0,96 a R$ 341.322,41, com mediana R$ 47,08.

**Decisão.** O dado bruto permanece intacto. Cada item recebe a flag `custo_outlier` (custo acima
de 5× a mediana do próprio produto, ou não positivo). Os agregados de custo excluem os outliers
**e informam quantas linhas ficaram de fora**. A margem compara receita e custo da mesma população
(`receita_com_custo`).

**Motivo.** A especificação proíbe corrigir ou excluir dado da origem (§36.4, §36.10). Mas incluir
um custo de R$ 341 mil por saco de farinha produziria uma margem de −1.235%, que também é mentira.
A saída honesta é isolar, informar e deixar a decisão para a Controladoria.

**Consequência.** Menos de 1% das linhas é excluído (0,09% a 0,98% por ano). O número aparece na
interface e na tela de Qualidade.

---

## ADR-009 · Regra `MB*` → BOLO validada contra o 161, não presumida

**Contexto.** O ERP tem 3 grupos de produto; o relatório 161 usa 4 classificações. O grupo
`MISTURAS` precisa ser dividido entre `MISTURAS` e `BOLO`.

**Decisão.** Produtos do grupo 4003000 cuja descrição começa com `MB` (Mistura para Bolo) são
classificados como `BOLO`; os demais, `MISTURAS`. A regra vive em
`config/product_classification.yaml`, versionada, e cada produto guarda a origem da classificação.

**Motivo.** A hipótese foi **testada antes de adotada**: o confronto com o 161 REALIZADO de 2025
fecha em −1,15% (FARINHAS), −0,51% (FARELO), −2,62% (BOLO) e −0,16% (MISTURAS) em tonelagem.

**Consequência.** O status é `PROVISIONAL` até o consultor comercial homologar. É a única causa
conhecida da divergência residual por classificação (Q-14).

---

## ADR-010 · Filtro global único atravessando todas as páginas

**Decisão.** Um objeto `Filtros` vive no estado da sessão e é lido por todas as páginas;
`src/repositories/filters.py` traduz o mesmo objeto para `WHERE` sobre fontes com colunas
diferentes.

**Motivo.** Sem isso, dois gráficos lado a lado podem estar falando de recortes distintos — o tipo
de erro que destrói a confiança em uma reunião, e que é invisível na tela.

**Consequência.** Um filtro sem coluna correspondente na consulta é ignorado em silêncio (não
quebra a página), mas o recorte ativo aparece escrito na barra lateral e carimbado nas exportações.

---

## ADR-011 · Página de Qualidade construída primeiro

**Decisão.** A tela de Qualidade e Reconciliação foi a primeira página implementada, antes de
qualquer dashboard comercial.

**Motivo.** A especificação (§28) afirma que sem ela "a plataforma corre o risco de parecer precisa
sem realmente ser confiável". Construir os gráficos bonitos primeiro cria o incentivo errado: o
número apresentável chega antes do número verificado.

**Consequência.** Todo dashboard nasceu já apoiado em 23 verificações automáticas e 1.064 pontos de
reconciliação, com falha crítica bloqueando o pipeline (código de saída 3).
