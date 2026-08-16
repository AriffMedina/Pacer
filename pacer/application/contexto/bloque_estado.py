"""Bloque de estado precalculado que se inyecta al prompt del sistema.

El modelo LEE esto. No calcula fechas, no cuenta semanas y no deduce en qué
punto del plan está el corredor. Evita más alucinaciones que cualquier
instrucción escrita en el prompt.
"""

from datetime import date

from pacer.domain.entidades.carrera import Carrera, pendientes
from pacer.domain.entidades.plan import Plan, Semana, Sesion
from pacer.domain.servicios.categoria import categoria_de_km, como_se_entrena

DIAS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def construir_bloque(
    plan: Plan | None = None,
    *,
    hoy: date,
    fecha_carrera: date | None = None,
    carreras: tuple[Carrera, ...] = (),
) -> str:
    """Arma el bloque de estado que el coach lee antes de responder.

    Funciona sin plan a propósito: las carreras que el corredor apunta en el
    calendario existen desde antes de que haya entrenamiento, y el coach tiene
    que enterarse igual. Si no, agregar algo en la agenda y que el coach no lo
    sepa se siente como hablar con dos aplicaciones distintas.
    """
    lineas = []

    if plan is not None:
        sesiones = sorted(
            (sesion for semana in plan.semanas for sesion in semana.sesiones),
            key=lambda sesion: sesion.fecha,
        )
        semana = _semana_de(plan, hoy)
        numero = semana.numero if semana is not None else len(plan.semanas)

        lineas += [
            _linea_de_encabezado(hoy, numero, len(plan.semanas), fecha_carrera),
            _linea_de_hoy(sesiones, hoy),
            _linea_siguiente(sesiones, hoy),
            _linea_ultima_completada(sesiones),
        ]
    else:
        lineas.append(f"HOY: {_fecha_hablada(hoy)} · todavía no hay plan")

    if carreras:
        lineas.append(_linea_carreras(carreras, hoy, fecha_carrera))

    return "\n".join(lineas)


def _linea_carreras(
    carreras: tuple[Carrera, ...], hoy: date, fecha_carrera: date | None
) -> str:
    """Las carreras apuntadas, ya masticadas para el modelo.

    Van los días que faltan YA CALCULADOS —el modelo restando fechas se
    equivoca, y una cuenta regresiva mal dicha destruye la confianza— y va con
    qué plan se entrena cada distancia, para que no tenga que deducirlo.
    También va CUÁL es la objetivo: sin eso no sabía para cuál estaba
    entrenando y la conversación se volvía un interrogatorio.
    """
    proximas = pendientes(carreras, hoy)
    if not proximas:
        return "CARRERAS APUNTADAS: ninguna próxima"

    partes = []
    for c in proximas:
        trozos = [c.nombre]
        if c.distancia_km is not None:
            trozos.append(f"{c.distancia_km} km, {como_se_entrena(c.distancia_km)}")
            categoria = categoria_de_km(c.distancia_km)
            if categoria:
                trozos.append(f'objetivo="{categoria}"')
        trozos.append(f"el {_fecha_hablada(c.fecha)}")
        trozos.append(f"faltan {(c.fecha - hoy).days} días")
        if fecha_carrera is not None and c.fecha == fecha_carrera:
            trozos.append("ES LA CARRERA OBJETIVO, el plan es para esta")
        partes.append(" (" .join([trozos[0], ", ".join(trozos[1:])]) + ")")

    cabeza = "CARRERAS APUNTADAS: " + " · ".join(partes)

    if fecha_carrera is None or not any(c.fecha == fecha_carrera for c in proximas):
        return (
            cabeza
            + "\nNINGUNA ES TODAVÍA LA OBJETIVO: pregúntale para cuál quiere el "
            'plan y guarda su objetivo="..." y su fecha con actualizar_perfil.'
        )
    return cabeza


def _fecha_hablada(fecha: date) -> str:
    return f"{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month - 1]}"


def _linea_de_encabezado(
    hoy: date, semana: int, total: int, fecha_carrera: date | None
) -> str:
    cabeza = f"HOY: {_fecha_hablada(hoy)} · SEMANA {semana} DE {total}"
    if fecha_carrera is None:
        return cabeza
    return f"{cabeza} · faltan {(fecha_carrera - hoy).days} días"


def _semana_de(plan: Plan, hoy: date) -> Semana | None:
    for semana in plan.semanas:
        if any(sesion.fecha == hoy for sesion in semana.sesiones):
            return semana
    return None


def _linea_de_hoy(sesiones: list[Sesion], hoy: date) -> str:
    de_hoy = next((s for s in sesiones if s.fecha == hoy), None)
    if de_hoy is None:
        return "SESIÓN DE HOY: descanso"
    estado = "completada" if de_hoy.completada else "pendiente"
    return f"SESIÓN DE HOY: {de_hoy.tipo} {de_hoy.km} km ({estado})"


def _linea_siguiente(sesiones: list[Sesion], hoy: date) -> str:
    siguiente = next(
        (s for s in sesiones if s.fecha > hoy and not s.completada), None
    )
    if siguiente is None:
        return "SIGUIENTE: no quedan sesiones"
    dia = DIAS[siguiente.fecha.weekday()]
    return f"SIGUIENTE: {dia}, {siguiente.tipo} {siguiente.km} km"


def _linea_ultima_completada(sesiones: list[Sesion]) -> str:
    completadas = [s for s in sesiones if s.completada]
    if not completadas:
        return "ÚLTIMA COMPLETADA: ninguna todavía"
    ultima = completadas[-1]
    dia = DIAS[ultima.fecha.weekday()]
    return (
        f"ÚLTIMA COMPLETADA: {dia}, {ultima.tipo} {ultima.km} km,"
        f' sensación "{ultima.sensacion}"'
    )
