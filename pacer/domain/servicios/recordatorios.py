"""Qué recordatorios deberían existir, dado un plan y el momento actual.

Función pura: no toca base de datos ni reloj. Se le pasa `ahora` y devuelve la
lista completa de lo que corresponde. Quién los guarda y quién los entrega es
problema de otras capas — n8n entrega, no decide, y tampoco redacta.
"""

from datetime import datetime, timedelta

from pacer.domain.entidades.plan import Plan, Sesion
from pacer.domain.entidades.recordatorio import Recordatorio, clave_de_sesion

# Se pregunta al día siguiente, no el mismo día: antes de que corra, "¿cómo te
# fue?" es ruido.
DIAS_DE_ESPERA = 1
HORA_DE_AVISO = 19

# Más allá de esta ventana el recordatorio deja de servir: preguntar por una
# sesión de hace tres semanas no ayuda a nadie y ensucia el chat.
DIAS_DE_VENTANA = 4

NOMBRES = {"facil": "fácil", "calidad": "de calidad", "largo": "largo"}


def recordatorios_pendientes(
    plan: Plan, corredor_id: int, ahora: datetime
) -> list[Recordatorio]:
    """Recordatorios que deberían existir para las sesiones sin reportar."""
    hoy = ahora.date()
    desde = hoy - timedelta(days=DIAS_DE_VENTANA)

    return [
        _para(sesion, corredor_id, ahora)
        for semana in plan.semanas
        for sesion in semana.sesiones
        if not sesion.completada and desde <= sesion.fecha < hoy
    ]


def _para(sesion: Sesion, corredor_id: int, ahora: datetime) -> Recordatorio:
    tipo = NOMBRES.get(sesion.tipo, sesion.tipo)

    momento = datetime.combine(
        sesion.fecha + timedelta(days=DIAS_DE_ESPERA),
        datetime.min.time().replace(hour=HORA_DE_AVISO),
        tzinfo=ahora.tzinfo,
    )

    return Recordatorio(
        corredor_id=corredor_id,
        texto=(
            f"¿Cómo te fue en el {tipo} de {sesion.km} km? "
            "Cuéntame cómo lo sentiste."
        ),
        programado_para=momento,
        clave=clave_de_sesion(corredor_id, sesion.fecha),
    )
