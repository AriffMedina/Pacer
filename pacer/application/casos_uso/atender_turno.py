"""Un turno completo, con el plan cargado y guardado alrededor de la conversación.

El plan vive en la base, no en la conversación: si el corredor cierra la app y
contesta por Telegram tres horas después, el estado sigue ahí.
"""

from datetime import date
from typing import Any

from pacer.application.casos_uso.conversar import ResultadoTurno, procesar_turno
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import PuertoLLM
from pacer.domain.puertos.repositorio import PuertoRepositorioPlan


async def atender_turno(
    llm: PuertoLLM,
    repositorio: PuertoRepositorioPlan,
    sistema: str,
    mensajes: list[dict[str, Any]],
    perfil: Perfil,
    corredor_id: int,
    hoy: date,
) -> ResultadoTurno:
    """Carga el plan activo, procesa el turno y guarda si el plan cambió."""
    previo = await repositorio.version_activa(corredor_id)

    resultado = procesar_turno(llm, sistema, mensajes, perfil, hoy=hoy, plan=previo)

    if _hay_version_nueva(previo, resultado):
        assert resultado.plan is not None
        await repositorio.guardar(resultado.plan, corredor_id=corredor_id)

    return resultado


def _hay_version_nueva(previo: Any, resultado: ResultadoTurno) -> bool:
    """Se guarda solo cuando nace una versión: registrar un hecho no crea filas."""
    if resultado.plan is None:
        return False
    if previo is None:
        return True
    return bool(resultado.plan.version > previo.version)
