"""Las carreras de la agenda: apuntarlas hablando y que el coach las vea."""

from datetime import date
from typing import Any

from pacer.application.casos_uso.conversar import procesar_turno
from pacer.application.contexto.bloque_estado import construir_bloque
from pacer.domain.entidades.carrera import Carrera, pendientes
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM

HOY = date(2026, 8, 20)


class LLMDeMentira:
    """Contesta la secuencia que se le dé, una respuesta por vuelta."""

    def __init__(self, *respuestas: RespuestaLLM) -> None:
        self._respuestas = list(respuestas)

    def conversar(
        self, sistema: str, mensajes: list[dict[str, Any]], herramientas: dict[str, Any]
    ) -> RespuestaLLM:
        return self._respuestas.pop(0)


def pide_apuntar(**entrada: Any) -> RespuestaLLM:
    return RespuestaLLM(
        texto="Listo, la apunté.",
        llamadas=(
            LlamadaHerramienta(id="t1", nombre="apuntar_carrera", entrada=entrada),
        ),
        mensaje={"role": "assistant", "content": [{"text": "Listo, la apunté."}]},
    )


# --- pendientes ----------------------------------------------------------


def test_solo_devuelve_las_que_no_han_pasado_y_en_orden() -> None:
    carreras = (
        Carrera(fecha=date(2026, 12, 6), nombre="Diciembre"),
        Carrera(fecha=date(2026, 1, 10), nombre="Ya pasó"),
        Carrera(fecha=date(2026, 9, 5), nombre="Septiembre"),
    )

    assert [c.nombre for c in pendientes(carreras, HOY)] == [
        "Septiembre",
        "Diciembre",
    ]


def test_la_carrera_de_hoy_sigue_siendo_pendiente() -> None:
    """El día de la carrera es justo cuando más quieres verla en la agenda."""
    carreras = (Carrera(fecha=HOY, nombre="Es hoy"),)

    assert len(pendientes(carreras, HOY)) == 1


# --- apuntarla hablando --------------------------------------------------


def test_el_coach_apunta_una_carrera_que_le_dictan() -> None:
    llm = LLMDeMentira(
        pide_apuntar(
            nombre="Maratón CDMX", fecha="2026-12-06", distancia="maraton", nota="Meta 4h"
        )
    )

    resultado = procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY)

    assert len(resultado.carreras_nuevas) == 1
    apuntada = resultado.carreras_nuevas[0]
    assert apuntada.nombre == "Maratón CDMX"
    assert apuntada.fecha == date(2026, 12, 6)
    assert apuntada.nota == "Meta 4h"


def test_acepta_la_fecha_como_la_diria_una_persona() -> None:
    llm = LLMDeMentira(pide_apuntar(nombre="Carrera del pueblo", fecha="6 de diciembre de 2026"))

    resultado = procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY)

    assert resultado.carreras_nuevas[0].fecha == date(2026, 12, 6)


def test_una_fecha_que_no_se_entiende_no_apunta_nada() -> None:
    """Tragarse el fallo dejaría al corredor creyendo que quedó apuntada."""
    llm = LLMDeMentira(
        pide_apuntar(nombre="Sin fecha", fecha="el año que viene"),
        RespuestaLLM(
            texto="¿Qué día exactamente?",
            llamadas=(),
            mensaje={"role": "assistant", "content": [{"text": "¿Qué día?"}]},
        ),
    )

    resultado = procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY)

    assert resultado.carreras_nuevas == ()
    assert resultado.texto == "¿Qué día exactamente?"


def test_una_carrera_sin_nombre_no_se_apunta() -> None:
    llm = LLMDeMentira(
        pide_apuntar(nombre="  ", fecha="2026-12-06"),
        RespuestaLLM(
            texto="¿Cómo se llama?",
            llamadas=(),
            mensaje={"role": "assistant", "content": [{"text": "¿Cómo se llama?"}]},
        ),
    )

    assert procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY).carreras_nuevas == ()


# --- que el coach las vea ------------------------------------------------


def test_el_bloque_de_estado_lista_las_carreras_con_los_dias_ya_contados() -> None:
    """El modelo no resta fechas: se equivoca, y una cuenta regresiva mal dicha
    destruye la confianza más rápido que cualquier otra cosa."""
    carreras = (
        Carrera(fecha=date(2026, 9, 5), nombre="Medio de Toluca", distancia="21k"),
    )

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    assert "Medio de Toluca" in bloque
    assert "21k" in bloque
    assert "faltan 16 días" in bloque


def test_el_coach_ve_las_carreras_aunque_todavia_no_haya_plan() -> None:
    """Apuntar algo en el calendario y que el coach no se entere se siente como
    hablar con dos aplicaciones distintas."""
    carreras = (Carrera(fecha=date(2026, 9, 5), nombre="La del trabajo"),)

    bloque = construir_bloque(plan=None, hoy=HOY, carreras=carreras)

    assert "todavía no hay plan" in bloque
    assert "La del trabajo" in bloque


def test_las_carreras_que_ya_pasaron_no_ensucian_el_bloque() -> None:
    carreras = (Carrera(fecha=date(2026, 1, 10), nombre="Vieja"),)

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    assert "Vieja" not in bloque
    assert "ninguna próxima" in bloque
