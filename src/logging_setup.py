"""
Logging (loguru) + trilha de auditoria JSONL.

Saida dupla:
  - stdout            -> operacao (Docker/CI)
  - logs/app.log      -> log humano rotativo
  - logs/audit.jsonl  -> eventos de auditoria estruturados

Higiene: nunca logar senha, token ou credencial. `_redact` remove chaves
sensiveis antes de serializar.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from src.config import get_settings

_SENSITIVE_KEYS = {
    "password", "senha", "passwd", "pwd", "token", "secret", "api_key",
    "apikey", "authorization", "credential", "credentials", "cgccpf",
    "cnpj_cpf", "cgccpf_par",
}

_configured = False


def _redact(value: Any) -> Any:
    """Remove valores de chaves sensiveis, recursivamente."""
    if isinstance(value, dict):
        return {
            k: ("***" if str(k).lower() in _SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    return value


def setup_logging(force: bool = False) -> None:
    """Configura os sinks do loguru (idempotente)."""
    global _configured
    if _configured and not force:
        return

    settings = get_settings()
    log_dir = settings.log_path
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
        ),
        filter=lambda record: "audit" not in record["extra"],
    )

    logger.add(
        log_dir / "app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        filter=lambda record: "audit" not in record["extra"],
    )

    logger.add(
        log_dir / "audit.jsonl",
        level="INFO",
        rotation="10 MB",
        retention="365 days",
        encoding="utf-8",
        serialize=True,
        filter=lambda record: "audit" in record["extra"],
    )

    _configured = True


def log_audit(
    action: str,
    *,
    actor: str = "agent",
    target: str = "system",
    outcome: str = "success",
    data: dict[str, Any] | None = None,
) -> None:
    """
    Registra um evento de auditoria em logs/audit.jsonl.

    Campos obrigatorios: timestamp, actor, action, target, outcome.
    """
    setup_logging()
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "actor": actor,
        "action": action,
        "target": target,
        "outcome": outcome,
        "data": _redact(data or {}),
    }
    logger.bind(audit=True).info(payload)


__all__ = ["logger", "setup_logging", "log_audit"]
