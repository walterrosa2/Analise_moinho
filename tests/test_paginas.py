"""
Smoke test das paginas Streamlit com AppTest.

Cada pagina e executada de verdade contra o banco carregado; o teste falha se
alguma levantar excecao. E o equivalente a abrir todas as telas uma a uma.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "app" / "pages").glob("p*.py"))

TIMEOUT = 180


@pytest.mark.parametrize("pagina", PAGES, ids=lambda p: p.stem)
def test_pagina_renderiza_sem_excecao(pagina: Path) -> None:
    app = AppTest.from_file(str(pagina), default_timeout=TIMEOUT)
    app.run()
    if app.exception:
        detalhes = "\n".join(
            f"{e.value}\n{getattr(e, 'stack_trace', '')}" for e in app.exception
        )
        pytest.fail(f"{pagina.name} levantou exceção:\n{detalhes}")


def test_main_carrega() -> None:
    app = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=TIMEOUT)
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
