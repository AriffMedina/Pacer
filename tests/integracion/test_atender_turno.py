"""El turno completo contra una base real: conversación entra, filas salen."""

from datetime import date
from typing import Any

from pacer.application.casos_uso.atender_turno import atender_turno
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

CORREDOR = 1
HOY = date(2026, 8, 16)

PERFIL = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),
)


class LLMFalso:
    def __init__(self, *respuestas: RespuestaLLM) -> None:
        self._respuestas = list(respuestas)

    def conversar(
        self, sistema: str, mensajes: list[dict[str, Any]], herramientas: dict[str, Any]
    ) -> RespuestaLLM:
        return self._respuestas.pop(0)


def con_llamada(nombre: str, entrada: dict[str, Any]) -> RespuestaLLM:
    return RespuestaLLM(
        texto="",
        llamadas=(LlamadaHerramienta(id="tu_1", nombre=nombre, entrada=entrada),),
        mensaje={"role": "assistant"},
    )


def solo_texto(texto: str) -> RespuestaLLM:
    return RespuestaLLM(texto=texto, llamadas=(), mensaje={"role": "assistant"})


def dicho(texto: str) -> list[dict[str, Any]]:
    return [{"role": "user", "content": [{"text": texto}]}]


async def test_generar_el_plan_lo_deja_guardado(
    repositorio: RepositorioPlan,
) -> None:
    llm = LLMFalso(con_llamada("generar_plan", {}), solo_texto("Listo."))

    await atender_turno(
        llm, repositorio, "sistema", dicho("hazme el plan"), PERFIL, CORREDOR, HOY
    )

    guardado = await repositorio.version_activa(CORREDOR)
    assert guardado is not None
    assert guardado.version == 1
    assert len(guardado.semanas) == 11


async def test_el_ajuste_deja_dos_filas_en_la_base(
    repositorio: RepositorioPlan,
) -> None:
    await atender_turno(
        LLMFalso(con_llamada("generar_plan", {}), solo_texto("ok")),
        repositorio,
        "sistema",
        dicho("hazme el plan"),
        PERFIL,
        CORREDOR,
        HOY,
    )

    await atender_turno(
        LLMFalso(
            con_llamada(
                "registrar_sesion",
                {"pista_temporal": "hoy", "km": 5.0, "sensacion": "muy_dura"},
            ),
            solo_texto("Te bajé la carga."),
        ),
        repositorio,
        "sistema",
        dicho("hoy acabé muerto"),
        PERFIL,
        CORREDOR,
        HOY,
    )

    versiones = await repositorio.versiones(CORREDOR)
    assert [p.version for p in versiones] == [1, 2]
    assert versiones[0].motivo_cambio is None
    assert "muy_dura" in str(versiones[1].motivo_cambio)


async def test_una_conversacion_sin_plan_no_escribe_nada(
    repositorio: RepositorioPlan,
) -> None:
    llm = LLMFalso(solo_texto("¿Para qué carrera te preparas?"))

    await atender_turno(
        llm, repositorio, "sistema", dicho("hola"), Perfil(), CORREDOR, HOY
    )

    assert await repositorio.versiones(CORREDOR) == []
