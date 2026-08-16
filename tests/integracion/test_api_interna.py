"""La API que consume n8n. Lo que se prueba es la frontera, no la entrega."""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

TOKEN = "token-de-prueba"
CABECERA = {"X-Pacer-Token": TOKEN}


@pytest.fixture(scope="module")
def cliente(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    carpeta = tmp_path_factory.mktemp("bd-interna")
    previo = dict(os.environ)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{carpeta}/interna.db"
    os.environ["CALENTAR_VOZ"] = "false"
    os.environ["LANGFUSE_PUBLIC_KEY"] = ""
    os.environ["LANGFUSE_SECRET_KEY"] = ""
    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    os.environ["PACER_TOKEN"] = TOKEN

    from pacer.interfaces.http import app as modulo

    with TestClient(modulo.app) as cliente:
        yield cliente

    os.environ.clear()
    os.environ.update(previo)


def test_sin_token_no_se_entra(cliente: TestClient) -> None:
    assert cliente.get("/internal/recordatorios/vencidos").status_code == 401


def test_con_token_equivocado_tampoco(cliente: TestClient) -> None:
    respuesta = cliente.get(
        "/internal/recordatorios/vencidos", headers={"X-Pacer-Token": "otro"}
    )

    assert respuesta.status_code == 401


def test_con_el_token_correcto_responde(cliente: TestClient) -> None:
    respuesta = cliente.get("/internal/recordatorios/vencidos", headers=CABECERA)

    assert respuesta.status_code == 200
    assert isinstance(respuesta.json(), list)


def test_materializar_sin_plan_no_crea_nada(cliente: TestClient) -> None:
    respuesta = cliente.post("/internal/recordatorios/materializar", headers=CABECERA)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"nuevos": 0}


def test_confirmar_algo_inexistente_responde_sin_entregar(
    cliente: TestClient,
) -> None:
    respuesta = cliente.post(
        "/internal/recordatorios/9999/confirmar", headers=CABECERA, json={}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["entregado"] is False


async def _sembrar_plan_con_sesion_pasada(cliente: TestClient) -> None:
    """Un plan cuya primera sesión ya pasó y nadie reportó."""
    from pacer.application.casos_uso.crear_plan import crear_plan
    from pacer.domain.entidades.perfil import Perfil
    from pacer.infrastructure.persistencia.repositorio import RepositorioPlan
    from pacer.infrastructure.persistencia.repositorio_corredor import (
        RepositorioCorredor,
    )

    perfil = Perfil(
        objetivo="21k",
        nivel="intermedio",
        dias_disponibles=4,
        km_semana=25,
        fecha_carrera=datetime.now(UTC).date() + timedelta(weeks=12),
    )

    async with cliente.app.state.fabrica() as bd:
        corredores = RepositorioCorredor(bd)
        corredor = await corredores.obtener_o_crear_piloto()
        # Sin canal vinculado el recordatorio no tendría dónde llegar.
        await corredores.vincular_telegram(corredor.id, 555000)
        plan = crear_plan(perfil, hoy=datetime.now(UTC).date() - timedelta(days=2))
        await RepositorioPlan(bd).guardar(plan, corredor_id=corredor.id)


def test_el_ciclo_completo_del_contrato_con_n8n(cliente: TestClient) -> None:
    """Materializar → listar vencidos → confirmar → no reenviar.

    Es el contrato entero de `Architecture.md` §7.3 en un solo test.
    """
    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
        _sembrar_plan_con_sesion_pasada(cliente)
    )

    creados = cliente.post(
        "/internal/recordatorios/materializar", headers=CABECERA
    ).json()
    assert creados["nuevos"] >= 1

    # Correrlo otra vez no duplica: la clave es estable y la base la exige única.
    assert cliente.post(
        "/internal/recordatorios/materializar", headers=CABECERA
    ).json() == {"nuevos": 0}

    vencidos: list[dict[str, Any]] = cliente.get(
        "/internal/recordatorios/vencidos", headers=CABECERA
    ).json()
    assert vencidos
    assert vencidos[0]["clave_idempotencia"]
    assert vencidos[0]["canal"] == "telegram"
    # n8n lee el destino del dato, no de un campo fijo en el nodo.
    assert vencidos[0]["chat_id"] == 555000

    primero = vencidos[0]["id"]
    entrega = cliente.post(
        f"/internal/recordatorios/{primero}/confirmar",
        headers=CABECERA,
        json={"id_mensaje_proveedor": "msg_1"},
    ).json()
    assert entrega["entregado"] is True

    # El reintento de n8n no reenvía.
    reintento = cliente.post(
        f"/internal/recordatorios/{primero}/confirmar", headers=CABECERA, json={}
    ).json()
    assert reintento["entregado"] is False

    restantes = cliente.get(
        "/internal/recordatorios/vencidos", headers=CABECERA
    ).json()
    assert primero not in [r["id"] for r in restantes]
