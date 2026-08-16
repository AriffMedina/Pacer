"""Repositorio de recordatorios.

La idempotencia vive en la base: `clave` es UNIQUE. Materializar de más no
duplica y confirmar de más no reenvía, sin que quien llame tenga que acordarse.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.recordatorio import Recordatorio
from pacer.infrastructure.persistencia.modelos import RecordatorioORM

LIMITE_POR_TANDA = 20


class RepositorioRecordatorio:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def materializar(self, recordatorios: list[Recordatorio]) -> int:
        """Guarda los que falten. Devuelve cuántos son nuevos."""
        nuevos = 0

        for recordatorio in recordatorios:
            self._sesion.add(
                RecordatorioORM(
                    corredor_id=recordatorio.corredor_id,
                    clave=recordatorio.clave,
                    texto=recordatorio.texto,
                    programado_para=recordatorio.programado_para,
                    canal=recordatorio.canal,
                )
            )
            try:
                await self._sesion.commit()
                nuevos += 1
            except IntegrityError:
                # Ya existía: es exactamente lo que la clave UNIQUE debe hacer.
                await self._sesion.rollback()

        return nuevos

    async def vencidos(
        self, ahora: datetime, limite: int = LIMITE_POR_TANDA
    ) -> list[Recordatorio]:
        """Los que ya tocaban y nadie ha entregado todavía."""
        consulta = (
            select(RecordatorioORM)
            .where(
                RecordatorioORM.enviado_en.is_(None),
                RecordatorioORM.programado_para <= ahora,
            )
            .order_by(RecordatorioORM.programado_para)
            .limit(limite)
        )
        filas = (await self._sesion.execute(consulta)).scalars()
        return [_a_dominio(fila) for fila in filas]

    async def confirmar(
        self, recordatorio_id: int, id_mensaje_proveedor: str | None = None
    ) -> bool:
        """Marca como entregado. Devuelve False si ya lo estaba.

        Que un reintento de n8n devuelva False en vez de reenviar es la razón de
        que la confirmación sea segura de repetir.
        """
        fila = await self._sesion.get(RecordatorioORM, recordatorio_id)
        if fila is None or fila.enviado_en is not None:
            return False

        fila.enviado_en = datetime.now(tz=fila.programado_para.tzinfo)
        fila.id_mensaje_proveedor = id_mensaje_proveedor
        await self._sesion.commit()
        return True


def _a_dominio(fila: RecordatorioORM) -> Recordatorio:
    return Recordatorio(
        id=fila.id,
        corredor_id=fila.corredor_id,
        texto=fila.texto,
        programado_para=fila.programado_para,
        clave=fila.clave,
        canal=fila.canal,
        enviado_en=fila.enviado_en,
    )
