"""Las carreras de la agenda: apuntarlas hablando y que el coach las vea."""

import json
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
        self.recibidos: list[list[dict[str, Any]]] = []

    def conversar(
        self, sistema: str, mensajes: list[dict[str, Any]], herramientas: dict[str, Any]
    ) -> RespuestaLLM:
        self.recibidos.append([dict(m) for m in mensajes])
        return self._respuestas.pop(0)


def linea_de_carreras(bloque: str) -> str:
    """Solo la línea de carreras. El resto del bloque tiene sus propios ' · '."""
    return next(l for l in bloque.splitlines() if l.startswith("CARRERAS APUNTADAS:"))


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
            nombre="Maratón CDMX", fecha="2026-12-06", distancia_km=42.2, nota="Meta 4h"
        ),
        RespuestaLLM(
            texto="Listo, ya está apuntada.",
            llamadas=(),
            mensaje={"role": "assistant", "content": [{"text": "Listo."}]},
        ),
    )

    resultado = procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY)

    assert len(resultado.carreras_nuevas) == 1
    apuntada = resultado.carreras_nuevas[0]
    assert apuntada.nombre == "Maratón CDMX"
    assert apuntada.fecha == date(2026, 12, 6)
    assert apuntada.distancia_km == 42.2
    assert apuntada.nota == "Meta 4h"


def test_acepta_la_fecha_como_la_diria_una_persona() -> None:
    llm = LLMDeMentira(
        pide_apuntar(nombre="Carrera del pueblo", fecha="6 de diciembre de 2026"),
        RespuestaLLM(
            texto="Apuntada.",
            llamadas=(),
            mensaje={"role": "assistant", "content": [{"text": "Apuntada."}]},
        ),
    )

    resultado = procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY)

    assert resultado.carreras_nuevas[0].fecha == date(2026, 12, 6)


def test_al_apuntar_le_devuelve_al_modelo_con_que_plan_se_entrena() -> None:
    """El bug reportado: apuntó una carrera de 3.5 km y a renglón seguido dijo
    que no podía hacer planes de 5 km. No lo sabía porque nadie se lo dijo."""
    capturados: list[dict[str, Any]] = []

    class Espia(LLMDeMentira):
        def conversar(self, sistema, mensajes, herramientas):  # type: ignore[no-untyped-def]
            capturados.append({"mensajes": list(mensajes)})
            return super().conversar(sistema, mensajes, herramientas)

    llm = Espia(
        pide_apuntar(nombre="Carrera azul", fecha="2026-09-12", distancia_km=3.5),
        RespuestaLLM(
            texto="La Carrera azul de 3.5 km la preparamos como un 5K.",
            llamadas=(),
            mensaje={"role": "assistant", "content": [{"text": "ok"}]},
        ),
    )

    procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY)

    devuelto = json.dumps(capturados[-1]["mensajes"], default=str)
    assert "se entrena como un 5K" in devuelto


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


def test_al_pausar_se_le_dice_la_vuelta_REAL_no_una_sesion_anterior() -> None:
    """El coach anunció "vuelves el lunes 24 con 5.3 km" cuando la vuelta real
    era el martes 25 con 6.6. Le llegaba una sesión ANTERIOR al parón como si
    fuera la de vuelta, y con ese dato absurdo se inventó una fecha creíble."""
    from datetime import date as _date

    from pacer.domain.entidades.plan import Plan, Semana, Sesion

    plan = Plan(
        version=1,
        semanas=(
            Semana(
                numero=1,
                sesiones=(
                    Sesion(fecha=_date(2026, 8, 20), tipo="largo", km=15.4),
                    Sesion(fecha=_date(2026, 8, 22), tipo="facil", km=7.2),
                    Sesion(fecha=_date(2026, 8, 29), tipo="facil", km=8.0),
                ),
            ),
        ),
    )
    llm = LLMDeMentira(
        RespuestaLLM(
            texto="",
            llamadas=(
                LlamadaHerramienta(
                    id="t1",
                    nombre="pausar_entrenamiento",
                    entrada={"desde": "2026-08-21", "hasta": "2026-08-27"},
                ),
            ),
            mensaje={"role": "assistant", "content": []},
        ),
        RespuestaLLM(texto="Listo.", llamadas=(), mensaje={"role": "assistant", "content": []}),
    )

    procesar_turno(llm, "sistema", [], Perfil(), hoy=HOY, plan=plan)

    devuelto = json.dumps(llm.recibidos[-1], ensure_ascii=False, default=str)
    assert "29 de agosto" in devuelto
    assert "20 de agosto" not in devuelto


def test_el_bloque_de_estado_lista_las_carreras_con_los_dias_ya_contados() -> None:
    """El modelo no resta fechas: se equivoca, y una cuenta regresiva mal dicha
    destruye la confianza más rápido que cualquier otra cosa."""
    carreras = (
        Carrera(fecha=date(2026, 9, 5), nombre="Medio de Toluca", distancia_km=21.1),
    )

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    assert "Medio de Toluca" in bloque
    assert "21.1 km" in bloque
    assert "faltan 16 días" in bloque


def test_el_bloque_dice_con_que_plan_se_entrena_cada_distancia() -> None:
    """Sin esto el modelo tiene que deducirlo, y deduciendo se contradijo."""
    carreras = (Carrera(fecha=date(2026, 9, 12), nombre="Carrera azul", distancia_km=3.5),)

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    assert "se entrena como un 5K" in bloque
    assert 'objetivo="5k"' in bloque


def test_el_bloque_marca_cual_es_la_carrera_objetivo() -> None:
    """Con varias apuntadas y ninguna marcada, el coach preguntaba en círculos."""
    carreras = (
        Carrera(fecha=date(2026, 9, 12), nombre="Carrera azul", distancia_km=3.5),
        Carrera(fecha=date(2026, 12, 6), nombre="Maratón CDMX", distancia_km=42.2),
    )

    bloque = construir_bloque(
        hoy=HOY, carreras=carreras, fecha_carrera=date(2026, 9, 12)
    )

    azul, maraton = linea_de_carreras(bloque).split(" · ")
    assert "ES LA CARRERA OBJETIVO" in azul
    assert "ES LA CARRERA OBJETIVO" not in maraton


def test_si_ninguna_es_la_objetivo_le_dice_que_pregunte() -> None:
    carreras = (
        Carrera(fecha=date(2026, 9, 12), nombre="Carrera azul", distancia_km=3.5),
        Carrera(fecha=date(2026, 12, 6), nombre="Maratón CDMX", distancia_km=42.2),
    )

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    assert "NINGUNA ES TODAVÍA LA OBJETIVO" in bloque


def test_una_distancia_que_no_se_cubre_se_dice_en_el_bloque() -> None:
    """Un 100k no se entrena con el plan de maratón. El coach tiene que poder
    decirlo sin inventarse el motivo."""
    carreras = (Carrera(fecha=date(2026, 9, 5), nombre="Ultra", distancia_km=100.0),)

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    entrada = linea_de_carreras(bloque)
    assert "no la cubro" in entrada
    # No se le ofrece un objetivo que guardar: no hay plan para esa distancia.
    assert "objetivo=" not in entrada


def test_el_coach_ve_las_carreras_aunque_todavia_no_haya_plan() -> None:
    """Apuntar algo en el calendario y que el coach no se entere se siente como
    hablar con dos aplicaciones distintas."""
    carreras = (Carrera(fecha=date(2026, 9, 5), nombre="La del trabajo"),)

    bloque = construir_bloque(plan=None, hoy=HOY, carreras=carreras)

    assert "PLAN: todavía no hay" in bloque
    assert "La del trabajo" in bloque


def test_las_carreras_que_ya_pasaron_no_ensucian_el_bloque() -> None:
    carreras = (Carrera(fecha=date(2026, 1, 10), nombre="Vieja"),)

    bloque = construir_bloque(hoy=HOY, carreras=carreras)

    assert "Vieja" not in bloque
    assert "ninguna próxima" in bloque
