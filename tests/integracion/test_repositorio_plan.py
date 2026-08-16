from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pacer.domain.entidades.plan import Sesion
from pacer.domain.servicios.ajustador import ajustar
from pacer.domain.servicios.generador_plan import generar_plan
from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

CORREDOR = 1


@pytest.fixture
async def sesion_bd() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion

    await motor.dispose()


def plan_nuevo():
    return generar_plan(
        distancia="21k",
        nivel="intermedio",
        semanas=12,
        km_semana=25,
        dias=4,
        inicio=date(2026, 8, 17),
    )


async def test_guarda_y_recupera_un_plan(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioPlan(sesion_bd)
    plan = plan_nuevo()

    await repositorio.guardar(plan, corredor_id=CORREDOR)
    recuperado = await repositorio.version_activa(corredor_id=CORREDOR)

    assert recuperado is not None
    assert recuperado.version == 1
    assert len(recuperado.semanas) == 12
    assert len(recuperado.semanas[0].sesiones) == 4


async def test_el_ajuste_deja_dos_versiones_y_la_v1_archivada(
    sesion_bd: AsyncSession,
) -> None:
    repositorio = RepositorioPlan(sesion_bd)
    plan = plan_nuevo()
    await repositorio.guardar(plan, corredor_id=CORREDOR)

    reporte = Sesion(
        fecha=plan.semanas[0].sesiones[-1].fecha,
        tipo="largo",
        km=10.0,
        completada=True,
        sensacion="muy_dura",
    )
    await repositorio.guardar(ajustar(plan, reporte), corredor_id=CORREDOR)

    versiones = await repositorio.versiones(corredor_id=CORREDOR)

    assert [p.version for p in versiones] == [1, 2]
    assert versiones[0].motivo_cambio is None
    assert versiones[1].motivo_cambio is not None
    assert "muy_dura" in versiones[1].motivo_cambio


async def test_la_version_activa_es_la_mas_reciente(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioPlan(sesion_bd)
    plan = plan_nuevo()
    await repositorio.guardar(plan, corredor_id=CORREDOR)

    reporte = Sesion(
        fecha=plan.semanas[0].sesiones[-1].fecha,
        tipo="largo",
        km=10.0,
        completada=True,
        sensacion="con_dolor",
    )
    await repositorio.guardar(ajustar(plan, reporte), corredor_id=CORREDOR)

    activa = await repositorio.version_activa(corredor_id=CORREDOR)

    assert activa is not None
    assert activa.version == 2
