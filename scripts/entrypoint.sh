#!/bin/sh
set -e

echo "=== Moinho Analytics — Iniciando Container ==="
echo "Porta configurada: ${PORT:-8501}"

# Garante inicialização do banco e seed de dados se necessário
python scripts/auto_seed.py || echo "Aviso: auto_seed não completou perfeitamente ou banco não estava disponível imediatamente."

echo "=== Iniciando Streamlit na porta ${PORT:-8501} ==="
exec streamlit run app/main.py \
    --server.port="${PORT:-8501}" \
    --server.address=0.0.0.0 \
    --server.headless=true
