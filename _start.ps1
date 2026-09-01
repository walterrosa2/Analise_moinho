# =====================================================================
# Plataforma Analitica — Moinho Sete Irmaos
# Sobe o banco, prepara o ambiente, carrega os dados e abre a aplicacao.
#
#   .\_start.ps1              # fluxo completo
#   .\_start.ps1 -SoApp       # so a aplicacao (banco ja carregado)
#   .\_start.ps1 -Recarregar  # forca recarga de todas as fontes
# =====================================================================
param(
    [switch]$SoApp,
    [switch]$Recarregar,
    [int]$Porta = 8501
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "==============================================================" -ForegroundColor Cyan
Write-Host " Plataforma Analitica do Diagnostico Comercial" -ForegroundColor Cyan
Write-Host " Moinho Sete Irmaos" -ForegroundColor Cyan
Write-Host "==============================================================" -ForegroundColor Cyan

# --- 1. .env -----------------------------------------------------------
if (-not (Test-Path ".env")) {
    Write-Host "[1/5] Criando .env a partir de .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "      ATENCAO: revise a senha do banco em .env" -ForegroundColor Yellow
} else {
    Write-Host "[1/5] .env encontrado." -ForegroundColor Green
}

# --- 2. venv -----------------------------------------------------------
if (-not (Test-Path ".venv")) {
    Write-Host "[2/5] Criando ambiente virtual..." -ForegroundColor Yellow
    py -3 -m venv .venv
    & ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
    & ".venv\Scripts\python.exe" -m pip install -r requirements.txt
} else {
    Write-Host "[2/5] Ambiente virtual encontrado." -ForegroundColor Green
}
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# PYTHONPATH na raiz: obrigatorio porque a app roda de dentro de app/
$env:PYTHONPATH = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

# --- 3. PostgreSQL -----------------------------------------------------
Write-Host "[3/5] Subindo PostgreSQL..." -ForegroundColor Yellow
docker compose up -d postgres | Out-Null

$tentativas = 0
do {
    Start-Sleep -Seconds 2
    $tentativas++
    $pronto = (docker exec moinho_analytics_db pg_isready -U moinho 2>&1) -match "accepting connections"
} while (-not $pronto -and $tentativas -lt 30)

if (-not $pronto) {
    Write-Host "      ERRO: o banco nao respondeu em 60s." -ForegroundColor Red
    Write-Host "      Verifique: docker compose logs postgres" -ForegroundColor Red
    exit 1
}
Write-Host "      Banco pronto." -ForegroundColor Green

# --- 4. Pipeline -------------------------------------------------------
if (-not $SoApp) {
    Write-Host "[4/5] Executando o pipeline de dados..." -ForegroundColor Yellow
    if ($Recarregar) {
        & $Python scripts\run_pipeline.py --forcar
    } else {
        & $Python scripts\run_pipeline.py
    }
    if ($LASTEXITCODE -eq 3) {
        Write-Host "      ATENCAO: ha verificacoes criticas de qualidade falhando." -ForegroundColor Red
        Write-Host "      A aplicacao vai abrir, mas confira a pagina Qualidade antes de apresentar numeros." -ForegroundColor Red
    } elseif ($LASTEXITCODE -ne 0) {
        Write-Host "      ERRO no pipeline (codigo $LASTEXITCODE)." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "[4/5] Pipeline ignorado (-SoApp)." -ForegroundColor Gray
}

# --- 5. Aplicacao ------------------------------------------------------
Write-Host "[5/5] Abrindo a aplicacao em http://localhost:$Porta" -ForegroundColor Green
Write-Host "      Ctrl+C encerra." -ForegroundColor Gray
Write-Host ""

& $Python -m streamlit run app\main.py --server.port=$Porta --server.address=0.0.0.0
