"""Guardarrailes duros. Viven en código, nunca en el prompt.

Un guardarrail escrito en el prompt es una sugerencia; uno escrito acá es una
garantía. El modelo no puede desobedecer lo que nunca llega a ejecutar.
"""

from pacer.domain.entidades.perfil import Perfil

CAMPOS_REQUERIDOS = (
    "objetivo",
    "nivel",
    "dias_disponibles",
    "km_semana",
    "fecha_carrera",
)


def campos_faltantes(perfil: Perfil) -> tuple[str, ...]:
    """Qué le falta al perfil para poder generar un plan."""
    return tuple(
        campo for campo in CAMPOS_REQUERIDOS if getattr(perfil, campo) is None
    )


def puede_generar_plan(perfil: Perfil) -> bool:
    """El plan no se genera con datos incompletos: se pregunta."""
    return not campos_faltantes(perfil)


def puede_subir_intensidad(perfil: Perfil) -> bool:
    """Si hay dolor reportado, ninguna acción sube la intensidad. Sin excepciones."""
    return not perfil.dolor_actual
