"""
Mecanismo de autenticação simples e seguro para acesso à plataforma.

Bloqueia o acesso às páginas analíticas enquanto o usuário não autenticar com
as credenciais configuradas em Settings (AUTH_USER e AUTH_PASSWORD).
"""
from __future__ import annotations

import hmac

import streamlit as st

from src.config import get_settings


def _check_credentials(user_input: str, password_input: str) -> bool:
    settings = get_settings()
    expected_user = settings.auth_user.strip()
    expected_pass = settings.auth_password.strip()

    user_match = hmac.compare_digest(
        user_input.strip().encode("utf-8"),
        expected_user.encode("utf-8"),
    )
    pass_match = hmac.compare_digest(
        password_input.strip().encode("utf-8"),
        expected_pass.encode("utf-8"),
    )
    return user_match and pass_match


def require_auth() -> None:
    """
    Exige autenticação. Se não autenticado, renderiza formulário de login e interrompe execução.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        return

    if st.session_state.get("authenticated", False):
        return

    login_css = """
    <style>
      .login-box {
        max-width: 460px;
        margin: 2.5rem auto 1rem auto;
        padding: 2rem 2.2rem;
        background: #ffffff;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border: 1px solid #eaeaea;
        text-align: center;
      }
      .login-logo {
        font-size: 2.8rem;
        margin-bottom: 0.3rem;
      }
      .login-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 0.2rem;
      }
      .login-subtitle {
        font-size: 0.88rem;
        color: #666666;
        margin-bottom: 1.5rem;
      }
    </style>
    """
    st.markdown(login_css, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div class="login-box">
                <div class="login-logo">🌾</div>
                <div class="login-title">Moinho Sete Irmãos</div>
                <div class="login-subtitle">Diagnóstico Comercial &bull; Acesso Restrito</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form", clear_on_submit=False):
            # Sem placeholder de exemplo: a tela de login não sugere credencial.
            username = st.text_input(
                "Usuário",
                autocomplete="username",
            )
            password = st.text_input(
                "Senha",
                type="password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Entrar na Plataforma",
                use_container_width=True,
                type="primary",
            )

            if submitted:
                if _check_credentials(username, password):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username.strip()
                    st.success("Autenticação realizada com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos. Verifique suas credenciais.")

    st.stop()


def render_user_sidebar() -> None:
    """
    Renderiza na barra lateral o usuário logado e a opção de logout.
    """
    settings = get_settings()
    if not settings.auth_enabled:
        return

    if not st.session_state.get("authenticated", False):
        return

    username = st.session_state.get("username", settings.auth_user)
    with st.sidebar:
        st.markdown("---")
        c1, c2 = st.columns([3, 2])
        with c1:
            st.markdown(f"👤 **{username}**")
        with c2:
            if st.button("Sair", key="btn_logout", use_container_width=True):
                st.session_state["authenticated"] = False
                st.session_state.pop("username", None)
                st.rerun()
