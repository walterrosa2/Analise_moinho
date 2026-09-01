# PRD — Plataforma Analítica do Diagnóstico Comercial & Deploy Railway

## Objetivo

Disponibilizar a plataforma analítica do Diagnóstico Comercial do Moinho Sete Irmãos em nuvem (Railway) para acesso e análise colaborativa de outros consultores, com proteção de acesso por credenciais simples e garantia de carga/persistência de todos os dados do banco analítico.

## Usuários

- Consultores de gestão que realizam diagnósticos, reuniões executivas e análises aprofundadas em ambiente compartilhado.
- Diretoria e lideranças das áreas Comercial, Logística e Controladoria do Moinho Sete Irmãos.

## Requisitos de Deploy e Proteção (Railway)

1. **Camada de Autenticação Simples**:
   - Tela de login inicial obrigatória com credenciais configuráveis (`AUTH_USER` e `AUTH_PASSWORD`), tendo como padrão `admin` / `admin`.
   - Bloqueio completo do acesso aos dados e navegação para usuários não autenticados.
   - Opção de logout na barra lateral.
2. **Conexão Resiliente PostgreSQL**:
   - Compatibilidade com URLs dinâmicas do Railway (`DATABASE_URL`), com normalização automática de dialeto para `postgresql+psycopg://`.
   - Máscara de segurança para URLs de banco em logs e telas de diagnóstico.
3. **Seed e Carga de Dados**:
   - Carga automatizada no deploy (`auto_seed.py` e `run_pipeline.py`) a partir dos dados pré-processados (`data/parquet/*.parquet`).
   - Execução automática de migrações e reconstrução de views materializadas sem intervenção manual.
4. **Alinhamento de Porta e Entrypoint**:
   - Conformidade com a skill `railway-deploy-checklist`: `ENV PORT=8501`, `EXPOSE 8501` e inicialização dinâmica via variável `$PORT`.

## Restrições

- Credenciais reais nunca devem ser commitadas em repositórios públicos.
- Dados brutos e planilhas originais permanecem isolados; apenas os conjuntos consolidados (`parquet`) são utilizados para seed.
- A autenticação não deve interferir na arquitetura desacoplada de dados (Streamlit -> Repositories -> PostgreSQL).

## Riscos e Mitigações

- **Risco**: Instância PostgreSQL do Railway reiniciar ou iniciar vazia.
  - **Mitigação**: O script `scripts/auto_seed.py` no entrypoint detecta banco não populado e executa a carga e migrações automaticamente de forma idempotente.
- **Risco**: Porta roteada pelo proxy do Railway ser diferente da porta do Streamlit.
  - **Mitigação**: O entrypoint consome diretamente `${PORT}` e `src/config.py` normaliza a porta de execução.
