# Walkthrough — Deploy no Railway & Autenticação da Plataforma

## O que foi implementado

1. **Camada de Autenticação Segura (Login Simples)**:
   - Tela de login inicial obrigatória com tema do Moinho Sete Irmãos.
   - Credenciais padrão: usuário `admin` e senha `admin` (configuráveis via variáveis `AUTH_USER` e `AUTH_PASSWORD`).
   - Comparação segura com `hmac.compare_digest` para mitigar ataques de temporização (*timing attacks*).
   - Bloqueio completo da aplicação via `st.stop()` até autenticação bem-sucedida.
   - Identificação do usuário conectado e botão de logout ("Sair") na barra lateral.

2. **Ajustes de Conformidade para Deploy no Railway (`railway-deploy-checklist`)**:
   - **Normalização de `DATABASE_URL`**: em `src/config.py`, conversão automática de URLs do Railway (`postgres://`, `postgresql://`, `postgresql+psycopg2://`) para `postgresql+psycopg://` (driver psycopg v3).
   - **Porta Dinâmica**: alinhamento com a porta injetada pelo Railway (`$PORT` -> `server_port`), com `ENV PORT=8501` e `EXPOSE 8501` no Dockerfile.
   - **Seed de Dados Automático**: inclusão dos conjuntos consolidados `data/parquet/*.parquet` (~13.5MB) na imagem Docker e criação do script `scripts/auto_seed.py`, garantindo que o PostgreSQL do Railway seja migrado e totalmente populado no primeiro boot sem intervenção manual.
   - **Entrypoint Resiliente**: `scripts/entrypoint.sh` aguarda o banco, executa migrations e carga inicial e sobe o Streamlit na porta do ambiente.
   - **Orquestração Railway**: criação do `railway.toml` definindo builder Dockerfile e healthchecks.

---

## Estrutura dos Arquivos Modificados / Criados

- `src/config.py`: adicionado suporte a `auth_enabled`, `auth_user`, `auth_password`, `port` / `server_port` e normalizador `db_url` / `db_url_safe`.
- `app/components/auth.py`: novo módulo de autenticação Streamlit (formulário de login e logout na sidebar).
- `app/main.py`: proteção de acesso via `auth.require_auth()` e renderização de `auth.render_user_sidebar()`.
- `scripts/auto_seed.py`: script de migração e carga idempotente do banco para ambientes em nuvem.
- `scripts/entrypoint.sh`: entrypoint do container para inicialização e subida do serviço.
- `Dockerfile`: atualizado para multi-stage com cópia dos parquets, porta configurável e entrypoint.
- `.dockerignore`: liberados os parquets de dados para inclusão na imagem Docker.
- `railway.toml`: manifesto declarativo de deploy para a plataforma Railway.
- `.env.example`: variáveis de ambiente documentadas para Railway e autenticação.
- `tests/test_auth.py`: testes unitários para a rotina de autenticação.
- `tests/test_railway_config.py`: testes de conformidade de porta e normalização de URLs do Railway.

---

## Como fazer o Deploy no Railway (Passo a Passo)

### Opção 1: Via Railway CLI (Mais rápido)

1. **Login no Railway** (caso ainda não tenha feito):
   ```bash
   railway login
   ```

2. **Vincular ou Criar o Projeto**:
   ```bash
   railway init
   ```

3. **Adicionar o Banco PostgreSQL no Railway**:
   - Pelo dashboard ou CLI: Adicione o plugin **PostgreSQL** no mesmo projeto do Railway.
   - O Railway criará automaticamente a variável `DATABASE_URL`.

4. **Configurar as Variáveis de Ambiente no Serviço Web**:
   No painel do Railway (ou via `railway variables`):
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}` (ou a URL de conexão do PostgreSQL Railway)
   - `AUTH_USER`: `admin` (ou o usuário desejado)
   - `AUTH_PASSWORD`: `admin` (ou a senha desejada)
   - `AUTH_ENABLED`: `true`

5. **Subir a Aplicação**:
   ```bash
   railway up
   ```
   *O container subirá, aplicará as migrações, carregará automaticamente os dados dos parquets para o PostgreSQL e iniciará a aplicação.*

---

### Opção 2: Via GitHub Integration no Railway

1. Envie o código para o repositório GitHub (`git push`).
2. No painel do [Railway](https://railway.com):
   - Clique em **+ New Project** -> **Deploy from GitHub repo**.
   - Selecione este repositório.
   - Clique em **+ New** -> **Database** -> **Add PostgreSQL**.
   - No serviço da aplicação web, adicione a variável de ambiente:
     `DATABASE_URL` conectada ao serviço PostgreSQL (ex: `${{Postgres.DATABASE_URL}}`).
   - Configure opcionalmente `AUTH_USER` e `AUTH_PASSWORD`.
3. O Railway fará o build do Dockerfile e deploy automático.

---

## Como Validar Localmente

1. **Executar a suíte de testes**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest
   ```

2. **Executar a checagem de estilo e qualidade**:
   ```powershell
   .\.venv\Scripts\python.exe -m ruff check src app scripts tests
   ```

3. **Abrir a aplicação localmente**:
   ```powershell
   .\_start.ps1
   ```
   - Acesse `http://localhost:8501`.
   - Digite o usuário `admin` e senha `admin`.
   - Navegue pelas páginas e valide os dados e gráficos.
