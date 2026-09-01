"""
Testes de configuração para o ambiente Railway.
"""
from __future__ import annotations

from src.config import Settings


def test_database_url_normalization_postgres_prefix() -> None:
    s = Settings(database_url="postgres://postgres:minhasenha@containers-us-west.railway.app:7890/railway")
    assert s.db_url == "postgresql+psycopg://postgres:minhasenha@containers-us-west.railway.app:7890/railway"


def test_database_url_normalization_postgresql_prefix() -> None:
    s = Settings(database_url="postgresql://postgres:minhasenha@roundhouse.proxy.rlwy.net:12345/railway")
    assert s.db_url == "postgresql+psycopg://postgres:minhasenha@roundhouse.proxy.rlwy.net:12345/railway"


def test_database_url_normalization_psycopg2_prefix() -> None:
    s = Settings(database_url="postgresql+psycopg2://postgres:minhasenha@host:5432/db")
    assert s.db_url == "postgresql+psycopg://postgres:minhasenha@host:5432/db"


def test_database_url_safe_mascara_senha() -> None:
    s = Settings(database_url="postgresql://admin_user:super_secret_password@host.railway.internal:5432/moinho")
    assert "super_secret_password" not in s.db_url_safe
    assert s.db_url_safe == "postgresql+psycopg://admin_user:***@host.railway.internal:5432/moinho"


def test_server_port_prioriza_env_port() -> None:
    # Quando Railway injeta PORT=8080
    s1 = Settings(port=8080, app_port=8501)
    assert s1.server_port == 8080

    # Quando não há PORT, usa app_port
    s2 = Settings(port=None, app_port=8501)
    assert s2.server_port == 8501


def test_database_url_sanitiza_parenteses_espurios() -> None:
    # Caso o usuário cole ${{Postgres.DATABASE_URL}}) com parêntese acidental no final
    s = Settings(database_url="postgresql://postgres:pass@postgres.railway.internal:5432/railway)")
    assert s.db_url == "postgresql+psycopg://postgres:pass@postgres.railway.internal:5432/railway"

