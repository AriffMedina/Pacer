"""Repositorio de planes. Traduce entre dominio y ORM en ambos sentidos.

Los planes no se sobrescriben: cada versión es una fila nueva y las anteriores
quedan archivadas con su `motivo_cambio`.
"""

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.plan import Plan, Semana, Sensacion, Sesion, TipoSesion
from pacer.infrastructure.persistencia.modelos import PlanORM, SemanaORM, SesionORM


class RepositorioPlan:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def guardar(self, plan: Plan, corredor_id: int) -> None:
        """Inserta una versión nueva, o reescribe la que ya existe.

        Versionar sigue siendo la regla para los CAMBIOS de plan. Pero dentro de
        una misma versión hay hechos que se acumulan —una sesión reportada como
        `normal` marca `completada` sin crear una v2— y esos también tienen que
        persistir. Antes se descartaban en silencio: el turno reportaba `ok` al
        modelo y nada llegaba a la base.
        """
        existente = await self._sesion.execute(
            select(PlanORM).where(
                PlanORM.corredor_id == corredor_id,
                PlanORM.version == plan.version,
            )
        )
        fila = existente.scalar_one_or_none()

        if fila is not None:
            await self._sesion.delete(fila)
            await self._sesion.flush()

        self._sesion.add(_a_orm(plan, corredor_id))
        await self._sesion.commit()

    async def borrar_todo(self, corredor_id: int) -> int:
        """Descarta el plan del corredor con todas sus versiones.

        Distinto de ajustar: ajustar versiona y archiva. Esto es "ya no voy a
        esa carrera". Se recorre y se borra fila por fila —en vez de un DELETE
        masivo— para que el cascade se lleve semanas y sesiones con él.
        """
        filas = (
            await self._sesion.execute(
                select(PlanORM).where(PlanORM.corredor_id == corredor_id)
            )
        ).scalars()

        borradas = 0
        for fila in filas:
            await self._sesion.delete(fila)
            borradas += 1

        await self._sesion.commit()
        return borradas

    async def versiones(self, corredor_id: int) -> list[Plan]:
        consulta = (
            select(PlanORM)
            .where(PlanORM.corredor_id == corredor_id)
            .order_by(PlanORM.version)
        )
        filas = await self._sesion.execute(consulta)
        return [_a_dominio(fila) for fila in filas.scalars()]

    async def version_activa(self, corredor_id: int) -> Plan | None:
        consulta = (
            select(PlanORM)
            .where(PlanORM.corredor_id == corredor_id)
            .order_by(PlanORM.version.desc())
            .limit(1)
        )
        fila = (await self._sesion.execute(consulta)).scalar_one_or_none()
        return _a_dominio(fila) if fila is not None else None


def _a_orm(plan: Plan, corredor_id: int) -> PlanORM:
    return PlanORM(
        corredor_id=corredor_id,
        version=plan.version,
        motivo_cambio=plan.motivo_cambio,
        semanas=[
            SemanaORM(
                numero=semana.numero,
                es_descarga=semana.es_descarga,
                bloque=semana.bloque,
                recortada=semana.recortada,
                sesiones=[
                    SesionORM(
                        fecha=sesion.fecha,
                        tipo=sesion.tipo,
                        km=sesion.km,
                        completada=sesion.completada,
                        sensacion=sesion.sensacion,
                    )
                    for sesion in semana.sesiones
                ],
            )
            for semana in plan.semanas
        ],
    )


def _a_dominio(fila: PlanORM) -> Plan:
    return Plan(
        version=fila.version,
        motivo_cambio=fila.motivo_cambio,
        semanas=tuple(
            Semana(
                numero=semana.numero,
                es_descarga=semana.es_descarga,
                # Las filas escritas antes de que existiera la columna vuelven
                # con NULL: el dominio espera los valores por defecto, no None.
                bloque=semana.bloque or "",
                recortada=bool(semana.recortada),
                sesiones=tuple(
                    Sesion(
                        fecha=sesion.fecha,
                        tipo=cast(TipoSesion, sesion.tipo),
                        km=sesion.km,
                        completada=sesion.completada,
                        sensacion=cast(Sensacion | None, sesion.sensacion),
                    )
                    for sesion in semana.sesiones
                ),
            )
            for semana in fila.semanas
        ),
    )
