"""Un número de días que el generador no admite no puede tumbar el turno.

Pasó en producción, con la app pública y alguien probándola: dijo que podía
entrenar CINCO días, el generador solo compone 3 o 4, y el `ValueError` subió
sin que nadie lo atrapara hasta convertirse en un 500. Desde el navegador eso
se ve como "se cortó la conexión" — sin explicación y sin nada que hacer.

El coach tiene que poder decir "puedo armarte 3 o 4 días, ¿cuál prefieres?".
Un límite del sistema se explica; no se estrella.
"""

from datetime import date

import pytest

from pacer.application.casos_uso.conversar import _generar
from pacer.application.casos_uso.crear_plan import crear_plan
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.servicios.generador_plan import COMPOSICION

HOY = date(2026, 8, 17)


def _perfil(dias: int) -> Perfil:
    return Perfil(
        nombre="Ariff",
        objetivo="10k",
        nivel="principiante",
        dias_disponibles=dias,
        km_semana=15,
        fecha_carrera=date(2026, 11, 15),
    )


def test_el_generador_sigue_rechazando_lo_que_no_sabe_componer() -> None:
    """Siete días no tienen composición: sin descanso no hay adaptación."""
    assert 7 not in COMPOSICION
    with pytest.raises(ValueError):
        crear_plan(_perfil(7), hoy=HOY)


def test_pedir_siete_dias_no_revienta_el_turno() -> None:
    """Lo que antes era un 500 ahora es una respuesta que el modelo puede leer."""
    plan, respuesta = _generar(_perfil(7), hoy=HOY, previo=None)

    assert plan is None
    assert "error" in respuesta


def test_el_rechazo_dice_cuantos_dias_si_admite() -> None:
    """Sin las alternativas, el coach solo sabe decir que no. El corredor se
    queda igual de atascado que con el 500, pero con mejores modales."""
    _, respuesta = _generar(_perfil(7), hoy=HOY, previo=None)

    admitidos = respuesta["dias_admitidos"]
    assert sorted(admitidos) == sorted(COMPOSICION)


def test_los_dias_que_si_se_admiten_siguen_armando_plan() -> None:
    """La red no puede tragarse los casos buenos."""
    for dias in COMPOSICION:
        plan, respuesta = _generar(_perfil(dias), hoy=HOY, previo=None)
        assert plan is not None, f"{dias} días debería armar plan"
        assert "error" not in respuesta
