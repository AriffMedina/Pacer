"""Despachador de herramientas.

Los guardarrailes corren ANTES de ejecutar. Si el modelo pide algo que no
corresponde, la herramienta devuelve un error estructurado y el modelo
pregunta en vez de inventar.
"""

from typing import Any

from pacer.application.guardarrailes.reglas import (
    campos_faltantes,
    puede_subir_intensidad,
)
from pacer.application.herramientas.esquemas import HERRAMIENTAS
from pacer.domain.entidades.perfil import Perfil

# Herramientas que aumentan la carga y por lo tanto pasan por el filtro de dolor.
SUBEN_INTENSIDAD = frozenset({"subir_intensidad", "adelantar_calidad"})

CONOCIDAS = frozenset(HERRAMIENTAS) | SUBEN_INTENSIDAD


def despachar(nombre: str, entrada: dict[str, Any], perfil: Perfil) -> dict[str, Any]:
    """Valida y ejecuta una llamada a herramienta pedida por el modelo."""
    if nombre not in CONOCIDAS:
        return {"error": "herramienta_desconocida", "nombre": nombre}

    if nombre in SUBEN_INTENSIDAD and not puede_subir_intensidad(perfil):
        return {
            "error": "bloqueado_por_dolor",
            "explicacion": (
                "Hay dolor reportado; esta semana ninguna acción sube la carga."
            ),
        }

    if nombre == "generar_plan":
        faltan = campos_faltantes(perfil)
        if faltan:
            return {"error": "faltan_datos", "campos": list(faltan)}

    # La ejecución real de cada herramienta se conecta en el orquestador.
    return {"ok": True, "herramienta": nombre, "entrada": entrada}
