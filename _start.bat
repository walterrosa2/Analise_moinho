@echo off
REM ====================================================================
REM  Plataforma Analitica - Moinho Sete Irmaos
REM  Sobe o banco, prepara o ambiente, carrega os dados e abre a app.
REM ====================================================================
setlocal
cd /d "%~dp0"

echo ==============================================================
echo  Plataforma Analitica do Diagnostico Comercial
echo  Moinho Sete Irmaos
echo ==============================================================

if not exist ".env" (
    echo [1/5] Criando .env a partir de .env.example...
    copy ".env.example" ".env" >nul
    echo       ATENCAO: revise a senha do banco em .env
) else (
    echo [1/5] .env encontrado.
)

if not exist ".venv" (
    echo [2/5] Criando ambiente virtual...
    py -3 -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
) else (
    echo [2/5] Ambiente virtual encontrado.
)

REM PYTHONPATH na raiz: obrigatorio porque a app roda de dentro de app/
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8

echo [3/5] Subindo PostgreSQL...
docker compose up -d postgres >nul 2>&1
if errorlevel 1 (
    echo       ERRO: Docker nao esta disponivel.
    exit /b 1
)

echo       Aguardando o banco...
set /a TENTATIVAS=0
:aguardar
timeout /t 2 /nobreak >nul
docker exec moinho_analytics_db pg_isready -U moinho >nul 2>&1
if not errorlevel 1 goto pronto
set /a TENTATIVAS+=1
if %TENTATIVAS% lss 30 goto aguardar
echo       ERRO: o banco nao respondeu em 60s. Veja: docker compose logs postgres
exit /b 1

:pronto
echo       Banco pronto.

echo [4/5] Executando o pipeline de dados...
".venv\Scripts\python.exe" scripts\run_pipeline.py
if errorlevel 3 (
    echo       ATENCAO: ha verificacoes criticas falhando. Confira a pagina Qualidade.
) else if errorlevel 1 (
    echo       ERRO no pipeline.
    exit /b 1
)

echo [5/5] Abrindo a aplicacao em http://localhost:8501
echo       Ctrl+C encerra.
echo.
".venv\Scripts\python.exe" -m streamlit run app\main.py --server.port=8501 --server.address=0.0.0.0

endlocal
