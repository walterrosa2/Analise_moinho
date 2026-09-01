# Task — Preparação para Deploy no Railway e Autenticação

Legenda: `[x]` concluído · `[ ]` pendente

## Checklist de Implementação

- [x] Auditar requisitos da skill `railway-deploy-checklist`.
- [x] Configurar suporte e normalização de `DATABASE_URL` (para dialeto `postgresql+psycopg://`) em `src/config.py`.
- [x] Configurar leitura dinâmica de porta (`PORT` / `server_port`) e credenciais em `src/config.py`.
- [x] Criar módulo de autenticação simples e seguro (`app/components/auth.py`) com login (`admin`/`admin`), comparação `hmac.compare_digest` e logout na barra lateral.
- [x] Integrar autenticação obrigatória em `app/main.py`.
- [x] Criar script de auto-seed e migração automática (`scripts/auto_seed.py`).
- [x] Criar script de entrypoint (`scripts/entrypoint.sh`) para o container Railway/Docker.
- [x] Ajustar `.dockerignore` para permitir os pacotes de dados processados (`!data/parquet/*.parquet`).
- [x] Atualizar `Dockerfile` com `ENV PORT=8501`, `EXPOSE 8501`, cópia de parquets e entrypoint seguro.
- [x] Criar `railway.toml` para orquestração declarativa do build e healthcheck no Railway.
- [x] Atualizar `.env.example` com documentação das variáveis de autenticação e deploy.
- [x] Criar testes unitários para autenticação (`tests/test_auth.py`).
- [x] Criar testes unitários para configurações Railway (`tests/test_railway_config.py`).
- [x] Validar linting (`ruff check`) em todo o projeto: 100% aprovado.
- [x] Validar suíte completa de testes (`pytest`): 100% aprovado.

## Validação

- `ruff check src app scripts tests`: passou sem erros.
- `pytest tests/test_auth.py tests/test_railway_config.py tests/test_paginas.py`: 21 passou.
- `pytest`: 73 passou.
