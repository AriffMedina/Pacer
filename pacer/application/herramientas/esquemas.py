"""Esquemas de las herramientas que se le exponen al modelo.

`model_json_schema()` es exactamente lo que Bedrock espera en `toolSpec`, así
que el esquema no se escribe dos veces.

Las descripciones dicen CUÁNDO usar la herramienta, no qué hace: es lo que más
mueve la aguja cuando el modelo no llama la herramienta o la llama mal.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ActualizarPerfil(BaseModel):
    """Úsala en cuanto el corredor mencione cualquiera de estos datos."""

    objetivo: Literal["5k", "10k", "21k", "maraton"] | None = None
    nivel: Literal["nuevo", "principiante", "intermedio", "avanzado"] | None = None
    dias_disponibles: int | None = Field(None, ge=2, le=6)
    km_semana: int | None = Field(None, ge=0, le=200)
    fecha_carrera: str | None = None
    dolor_actual: bool | None = None


class RegistrarSesion(BaseModel):
    """Úsala cuando el corredor cuente cómo le fue en un entrenamiento.

    Nunca pide un identificador de sesión: se manda la pista temporal tal como
    la dijo el corredor y el código resuelve a qué sesión se refiere.
    """

    pista_temporal: str = Field(description="Por ejemplo: ayer, el martes, hoy")
    km: float | None = Field(None, ge=0, le=100)
    sensacion: (
        Literal["facil", "normal", "pesada", "muy_dura", "con_dolor"] | None
    ) = None


class GenerarPlan(BaseModel):
    """Úsala solo cuando el perfil esté completo. Si falta algo, pregunta."""


HERRAMIENTAS: dict[str, type[BaseModel]] = {
    "actualizar_perfil": ActualizarPerfil,
    "registrar_sesion": RegistrarSesion,
    "generar_plan": GenerarPlan,
}


def catalogo_para_bedrock() -> dict[str, list[dict[str, object]]]:
    """Arma el `toolConfig` que espera la API `converse`."""
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": nombre,
                    "description": (modelo.__doc__ or "").strip(),
                    "inputSchema": {"json": modelo.model_json_schema()},
                }
            }
            for nombre, modelo in HERRAMIENTAS.items()
        ]
    }
