"""Un turno completo, con el plan cargado y guardado alrededor de la conversación.

El plan vive en la base, no en la conversación: si el corredor cierra la app y
contesta por Telegram tres horas después, el estado sigue ahí.
"""

from datetime import date
from typing import Any

from pacer.application.casos_uso.conversar import ResultadoTurno, procesar_turno
from pacer.domain.entidades.carrera import Carrera
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
    carreras: tuple[Carrera, ...] = (),
) -> ResultadoTurno:
    """Carga el plan activo, procesa el turno y guarda si el plan cambió."""
    previo = await repositorio.version_activa(corredor_id)

    resultado = procesar_turno(
        llm, sistema, mensajes, perfil, hoy=hoy, plan=previo, carreras=carreras
    )

    if _hay_algo_que_guardar(previo, resultado):
        assert resultado.plan is not None
        await repositorio.guardar(resultado.plan, corredor_id=corredor_id)

    return resultado


def _hay_algo_que_guardar(previo: Any, resultado: ResultadoTurno) -> bool:
    """¿Cambió algo del plan en este turno?

    No basta con mirar la versión. Reportar una sesión como `normal` marca
    `completada` sin crear una v2, y eso es un hecho que debe persistir. Antes
    se comparaba solo la versión y esos registros se perdían en silencio.
    """
    if resultado.plan is None:
        return False
    if previo is None:
        return True
    return resultado.plan != previo
