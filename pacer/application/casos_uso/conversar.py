"""Bucle de conversación con herramientas.

El modelo pide herramientas, el código las valida y ejecuta, y el resultado
vuelve al modelo para que redacte la respuesta hablada. El bucle tiene tope:
un modelo que insiste en llamar herramientas no puede colgar el turno.
"""

from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Literal

from pacer.application.casos_uso.crear_plan import crear_plan
from pacer.application.contexto.fechas import interpretar_fecha
from pacer.application.herramientas.despachador import despachar
from pacer.application.herramientas.esquemas import catalogo_para_bedrock
from pacer.domain.entidades.carrera import Carrera
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.entidades.plan import Plan, Sensacion
from pacer.domain.puertos.llm import LlamadaHerramienta, PuertoLLM
from pacer.domain.reglas.duracion import PlanImposible
from pacer.domain.servicios.ajustador import ajustar
from pacer.domain.servicios.categoria import categoria_de_km, como_se_entrena
from pacer.domain.servicios.registro import registrar
from pacer.domain.servicios.resolutor import resolver_sesion

MAX_VUELTAS = 4

TEXTO_DE_RESPALDO = "Perdón, se me enredó eso. ¿Me lo repites?"

COMO_DECIR_QUE_NO = (
    "Explica la razón con tus palabras, como entrenador, y ofrece SOLO las "
    "alternativas de la lista. NUNCA digas que el sistema no te deja: la "
    "decisión es tuya y tienes el motivo."
)

# Herramientas cuyo resultado no le dice nada nuevo al modelo: confirman que se
# guardó un dato que él mismo acaba de mandar. Si ya escribió texto en el mismo
# turno, ese texto sirve y el segundo viaje al modelo es tiempo regalado.
#
# `generar_plan` y `registrar_sesion` NO entran acá: sus resultados traen
# números y motivos que el modelo no puede haber sabido antes de llamarlas.
#
# `apuntar_carrera` SÍ aporta: devuelve con qué plan se entrena esa distancia,
# y eso el modelo no lo sabe. Sin ese viaje de vuelta acabó diciendo que no
# podía hacer planes de 5 km justo después de aceptar una carrera de 3.5.
SIN_NADA_NUEVO_QUE_CONTAR = frozenset({"actualizar_perfil"})

SENSACIONES_VALIDAS: tuple[Sensacion, ...] = (
    "facil",
    "normal",
    "pesada",
    "muy_dura",
    "con_dolor",
)

CAMPOS_DE_PERFIL = (
    "nombre",
    "objetivo",
    "nivel",
    "dias_disponibles",
    "km_semana",
    "dolor_actual",
)


@dataclass(frozen=True)
class AccionAgenda:
    """Un cambio en la agenda que quien llama tiene que persistir.

    El bucle de conversación es puro: decide QUÉ pasa con la agenda pero no
    toca la base. Devolver la intención en vez de ejecutarla es lo que permite
    probar todo esto sin levantar nada.
    """

    tipo: Literal["mover", "quitar"]
    carrera_id: int
    nueva_fecha: date | None = None


@dataclass(frozen=True)
class ResultadoTurno:
    texto: str
    perfil: Perfil
    mensajes: list[dict[str, Any]]
    vueltas: int
    herramientas_usadas: tuple[str, ...]
    plan: Plan | None = None
    corto_por_limite: bool = False
    carreras_nuevas: tuple[Carrera, ...] = ()
    """Las que se apuntaron en este turno. Quien llama las persiste."""

    acciones_agenda: tuple[AccionAgenda, ...] = ()
    """Movimientos y bajas de la agenda. Quien llama las aplica."""


def procesar_turno(
    llm: PuertoLLM,
    sistema: str,
    mensajes: list[dict[str, Any]],
    perfil: Perfil,
    *,
    hoy: date,
    plan: Plan | None = None,
    carreras: tuple[Carrera, ...] = (),
    max_vueltas: int = MAX_VUELTAS,
) -> ResultadoTurno:
    """Corre el ciclo pedir-ejecutar-responder hasta que el modelo cierre el turno."""
    historial = list(mensajes)
    usadas: list[str] = []
    apuntadas: list[Carrera] = []
    acciones: list[AccionAgenda] = []
    catalogo = catalogo_para_bedrock()

    for vuelta in range(1, max_vueltas + 1):
        respuesta = llm.conversar(sistema, historial, catalogo)

        if not respuesta.llamadas:
            return ResultadoTurno(
                texto=respuesta.texto,
                perfil=perfil,
                mensajes=historial,
                vueltas=vuelta,
                herramientas_usadas=tuple(usadas),
                plan=plan,
                carreras_nuevas=tuple(apuntadas),
                acciones_agenda=tuple(acciones),
            )

        historial.append(respuesta.mensaje)
        resultados = []

        for llamada in respuesta.llamadas:
            usadas.append(llamada.nombre)
            resultado = despachar(llamada.nombre, llamada.entrada, perfil)

            if "error" not in resultado:
                if llamada.nombre == "actualizar_perfil":
                    perfil, problema = _aplicar_actualizacion(perfil, llamada.entrada)
                    if problema is not None:
                        resultado = problema
                elif llamada.nombre == "generar_plan":
                    plan, resultado = _generar(perfil, hoy, previo=plan)
                elif llamada.nombre == "registrar_sesion":
                    plan, resultado = _registrar_y_ajustar(plan, llamada.entrada, hoy)
                elif llamada.nombre == "apuntar_carrera":
                    nueva, resultado = _apuntar_carrera(llamada.entrada)
                    if nueva is not None:
                        apuntadas.append(nueva)
                elif llamada.nombre in ACCIONES_DE_AGENDA:
                    perfil, accion, resultado = _tocar_agenda(
                        llamada.nombre, llamada.entrada, carreras, perfil
                    )
                    if accion is not None:
                        acciones.append(accion)

            resultados.append((llamada, resultado))

        historial.append(_mensaje_de_resultados(resultados))

        if _ya_dijo_todo(respuesta.texto, resultados):
            return ResultadoTurno(
                texto=respuesta.texto,
                perfil=perfil,
                mensajes=historial,
                vueltas=vuelta,
                herramientas_usadas=tuple(usadas),
                plan=plan,
                carreras_nuevas=tuple(apuntadas),
                acciones_agenda=tuple(acciones),
            )

    # Nunca se devuelve texto vacío: desde el teléfono, silencio y error se ven
    # igual, y el usuario acaba repitiendo sin saber si lo escucharon.
    return ResultadoTurno(
        texto=TEXTO_DE_RESPALDO,
        perfil=perfil,
        mensajes=historial,
        vueltas=max_vueltas,
        herramientas_usadas=tuple(usadas),
        plan=plan,
        corto_por_limite=True,
        carreras_nuevas=tuple(apuntadas),
        acciones_agenda=tuple(acciones),
    )


ACCIONES_DE_AGENDA = frozenset(
    {"mover_carrera", "quitar_carrera", "elegir_carrera_objetivo"}
)


def _tocar_agenda(
    herramienta: str,
    entrada: dict[str, Any],
    carreras: tuple[Carrera, ...],
    perfil: Perfil,
) -> tuple[Perfil, AccionAgenda | None, dict[str, Any]]:
    """Mover, quitar o elegir objetivo. Mantiene el perfil en sincronía.

    El corredor pospone una carrera y hasta ahora el coach apuntaba una nueva
    dejando la vieja: no era terquedad del modelo, es que no tenía con qué
    moverla. Si la que se toca es la objetivo, la fecha del plan se mueve o se
    limpia con ella, porque contar los días hacia una carrera borrada es peor
    que no contar nada.
    """
    objetivo = next(
        (c for c in carreras if c.id == entrada.get("carrera_id")), None
    )
    if objetivo is None:
        return perfil, None, {
            "error": "carrera_no_encontrada",
            "como_seguir": "Dile cuáles tiene apuntadas y pregúntale a cuál se refiere.",
        }

    es_la_objetivo = (
        perfil.fecha_carrera is not None and objetivo.fecha == perfil.fecha_carrera
    )

    if herramienta == "quitar_carrera":
        if es_la_objetivo:
            perfil = replace(perfil, fecha_carrera=None)
        return (
            perfil,
            AccionAgenda(tipo="quitar", carrera_id=objetivo.id or 0),
            {"ok": True, "quitada": objetivo.nombre, "era_la_objetivo": es_la_objetivo},
        )

    if herramienta == "mover_carrera":
        nueva = interpretar_fecha(str(entrada.get("nueva_fecha", "")))
        if nueva is None:
            return perfil, None, {
                "error": "fecha_no_entendida",
                "como_seguir": "Pregúntale el día, el mes y el año.",
            }
        if es_la_objetivo:
            perfil = replace(perfil, fecha_carrera=nueva)
        return (
            perfil,
            AccionAgenda(tipo="mover", carrera_id=objetivo.id or 0, nueva_fecha=nueva),
            {"ok": True, "movida": objetivo.nombre, "nueva_fecha": nueva.isoformat()},
        )

    # elegir_carrera_objetivo
    if objetivo.distancia_km is None:
        return perfil, None, {
            "error": "sin_distancia",
            "como_seguir": "Pregúntale de cuántos kilómetros es esa carrera.",
        }

    categoria = categoria_de_km(objetivo.distancia_km)
    if categoria is None:
        return perfil, None, {
            "error": "distancia_no_cubierta",
            "razon_para_explicar": como_se_entrena(objetivo.distancia_km),
        }

    perfil = replace(perfil, objetivo=categoria, fecha_carrera=objetivo.fecha)
    return perfil, None, {
        "ok": True,
        "carrera": objetivo.nombre,
        "objetivo": categoria,
        "fecha_carrera": objetivo.fecha.isoformat(),
    }


def _apuntar_carrera(entrada: dict[str, Any]) -> tuple[Carrera | None, dict[str, Any]]:
    """Convierte lo que dijo el modelo en una carrera de la agenda.

    Devuelve un error explícito cuando la fecha no se entiende. Tragarse el
    fallo y guardar sin fecha haría que el corredor crea que quedó apuntada.
    """
    fecha = interpretar_fecha(str(entrada.get("fecha", "")))
    if fecha is None:
        return None, {
            "error": "fecha_no_entendida",
            "como_seguir": "Pregúntale el día, el mes y el año de la carrera.",
        }

    nombre = str(entrada.get("nombre", "")).strip()
    if not nombre:
        return None, {"error": "falta_el_nombre"}

    km = entrada.get("distancia_km")
    carrera = Carrera(
        fecha=fecha,
        nombre=nombre,
        # Un decimal: las carreras se miden así. Nadie corre 12.347 km, y ese
        # ruido decimal se cuela en la tarjeta y en lo que dice el coach.
        distancia_km=round(float(km), 1) if km else None,
        nota=str(entrada.get("nota") or ""),
    )

    resultado: dict[str, Any] = {
        "ok": True,
        "fecha": fecha.isoformat(),
        "nombre": nombre,
    }
    if carrera.distancia_km is not None:
        # Se le devuelve con qué plan se entrena para que no tenga que
        # deducirlo. Deduciéndolo es como acabó diciendo que no podía hacer
        # planes de 5 km justo después de reconocer una carrera de 3.5.
        resultado["distancia_km"] = carrera.distancia_km
        resultado["como_se_entrena"] = como_se_entrena(carrera.distancia_km)

    return carrera, resultado


def _generar(
    perfil: Perfil, hoy: date, previo: Plan | None = None
) -> tuple[Plan | None, dict[str, Any]]:
    """Genera el plan y devuelve un RESUMEN al modelo, nunca el plan entero.

    Mandarle las semanas completas gastaría tokens sin darle nada que decidir:
    el modelo explica el plan, no lo lee sesión por sesión.
    """
    try:
        nuevo = crear_plan(perfil, hoy=hoy)
    except PlanImposible as rechazo:
        return None, _no_hay_plan(rechazo)

    # El generador siempre devuelve v1, pero `version_activa` toma la MAYOR: un
    # plan nuevo tiene que quedar por encima de su propia historia o la app
    # seguiría enseñando el plan de la carrera que el corredor abandonó.
    if previo is not None:
        nuevo = replace(
            nuevo,
            version=previo.version + 1,
            motivo_cambio="Plan nuevo para tu carrera objetivo.",
        )

    de_carga = [semana for semana in nuevo.semanas if not semana.es_descarga]
    arranque = nuevo.semanas[0].sesiones[0].fecha

    resultado: dict[str, Any] = {
        "ok": True,
        "semanas": len(nuevo.semanas),
        "km_primera_semana": nuevo.semanas[0].km_total,
        "km_pico": max(semana.km_total for semana in de_carga),
        # Siempre, aunque sea hoy: sin este dato el modelo preguntaba "¿cuándo
        # quieres que empiece?" por algo que ya estaba decidido.
        "empieza_el": arranque.isoformat(),
    }

    # Cuando la carrera está muy lejos el plan no empieza hoy: empieza cuando
    # toca. Decírselo evita que el corredor abra la app mañana y no vea nada.
    if arranque > hoy:
        resultado["que_hacer_mientras"] = (
            "El plan YA ESTÁ y el corredor puede verlo entero en la app desde "
            "ahora; lo que empieza en esa fecha es el entrenamiento. NO le "
            "digas que el plan aparecerá después. Dile que hasta entonces "
            "mantenga lo que ya hace, sin subir carga."
        )

    return nuevo, resultado


def _no_hay_plan(rechazo: PlanImposible) -> dict[str, Any]:
    """Lo que se le devuelve al modelo cuando la meta no admite un plan seguro.

    Las alternativas se derivan del rechazo REAL. Antes eran una lista fija que
    incluía "bajar la distancia" siempre, y hubo un caso donde eso empeoraba el
    problema: el modelo mezcló los números y dijo que 30 semanas no alcanzaban
    para un mínimo de 10.
    """
    if rechazo.minimo is None:
        # No es cuestión de tiempo: falta base. Mover la fecha no arregla nada.
        return {
            "error": "meta_inalcanzable",
            "motivo": rechazo.motivo,
            "razon_para_explicar": rechazo.razon,
            "alternativas": [
                "empezar por una distancia más corta y construir base primero"
            ],
            "no_ofrezcas": "mover la fecha de la carrera: el problema no es el tiempo",
            "como_decirlo": COMO_DECIR_QUE_NO,
        }

    return {
        "error": "faltan_semanas",
        "motivo": rechazo.motivo,
        "razon_para_explicar": rechazo.razon,
        "semanas_minimas": rechazo.minimo,
        "alternativas": [
            "mover la carrera objetivo a una fecha más adelante",
            "bajar la distancia de la meta",
        ],
        "como_decirlo": COMO_DECIR_QUE_NO,
    }


def _ya_dijo_todo(
    texto: str, resultados: list[tuple[LlamadaHerramienta, dict[str, Any]]]
) -> bool:
    """¿El texto que ya escribió el modelo sirve como respuesta final?

    Sirve cuando escribió algo Y todas las herramientas de la vuelta fueron de
    las que no aportan información nueva Y ninguna falló. Un error sí hay que
    devolvérselo: tiene que enterarse y corregir.
    """
    if not texto.strip():
        return False

    return all(
        llamada.nombre in SIN_NADA_NUEVO_QUE_CONTAR and "error" not in resultado
        for llamada, resultado in resultados
    )


def _registrar_y_ajustar(
    plan: Plan | None, entrada: dict[str, Any], hoy: date
) -> tuple[Plan | None, dict[str, Any]]:
    """Resuelve a qué sesión se refiere, la registra, y ajusta si hace falta.

    Este es el cuarto paso del ciclo: reportas cómo te fue y el plan reacciona.
    """
    if plan is None:
        return None, {"error": "sin_plan", "explicacion": "todavía no hay plan"}

    resolucion = resolver_sesion(plan, str(entrada.get("pista_temporal", "")), hoy)

    if resolucion.sesion is None:
        if resolucion.candidatas:
            return plan, {
                "error": "sesion_ambigua",
                "candidatas": [
                    {"fecha": s.fecha.isoformat(), "tipo": s.tipo, "km": s.km}
                    for s in resolucion.candidatas
                ],
            }
        return plan, {"error": "sesion_no_encontrada"}

    objetivo = resolucion.sesion
    cruda = entrada.get("sensacion")
    sensacion = _sensacion(cruda)

    # Una sensación que no reconocemos NO se degrada a "normal": eso perdería
    # en silencio un reporte de dolor. Se devuelve el catálogo y el coach pregunta.
    if sensacion is None:
        return plan, {
            "error": "sensacion_invalida",
            "recibido": cruda,
            "validas": list(SENSACIONES_VALIDAS),
        }

    km = float(entrada.get("km") or objetivo.km)

    registrado = registrar(plan, objetivo, km=km, sensacion=sensacion)
    reporte = replace(objetivo, km=km, completada=True, sensacion=sensacion)
    ajustado = ajustar(registrado, reporte)

    cambio = ajustado.version > registrado.version
    return ajustado, {
        "ok": True,
        "fecha": objetivo.fecha.isoformat(),
        "km": km,
        "sensacion": sensacion,
        "plan_ajustado": cambio,
        "motivo_cambio": ajustado.motivo_cambio,
        "version": ajustado.version,
    }


def _sensacion(valor: Any) -> Sensacion | None:
    """Valida contra el catálogo. Ausencia significa 'no comentó', y eso sí es normal."""
    if valor is None:
        return "normal"
    for opcion in SENSACIONES_VALIDAS:
        if valor == opcion:
            return opcion
    return None


def _mensaje_de_resultados(
    resultados: list[tuple[LlamadaHerramienta, dict[str, Any]]],
) -> dict[str, Any]:
    """Bedrock espera TODOS los toolResult de la vuelta en un solo mensaje."""
    return {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": llamada.id,
                    "content": [{"json": resultado}],
                }
            }
            for llamada, resultado in resultados
        ],
    }


def _aplicar_actualizacion(
    perfil: Perfil, entrada: dict[str, Any]
) -> tuple[Perfil, dict[str, Any] | None]:
    """Escribe solo los campos que el modelo mencionó; el resto no se toca.

    Si la fecha no se entiende se DEVUELVE el problema en vez de ignorarlo.
    Tragárselo dejaba al modelo probando formatos a ciegas —el guardarrail solo
    le decía "falta la fecha", nunca "la fecha que mandaste no se entiende"— y
    la conversación entraba en bucle.
    """
    cambios: dict[str, Any] = {
        campo: entrada[campo]
        for campo in CAMPOS_DE_PERFIL
        if entrada.get(campo) is not None
    }

    fecha_cruda = entrada.get("fecha_carrera")
    if fecha_cruda:
        fecha = interpretar_fecha(str(fecha_cruda))
        if fecha is None:
            return replace(perfil, **cambios), {
                "error": "fecha_no_entendida",
                "recibido": fecha_cruda,
                "formato_esperado": "AAAA-MM-DD",
                "explicacion": (
                    "Pregunta el día, el mes y el año, y mándalos como "
                    "2026-12-12. No se lo preguntes al corredor en ese formato."
                ),
            }
        cambios["fecha_carrera"] = fecha

    return replace(perfil, **cambios), None
