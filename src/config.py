"""
Configuracao central da plataforma (pydantic-settings + .env).

Regra: configuracao > hardcode. Todo parametro de negocio discutivel
(data de referencia de custo, inicio das analises de positivados,
tolerancias de reconciliacao) vive aqui ou em config/*.yaml, nunca no codigo.
"""
from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]

load_dotenv(ROOT / ".env", override=True)


class Settings(BaseSettings):
    """Configuracao lida de .env com defaults seguros para desenvolvimento."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Banco ---
    postgres_user: str = "moinho"
    postgres_password: str = "moinho"
    postgres_db: str = "moinho_analytics"
    postgres_host: str = "localhost"
    postgres_port: int = 5434
    database_url: str | None = None

    # --- Autenticação simples (proteção para deploy) ---
    auth_enabled: bool = True
    auth_user: str = "admin"
    auth_password: str = "admin"

    # --- Diretorios ---
    input_dir: str = "data/input"
    parquet_dir: str = "data/parquet"
    export_dir: str = "data/exports"
    log_dir: str = "logs"

    # --- Aplicacao ---
    app_host: str = "0.0.0.0"
    app_port: int = 8501
    port: int | None = None  # Railway injeta PORT automaticamente
    log_level: str = "INFO"

    # --- Regras analiticas configuraveis ---
    cost_reference_date_field: str = Field(
        default="DTFATUR",
        description="Campo de data da venda usado como referencia no as-of join de custos.",
    )
    positivados_analysis_start: str = Field(
        default="2021-05",
        description="Mes inicial padrao das analises de positivados (pos-implantacao do ERP).",
    )
    reconciliation_revenue_pct_tolerance: float = 0.5
    reconciliation_volume_pct_tolerance: float = 0.5

    @computed_field  # type: ignore[prop-decorator]
    @property
    def server_port(self) -> int:
        """Porta do servidor: prioriza $PORT (Railway) sobre APP_PORT."""
        return self.port if self.port is not None else self.app_port

    @computed_field  # type: ignore[prop-decorator]
    @property
    def db_url(self) -> str:
        """URL SQLAlchemy. `DATABASE_URL` explicito tem precedencia com normalizacao de driver."""
        if self.database_url:
            raw = self.database_url.strip().rstrip(")\"',; \t\n\r")
            # Railway / Heroku passam postgres:// ou postgresql:// sem o driver psycopg v3
            if raw.startswith("postgres://"):
                return "postgresql+psycopg://" + raw[len("postgres://"):]
            if raw.startswith("postgresql://"):
                return "postgresql+psycopg://" + raw[len("postgresql://"):]
            if raw.startswith("postgresql+psycopg2://"):
                return "postgresql+psycopg://" + raw[len("postgresql+psycopg2://"):]
            return raw
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def db_url_safe(self) -> str:
        """URL sem senha, segura para log e para a tela de diagnostico."""
        url = self.db_url
        if "@" in url and "://" in url:
            prefix, rest = url.split("://", 1)
            creds, host_part = rest.split("@", 1)
            user = creds.split(":", 1)[0] if ":" in creds else creds
            return f"{prefix}://{user}:***@{host_part}"
        return url

    # --- Paths absolutos ---
    @property
    def root(self) -> Path:
        return ROOT

    @property
    def input_path(self) -> Path:
        return self._abs(self.input_dir)

    @property
    def parquet_path(self) -> Path:
        return self._abs(self.parquet_dir)

    @property
    def export_path(self) -> Path:
        return self._abs(self.export_dir)

    @property
    def log_path(self) -> Path:
        return self._abs(self.log_dir)

    @property
    def config_path(self) -> Path:
        return ROOT / "config"

    @staticmethod
    def _abs(value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else ROOT / p


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@functools.lru_cache(maxsize=32)
def load_yaml(relative_path: str) -> dict[str, Any]:
    """Le um YAML de config/ e devolve dict (cacheado)."""
    path = get_settings().config_path / relative_path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_source_contract(source_id: str) -> dict[str, Any]:
    """Contrato de dados de uma fonte (config/sources/<id>.yaml)."""
    return load_yaml(f"sources/{source_id}.yaml")


def list_source_contracts() -> list[dict[str, Any]]:
    """Todos os contratos de fonte declarados, na ordem de carga."""
    sources_dir = get_settings().config_path / "sources"
    contracts: list[dict[str, Any]] = []
    for path in sorted(sources_dir.glob("*.yaml")):
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        data["_contract_file"] = path.name
        contracts.append(data)
    return sorted(contracts, key=lambda c: c.get("load_order", 999))
