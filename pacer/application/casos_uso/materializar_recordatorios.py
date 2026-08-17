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
    """Devuelve cuántos recordatorios nuevos se crearon.

    Recorre a TODOS los corredores con Telegram vinculado, no al primero de la
    tabla: desde que cada navegador y cada chat son su propia persona, mirar
    solo a uno dejaría al resto sin recordatorios en silencio.

    Solo los que tienen chat: un recordatorio sin canal por donde salir no es
    un recordatorio, es una fila.
    """
    planes = RepositorioPlan(bd)
    nuevos = 0

    for corredor in await RepositorioCorredor(bd).con_telegram():
        plan = await planes.version_activa(corredor.id)
        if plan is None:
            continue
        pendientes = recordatorios_pendientes(plan, corredor.id, ahora)
        nuevos += await RepositorioRecordatorio(bd).materializar(pendientes)

    return nuevos
