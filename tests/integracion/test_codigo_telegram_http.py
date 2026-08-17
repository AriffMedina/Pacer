"""El circuito entero: la web pide el código y el bot lo canjea.

Se prueba contra la API de verdad y no contra el repositorio porque lo que
importa es el contrato completo: que el código salga atado a LA COOKIE de
quien lo pidió, y que después ese chat resuelva a ese mismo corredor. Ahí es
donde estaba el agujero — cada canal creaba su propia persona.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

CHAT = 8_589_934_592


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    carpeta = tmp_path_factory.mktemp("bd-codigo-tg")
    previo = dict(os.environ)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{carpeta}/codigo.db"
    os.environ["CALENTAR_VOZ"] = "false"
    os.environ["LANGFUSE_PUBLIC_KEY"] = ""
    os.environ["LANGFUSE_SECRET_KEY"] = ""
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    from pacer.interfaces.http import app as modulo

    yield modulo.app

    os.environ.clear()
    os.environ.update(previo)


def navegador(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    """Un TestClient nuevo = un frasco de cookies nuevo = otra persona."""
    return TestClient(app)


async def _canjear(app, codigo: str, chat_id: int):  # type: ignore[no-untyped-def]
    from pacer.infrastructure.persistencia.repositorio_corredor import (
        RepositorioCorredor,
    )
    from pacer.infrastructure.reloj import ahora

    async with app.state.fabrica() as bd:
        return await RepositorioCorredor(bd).canjear_codigo_telegram(
            codigo, chat_id, ahora()
        )


def test_el_codigo_sale_con_la_forma_acordada(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        datos = cliente.post("/api/telegram/codigo").json()

    assert len(datos["codigo"]) == 6
    assert datos["codigo"].isdigit()
    assert datos["minutos"] == 10


def test_dos_navegadores_reciben_codigos_distintos(app) -> None:  # type: ignore[no-untyped-def]
    """Si compartieran código, canjear el tuyo me daría tu plan."""
    with navegador(app) as uno, navegador(app) as otro:
        assert (
            uno.post("/api/telegram/codigo").json()["codigo"]
            != otro.post("/api/telegram/codigo").json()["codigo"]
        )


@pytest.mark.anyio
async def test_canjear_hace_del_chat_el_corredor_de_esa_cookie(app) -> None:  # type: ignore[no-untyped-def]
    """El caso que justifica todo esto: armas el plan en la web y el bot te
    reconoce. Antes le escribías y te atendía como a un desconocido."""
    with navegador(app) as cliente:
        cliente.post(
            "/api/carreras",
            json={"nombre": "Maratón de Mérida", "km": 42.2, "fecha": "2027-01-10"},
        )
        codigo = cliente.post("/api/telegram/codigo").json()["codigo"]
        mias = cliente.get("/api/carreras").json()["carreras"]

    vinculado = await _canjear(app, codigo, CHAT)

    assert vinculado is not None
    assert vinculado.telegram_chat_id == CHAT
    # La prueba de que es la MISMA persona: lleva encima lo que apuntó por web.
    from pacer.infrastructure.persistencia.repositorio_carrera import (
        RepositorioCarrera,
    )

    async with app.state.fabrica() as bd:
        suyas = await RepositorioCarrera(bd).todas(vinculado.id)

    assert [c.nombre for c in suyas] == [c["nombre"] for c in mias] == [
        "Maratón de Mérida"
    ]


@pytest.mark.anyio
async def test_un_codigo_inventado_no_canjea(app) -> None:  # type: ignore[no-untyped-def]
    assert await _canjear(app, "000000", 8_589_934_599) is None
