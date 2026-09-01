"""
Testes unitários do módulo de autenticação e proteção de acesso.
"""
from __future__ import annotations

import pytest

from app.components.auth import _check_credentials
from src.config import Settings


def test_check_credentials_corretas(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(auth_user="admin", auth_password="admin_secret_password")
    monkeypatch.setattr("app.components.auth.get_settings", lambda: settings)

    assert _check_credentials("admin", "admin_secret_password") is True
    # Teste com espaços extras removidos
    assert _check_credentials(" admin ", "admin_secret_password") is True


def test_check_credentials_incorretas(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(auth_user="admin", auth_password="admin_secret_password")
    monkeypatch.setattr("app.components.auth.get_settings", lambda: settings)

    assert _check_credentials("admin", "senha_errada") is False
    assert _check_credentials("outro_usuario", "admin_secret_password") is False
    assert _check_credentials("", "") is False
