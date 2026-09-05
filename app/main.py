"""
Plataforma Analítica do Diagnóstico Comercial — Moinho Sete Irmãos.

Ponto de entrada do Streamlit. As páginas ficam em app/pages/ e falam apenas
com src/repositories — nenhuma SQL é escrita na camada de interface.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Permite `streamlit run app/main.py` a partir da raiz do projeto
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.components import auth, ui  # noqa: E402
from src.db.engine import ping  # noqa: E402
from src.logging_setup import setup_logging  # noqa: E402

st.set_page_config(
    page_title="Moinho Sete Irmãos — Diagnóstico Comercial",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

setup_logging()

CSS = """
<style>
  .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }
  [data-testid="stMetricValue"] { font-size: 1.55rem; font-weight: 600; }
  [data-testid="stMetricLabel"] { font-size: 0.78rem; opacity: 0.75; text-transform: uppercase;
                                  letter-spacing: 0.04em; }
  [data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
  h1 { font-size: 1.75rem !important; font-weight: 650; }
  h2 { font-size: 1.3rem !important; }
  h4 { margin-top: 1.4rem; font-weight: 600; }
  div[data-testid="stDataFrame"] { border-radius: 8px; }
  .stTabs [data-baseweb="tab-list"] { gap: 2px; }
  .stTabs [data-baseweb="tab"] { padding: 6px 14px; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Autenticação obrigatória (usuário e senha)
auth.require_auth()

if not ping():
    st.error(
        "**PostgreSQL indisponível.**\n\n"
        "Suba o banco e carregue os dados:\n\n"
        "```\ndocker compose up -d postgres\npy scripts/run_pipeline.py\n```"
    )
    st.stop()

ui.guia_rapido_navegacao()
auth.render_user_sidebar()

PAGINAS = {
    "Diagnóstico": [
        st.Page("pages/p00_visao_geral.py", title="Visão Geral", icon="🏠", default=True),
        st.Page("pages/p01_qualidade.py", title="Qualidade e Reconciliação", icon="🔍"),
    ],
    "Comercial": [
        st.Page("pages/p02_gestao_mix.py", title="Gestão Diária e Mix", icon="📊"),
        st.Page("pages/p03_vendas.py", title="Vendas e Devoluções", icon="🧾"),
        st.Page("pages/p04_regional.py", title="Regional e Territorial", icon="🗺️"),
        st.Page("pages/p13_potencial_mg.py", title="Potencial de Mercado MG", icon="🎯"),
        st.Page("pages/p05_rcas.py", title="RCAs e Vendedores", icon="👥"),
        st.Page("pages/p06_clientes.py", title="Clientes", icon="🏢"),
        st.Page("pages/p07_positivados.py", title="Positivados e Coortes", icon="🌱"),
    ],
    "Econômico": [
        st.Page("pages/p08_custos.py", title="Custos", icon="💰"),
        st.Page("pages/p09_logistica.py", title="Logística e CT-e", icon="🚚"),
        st.Page("pages/p10_trigo.py", title="Trigo × Custo × PMV", icon="🌾"),
    ],
    "Ferramentas": [
        st.Page("pages/p11_explorador.py", title="Explorador", icon="🧭"),
        st.Page("pages/p12_admin.py", title="Admin e Diagnóstico", icon="⚙️"),
    ],
}

navegacao = st.navigation(PAGINAS)
navegacao.run()
