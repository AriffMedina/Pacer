"""El bucle multi-turno se prueba con un LLM falso: sin red, determinista."""

from datetime import date
from typing import Any

from pacer.application.casos_uso.conversar import procesar_turno
from pacer.application.casos_uso.crear_plan import crear_plan
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM

HOY = date(2026, 8, 16)

PERFIL_COMPLETO = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),
)


class LLMFalso:
    """Devuelve respuestas preparadas, una por vuelta, y registra lo que recibió."""

    def __init__(self, *respuestas: RespuestaLLM) -> None:
        self._respuestas = list(respuestas)
        self.recibidos: list[list[dict[str, Any]]] = []

    def conversar(
        self,
        sistema: str,
        mensajes: list[dict[str, Any]],
        herramientas: dict[str, Any],
    ) -> RespuestaLLM:
        self.recibidos.append([dict(m) for m in mensajes])
        return self._respuestas.pop(0)


def solo_texto(texto: str) -> RespuestaLLM:
    return RespuestaLLM(texto=texto, llamadas=(), mensaje={"role": "assistant"})


def con_llamada(nombre: str, entrada: dict[str, Any]) -> RespuestaLLM:
    return RespuestaLLM(
        texto="",
        llamadas=(LlamadaHerramienta(id="tu_1", nombre=nombre, entrada=entrada),),
        mensaje={"role": "assistant"},
    )


def mensaje_usuario(texto: str) -> dict[str, Any]:
    return {"role": "user", "content": [{"text": texto}]}


def test_sin_herramientas_devuelve_el_texto_en_una_vuelta() -> None:
    llm = LLMFalso(solo_texto("¿Para qué carrera te preparas?"))

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("hola")], Perfil(), hoy=HOY
    )

    assert resultado.vueltas == 1
    assert "carrera" in resultado.texto


def test_ejecuta_la_herramienta_y_vuelve_a_preguntarle_al_modelo() -> None:
    llm = LLMFalso(
        con_llamada("actualizar_perfil", {"objetivo": "21k"}),
        solo_texto("Listo, lo anoté."),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("quiero un 21k")], Perfil(), hoy=HOY
    )

    assert resultado.vueltas == 2
    assert resultado.herramientas_usadas == ("actualizar_perfil",)
    assert "anoté" in resultado.texto


def test_la_actualizacion_de_perfil_se_aplica() -> None:
    llm = LLMFalso(
        con_llamada(
            "actualizar_perfil",
            {"objetivo": "21k", "km_semana": 25, "fecha_carrera": "2026-11-01"},
        ),
        solo_texto("Anotado."),
    )

    resultado = procesar_turno(llm, "sistema", [mensaje_usuario("...")], Perfil(), hoy=HOY)

    assert resultado.perfil.objetivo == "21k"
    assert resultado.perfil.km_semana == 25
    assert resultado.perfil.fecha_carrera == date(2026, 11, 1)


def test_los_campos_no_mencionados_no_se_pisan() -> None:
    previo = Perfil(objetivo="21k", nivel="intermedio")
    llm = LLMFalso(
        con_llamada("actualizar_perfil", {"km_semana": 30}),
        solo_texto("ok"),
    )

    resultado = procesar_turno(llm, "sistema", [mensaje_usuario("...")], previo, hoy=HOY)

    assert resultado.perfil.nivel == "intermedio"
    assert resultado.perfil.km_semana == 30


def test_el_resultado_de_la_herramienta_se_le_devuelve_al_modelo() -> None:
    llm = LLMFalso(
        con_llamada("generar_plan", {}),
        solo_texto("Me falta la fecha."),
    )

    procesar_turno(llm, "sistema", [mensaje_usuario("hazme el plan")], Perfil(), hoy=HOY)

    ultimos = llm.recibidos[-1]
    bloques = ultimos[-1]["content"]
    assert "toolResult" in bloques[0]
    assert bloques[0]["toolResult"]["content"][0]["json"]["error"] == "faltan_datos"


def test_generar_plan_con_perfil_completo_produce_el_plan() -> None:
    llm = LLMFalso(con_llamada("generar_plan", {}), solo_texto("Aquí está tu plan."))

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("hazme el plan")], PERFIL_COMPLETO, hoy=HOY
    )

    assert resultado.plan is not None
    assert len(resultado.plan.semanas) == 11


def test_al_modelo_se_le_devuelve_un_resumen_no_el_plan_entero() -> None:
    llm = LLMFalso(con_llamada("generar_plan", {}), solo_texto("Listo."))

    procesar_turno(
        llm, "sistema", [mensaje_usuario("hazme el plan")], PERFIL_COMPLETO, hoy=HOY
    )

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["semanas"] == 11
    assert "semanas_detalle" not in devuelto


def test_una_meta_inalcanzable_vuelve_como_alternativas() -> None:
    apurado = Perfil(
        objetivo="maraton",
        nivel="principiante",
        dias_disponibles=4,
        km_semana=32,
        fecha_carrera=date(2026, 10, 1),
    )
    llm = LLMFalso(con_llamada("generar_plan", {}), solo_texto("No alcanza el tiempo."))

    procesar_turno(llm, "sistema", [mensaje_usuario("plan")], apurado, hoy=HOY)

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["error"] == "meta_inalcanzable"
    assert devuelto["semanas_minimas"] == 20
    assert devuelto["alternativas"]


def test_registrar_una_sesion_dura_produce_la_version_dos() -> None:
    plan = crear_plan(PERFIL_COMPLETO, hoy=HOY)
    llm = LLMFalso(
        con_llamada(
            "registrar_sesion",
            {"pista_temporal": "hoy", "km": 5.0, "sensacion": "muy_dura"},
        ),
        solo_texto("Te bajé la carga de la semana."),
    )

    resultado = procesar_turno(
        llm,
        "sistema",
        [mensaje_usuario("hoy corrí y acabé muerto")],
        PERFIL_COMPLETO,
        hoy=HOY,
        plan=plan,
    )

    assert resultado.plan is not None
    assert resultado.plan.version == 2
    assert resultado.plan.motivo_cambio is not None


def test_al_modelo_se_le_da_el_motivo_para_que_lo_explique() -> None:
    plan = crear_plan(PERFIL_COMPLETO, hoy=HOY)
    llm = LLMFalso(
        con_llamada(
            "registrar_sesion",
            {"pista_temporal": "hoy", "km": 5.0, "sensacion": "con_dolor"},
        ),
        solo_texto("..."),
    )

    procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], PERFIL_COMPLETO, hoy=HOY, plan=plan
    )

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["plan_ajustado"] is True
    assert "con_dolor" in devuelto["motivo_cambio"]


def test_una_sesion_normal_no_cambia_la_version() -> None:
    plan = crear_plan(PERFIL_COMPLETO, hoy=HOY)
    llm = LLMFalso(
        con_llamada(
            "registrar_sesion",
            {"pista_temporal": "hoy", "km": 6.0, "sensacion": "normal"},
        ),
        solo_texto("Anotado."),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], PERFIL_COMPLETO, hoy=HOY, plan=plan
    )

    assert resultado.plan is not None
    assert resultado.plan.version == 1


def test_sin_plan_todavia_no_se_puede_registrar() -> None:
    llm = LLMFalso(
        con_llamada("registrar_sesion", {"pista_temporal": "ayer", "km": 5.0}),
        solo_texto("Todavía no tienes plan."),
    )

    procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], PERFIL_COMPLETO, hoy=HOY, plan=None
    )

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["error"] == "sin_plan"


def test_una_pista_ambigua_devuelve_opciones_no_un_error() -> None:
    plan = crear_plan(PERFIL_COMPLETO, hoy=HOY)
    llm = LLMFalso(
        con_llamada(
            "registrar_sesion",
            {"pista_temporal": "el otro día", "km": 5.0, "sensacion": "normal"},
        ),
        solo_texto("¿Cuál de estas?"),
    )

    procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], PERFIL_COMPLETO, hoy=HOY, plan=plan
    )

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["error"] == "sesion_ambigua"
    assert devuelto["candidatas"]


def test_una_sensacion_desconocida_no_se_degrada_a_normal() -> None:
    plan = crear_plan(PERFIL_COMPLETO, hoy=HOY)
    llm = LLMFalso(
        con_llamada(
            "registrar_sesion",
            {"pista_temporal": "hoy", "km": 5.0, "sensacion": "adolorido"},
        ),
        solo_texto("¿Cómo te sentiste exactamente?"),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], PERFIL_COMPLETO, hoy=HOY, plan=plan
    )

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["error"] == "sensacion_invalida"
    assert "con_dolor" in devuelto["validas"]
    assert resultado.plan is not None
    assert resultado.plan.version == 1


def test_el_bucle_no_gira_para_siempre() -> None:
    llm = LLMFalso(*[con_llamada("actualizar_perfil", {}) for _ in range(10)])

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], Perfil(), hoy=HOY, max_vueltas=3
    )

    assert resultado.vueltas == 3
    assert resultado.corto_por_limite
    # Nunca vacío: desde el teléfono, silencio y error se ven igual.
    assert resultado.texto


def test_una_fecha_ilegible_se_reporta_en_vez_de_ignorarse() -> None:
    llm = LLMFalso(
        con_llamada("actualizar_perfil", {"fecha_carrera": "el próximo verano"}),
        solo_texto("¿Qué día exactamente?"),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], Perfil(), hoy=HOY
    )

    devuelto = llm.recibidos[-1][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert devuelto["error"] == "fecha_no_entendida"
    assert devuelto["formato_esperado"] == "AAAA-MM-DD"
    assert resultado.perfil.fecha_carrera is None


def test_una_fecha_dicha_como_habla_la_gente_se_entiende() -> None:
    llm = LLMFalso(
        con_llamada("actualizar_perfil", {"fecha_carrera": "12 de diciembre de 2026"}),
        solo_texto("Anotado."),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], Perfil(), hoy=HOY
    )

    assert resultado.perfil.fecha_carrera == date(2026, 12, 12)


def test_los_demas_campos_se_guardan_aunque_la_fecha_falle() -> None:
    llm = LLMFalso(
        con_llamada(
            "actualizar_perfil",
            {"objetivo": "maraton", "fecha_carrera": "cuando pueda"},
        ),
        solo_texto("¿Cuándo?"),
    )

    resultado = procesar_turno(
        llm, "sistema", [mensaje_usuario("...")], Perfil(), hoy=HOY
    )

    assert resultado.perfil.objetivo == "maraton"
