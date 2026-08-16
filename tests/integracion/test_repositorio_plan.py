from dataclasses import replace
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.plan import Sesion
from pacer.domain.servicios.ajustador import ajustar
from pacer.domain.servicios.generador_plan import generar_plan
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

CORREDOR = 1


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


async def test_borrar_el_plan_se_lleva_todas_sus_versiones(
    sesion_bd: AsyncSession,
) -> None:
    """"Ya no voy a esa carrera" no es un ajuste, es descartar.

    Si quedara la v1 colgando, `version_activa` la devolvería y el coach
    seguiría recordando sesiones de algo que el corredor ya canceló.
    """
    repositorio = RepositorioPlan(sesion_bd)
    plan = plan_nuevo()
    await repositorio.guardar(plan, corredor_id=CORREDOR)
    await repositorio.guardar(
        replace(plan, version=2, motivo_cambio="bajé la carga"), corredor_id=CORREDOR
    )

    borradas = await repositorio.borrar_todo(CORREDOR)

    assert borradas == 2
    assert await repositorio.version_activa(CORREDOR) is None
    assert await repositorio.versiones(CORREDOR) == []


async def test_borrar_no_toca_el_plan_de_otro_corredor(
    sesion_bd: AsyncSession,
) -> None:
    repositorio = RepositorioPlan(sesion_bd)
    await repositorio.guardar(plan_nuevo(), corredor_id=CORREDOR)
    await repositorio.guardar(plan_nuevo(), corredor_id=99)

    await repositorio.borrar_todo(CORREDOR)

    assert await repositorio.version_activa(99) is not None


async def test_borrar_cuando_no_hay_plan_no_revienta(sesion_bd: AsyncSession) -> None:
    assert await RepositorioPlan(sesion_bd).borrar_todo(CORREDOR) == 0


async def test_el_viaje_de_ida_y_vuelta_no_pierde_como_se_describe_la_semana(
    sesion_bd: AsyncSession,
) -> None:
    """`bloque` y `es_descarga` son lo que el plan dice de sí mismo.

    Se perdían al guardar: el generador los calculaba, la base no los tenía y la
    vista mostraba un guion donde iba "construcción". Que el plan se describa
    solo es la mitad del valor de periodizarlo.
    """
    repositorio = RepositorioPlan(sesion_bd)
    plan = plan_nuevo()

    await repositorio.guardar(plan, corredor_id=CORREDOR)
    recuperado = await repositorio.version_activa(corredor_id=CORREDOR)

    assert recuperado is not None
    assert [s.bloque for s in recuperado.semanas] == [s.bloque for s in plan.semanas]
    assert [s.es_descarga for s in recuperado.semanas] == [
        s.es_descarga for s in plan.semanas
    ]
    assert any(s.bloque for s in recuperado.semanas)


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
