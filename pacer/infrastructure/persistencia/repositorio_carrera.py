"""Repositorio de las carreras apuntadas."""

from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.carrera import Carrera
from pacer.infrastructure.persistencia.modelos import CarreraORM


class RepositorioCarrera:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def todas(self, corredor_id: int) -> tuple[Carrera, ...]:
        consulta = (
            select(CarreraORM)
            .where(CarreraORM.corredor_id == corredor_id)
            .order_by(CarreraORM.fecha)
        )
        filas = (await self._sesion.execute(consulta)).scalars()
        return tuple(_a_dominio(fila) for fila in filas)

    async def agregar(self, corredor_id: int, carrera: Carrera) -> Carrera:
        """Apunta una carrera. Repetir la misma devuelve la que ya estaba.

        La unicidad la garantiza la base, no una consulta previa: entre el
        SELECT y el INSERT cabe otro turno, y el usuario puede estar hablando
        por Telegram mientras la agrega en la web.
        """
        fila = CarreraORM(
            corredor_id=corredor_id,
            fecha=carrera.fecha,
            nombre=carrera.nombre,
            distancia_km=carrera.distancia_km,
            nota=carrera.nota,
        )
        self._sesion.add(fila)
        try:
            await self._sesion.commit()
        except IntegrityError:
            await self._sesion.rollback()
            return await self._misma(corredor_id, carrera)

        await self._sesion.refresh(fila)
        return _a_dominio(fila)

    async def _misma(self, corredor_id: int, carrera: Carrera) -> Carrera:
        consulta = select(CarreraORM).where(
            CarreraORM.corredor_id == corredor_id,
            CarreraORM.fecha == carrera.fecha,
            CarreraORM.nombre == carrera.nombre,
        )
        fila = (await self._sesion.execute(consulta)).scalar_one()
        return _a_dominio(fila)

    async def quitar(self, corredor_id: int, carrera_id: int) -> bool:
        """Borra una carrera del corredor. Devuelve si existía.

        El `corredor_id` va en el WHERE aunque el id sea único: es lo que evita
        que un id ajeno borre lo de otra persona el día que haya login.
        """
        resultado = await self._sesion.execute(
            delete(CarreraORM).where(
                CarreraORM.id == carrera_id,
                CarreraORM.corredor_id == corredor_id,
            )
        )
        await self._sesion.commit()
        return bool(cast("CursorResult[Any]", resultado).rowcount)


def _a_dominio(fila: CarreraORM) -> Carrera:
    return Carrera(
        id=fila.id,
        fecha=fila.fecha,
        nombre=fila.nombre,
        # Se redondea también al LEER: las filas guardadas antes de esta regla
        # traen la basura decimal con la que se escribieron.
        distancia_km=_un_decimal(
            fila.distancia_km
            if fila.distancia_km is not None
            else _km_del_texto_viejo(fila.distancia)
        ),
        nota=fila.nota,
    )


def _un_decimal(km: float | None) -> float | None:
    return round(km, 1) if km is not None else None


# Distancias que se guardaron como texto antes de que fueran kilómetros.
TEXTO_VIEJO = {"5k": 5.0, "10k": 10.0, "21k": 21.1, "maraton": 42.2, "maratón": 42.2}


def _km_del_texto_viejo(texto: str | None) -> float | None:
    """Rescata la distancia de las filas escritas cuando era texto libre.

    Es compatibilidad hacia atrás, no una función de negocio: en cuanto esas
    filas se reescriban, esto y la columna vieja se van juntas.
    """
    if not texto:
        return None

    limpio = texto.strip().lower()
    if limpio in TEXTO_VIEJO:
        return TEXTO_VIEJO[limpio]

    try:
        return float(limpio.removesuffix("km").removesuffix("k").strip())
    except ValueError:
        return None
