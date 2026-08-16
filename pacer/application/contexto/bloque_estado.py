"""Bloque de estado precalculado que se inyecta al prompt del sistema.

El modelo LEE esto. No calcula fechas, no cuenta semanas y no deduce en qué
punto del plan está el corredor. Evita más alucinaciones que cualquier
instrucción escrita en el prompt.
"""

from datetime import date

from pacer.domain.entidades.plan import Plan, Semana, Sesion

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


def construir_bloque(plan: Plan, hoy: date, fecha_carrera: date) -> str:
    """Arma el bloque de estado que el coach lee antes de responder."""
    sesiones = sorted(
        (sesion for semana in plan.semanas for sesion in semana.sesiones),
        key=lambda sesion: sesion.fecha,
    )
    semana = _semana_de(plan, hoy)
    numero = semana.numero if semana is not None else len(plan.semanas)

    return "\n".join(
        (
            _linea_de_encabezado(hoy, numero, len(plan.semanas), fecha_carrera),
            _linea_de_hoy(sesiones, hoy),
            _linea_siguiente(sesiones, hoy),
            _linea_ultima_completada(sesiones),
        )
    )


def _linea_de_encabezado(
    hoy: date, semana: int, total: int, fecha_carrera: date
) -> str:
    fecha = f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]}"
    faltan = (fecha_carrera - hoy).days
    return f"HOY: {fecha} · SEMANA {semana} DE {total} · faltan {faltan} días"


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
