#!/bin/sh
set -e

PORTA_PADRAO=8501
PORTA="${PORT:-$PORTA_PADRAO}"

echo "=== Moinho Analytics — Iniciando Container ==="

# Diagnostico de porta explicito.
#
# Um 502 no Railway com o app saudavel quase sempre significa que o proxy bate
# numa porta diferente da que o app escuta. Sao DUAS configuracoes separadas:
#   - a variavel PORT (aqui embaixo)
#   - o "target port" do dominio publico (Settings -> Networking)
# Se as duas divergirem, o healthcheck pode ate passar e toda requisicao
# retorna 502. Registrar a origem da porta evita deduzir isso no escuro.
if [ -n "${PORT}" ]; then
    echo "Porta: ${PORTA} (veio da variavel de ambiente PORT)"
else
    echo "Porta: ${PORTA} (PORT nao definida — usando o padrao do Dockerfile)"
    echo "  Atencao: se o dominio publico do Railway apontar para outra porta,"
    echo "  todas as requisicoes retornarao 502 mesmo com o app no ar."
fi

# Garante inicialização do banco e seed de dados se necessário
python scripts/auto_seed.py || echo "Aviso: auto_seed não completou perfeitamente ou banco não estava disponível imediatamente."

echo "=== Iniciando Streamlit em 0.0.0.0:${PORTA} ==="
exec streamlit run app/main.py \
    --server.port="${PORTA}" \
    --server.address=0.0.0.0 \
    --server.headless=true
