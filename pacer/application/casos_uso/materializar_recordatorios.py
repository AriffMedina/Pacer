"""Convierte el plan vigente en recordatorios pendientes.

El backend decide QUÉ preguntar y CUÁNDO; n8n solo entrega. Correr esto de más
es inofensivo: la clave del recordatorio es estable y la base la exige única.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.servicios.recordatorios import recordatorios_pendientes
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor
from pacer.infrastructure.persistencia.repositorio_recordatorio import (
    RepositorioRecordatorio,
)


async def materializar_recordatorios(bd: AsyncSession, ahora: datetime) -> int:
    """Devuelve cuántos recordatorios nuevos se crearon."""
    corredor = await RepositorioCorredor(bd).obtener_o_crear_piloto()
    plan = await RepositorioPlan(bd).version_activa(corredor.id)

    if plan is None:
        return 0

    pendientes = recordatorios_pendientes(plan, corredor.id, ahora)
    return await RepositorioRecordatorio(bd).materializar(pendientes)
