"""El coach manda sobre la agenda, no solo escribe en ella.

Reportado: recomendó posponer la carrera, apuntó la fecha nueva y dejó la
vieja ahí. No era terquedad del modelo — no tenía con qué moverla ni con qué
borrarla. Se le dieron esas manos.
"""

from datetime import date
from typing import Any

from pacer.application.casos_uso.conversar import procesar_turno
from pacer.domain.entidades.carrera import Carrera
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM

HOY = date(2026, 8, 20)

AZUL = Carrera(id=7, fecha=date(2026, 9, 12), nombre="Carrera azul", distancia_km=3.5)
MARZO = Carrera(id=9, fecha=date(2027, 3, 20), nombre="De marzo", distancia_km=10.0)
AGENDA = (AZUL, MARZO)


class LLMDeMentira:
    def __init__(self, *respuestas: RespuestaLLM) -> None:
        self._respuestas = list(respuestas)

    def conversar(self, sistema: str, mensajes: Any, herramientas: Any) -> RespuestaLLM:
        return self._respuestas.pop(0)


def pide(nombre: str, **entrada: Any) -> RespuestaLLM:
    return RespuestaLLM(
        texto="",
        llamadas=(LlamadaHerramienta(id="t1", nombre=nombre, entrada=entrada),),
        mensaje={"role": "assistant", "content": []},
    )


def cierra(texto: str = "Listo.") -> RespuestaLLM:
    return RespuestaLLM(
        texto=texto, llamadas=(), mensaje={"role": "assistant", "content": []}
    )


def correr(*respuestas: RespuestaLLM, perfil: Perfil | None = None):  # type: ignore[no-untyped-def]
    return procesar_turno(
        LLMDeMentira(*respuestas),
        "sistema",
        [],
        perfil or Perfil(),
        hoy=HOY,
        carreras=AGENDA,
    )


# --- mover ---------------------------------------------------------------


def test_puede_mover_una_carrera_de_fecha() -> None:
    resultado = correr(pide("mover_carrera", carrera_id=7, nueva_fecha="2026-10-04"), cierra())

    assert len(resultado.acciones_agenda) == 1
    accion = resultado.acciones_agenda[0]
    assert accion.tipo == "mover"
    assert accion.carrera_id == 7
    assert accion.nueva_fecha == date(2026, 10, 4)


def test_mover_la_carrera_objetivo_mueve_tambien_la_fecha_del_plan() -> None:
    """Si no, el plan sigue apuntando al día viejo y todo se desincroniza."""
    perfil = Perfil(objetivo="5k", fecha_carrera=AZUL.fecha)

    resultado = correr(
        pide("mover_carrera", carrera_id=7, nueva_fecha="2026-10-04"),
        cierra(),
        perfil=perfil,
    )

    assert resultado.perfil.fecha_carrera == date(2026, 10, 4)


def test_mover_otra_carrera_no_toca_la_fecha_del_plan() -> None:
    perfil = Perfil(objetivo="5k", fecha_carrera=AZUL.fecha)

    resultado = correr(
        pide("mover_carrera", carrera_id=9, nueva_fecha="2027-04-10"),
        cierra(),
        perfil=perfil,
    )

    assert resultado.perfil.fecha_carrera == AZUL.fecha


def test_no_mueve_una_carrera_que_no_existe() -> None:
    resultado = correr(pide("mover_carrera", carrera_id=99, nueva_fecha="2026-10-04"), cierra())

    assert resultado.acciones_agenda == ()


def test_una_fecha_nueva_que_no_se_entiende_no_mueve_nada() -> None:
    resultado = correr(pide("mover_carrera", carrera_id=7, nueva_fecha="más adelante"), cierra())

    assert resultado.acciones_agenda == ()


# --- quitar --------------------------------------------------------------


def test_puede_quitar_una_carrera() -> None:
    resultado = correr(pide("quitar_carrera", carrera_id=7), cierra())

    assert resultado.acciones_agenda[0].tipo == "quitar"
    assert resultado.acciones_agenda[0].carrera_id == 7


def test_quitar_la_carrera_objetivo_deja_el_plan_sin_fecha() -> None:
    """Quedarse con la fecha de una carrera borrada es peor que no tener fecha:
    el coach seguiría contando los días para algo que ya no existe."""
    perfil = Perfil(objetivo="5k", fecha_carrera=AZUL.fecha)

    resultado = correr(pide("quitar_carrera", carrera_id=7), cierra(), perfil=perfil)

    assert resultado.perfil.fecha_carrera is None


# --- elegir la objetivo --------------------------------------------------


def test_elegir_la_objetivo_escribe_meta_y_fecha_de_una_sola_vez() -> None:
    """Antes había que copiar el objetivo y la fecha a mano en actualizar_perfil,
    que es justo donde el modelo se equivoca de dígito."""
    resultado = correr(pide("elegir_carrera_objetivo", carrera_id=9), cierra())

    assert resultado.perfil.objetivo == "10k"
    assert resultado.perfil.fecha_carrera == date(2027, 3, 20)


def test_no_se_puede_entrenar_para_una_distancia_que_no_se_cubre() -> None:
    agenda = (Carrera(id=3, fecha=date(2026, 12, 1), nombre="Ultra", distancia_km=100.0),)

    resultado = procesar_turno(
        LLMDeMentira(pide("elegir_carrera_objetivo", carrera_id=3), cierra()),
        "sistema",
        [],
        Perfil(),
        hoy=HOY,
        carreras=agenda,
    )

    assert resultado.perfil.objetivo is None


def test_una_carrera_sin_distancia_no_puede_ser_objetivo() -> None:
    agenda = (Carrera(id=4, fecha=date(2026, 12, 1), nombre="Sin medir"),)

    resultado = procesar_turno(
        LLMDeMentira(pide("elegir_carrera_objetivo", carrera_id=4), cierra()),
        "sistema",
        [],
        Perfil(),
        hoy=HOY,
        carreras=agenda,
    )

    assert resultado.perfil.objetivo is None
