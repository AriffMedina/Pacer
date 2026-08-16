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

    nombre: str | None = Field(
        None,
        max_length=40,
        description="Cómo se llama o cómo quiere que le digan. Solo el nombre.",
    )
    objetivo: Literal["5k", "10k", "21k", "maraton"] | None = None
    nivel: Literal["nuevo", "principiante", "intermedio", "avanzado"] | None = None
    dias_disponibles: int | None = Field(None, ge=2, le=6)
    km_semana: int | None = Field(None, ge=0, le=200)
    fecha_carrera: str | None = Field(
        None,
        description=(
            "Fecha de la carrera en formato ISO AAAA-MM-DD, por ejemplo "
            "2026-12-12. Si el corredor no dijo el año, pregúntaselo antes."
        ),
    )
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


class ApuntarCarrera(BaseModel):
    """Úsala cuando el corredor mencione una carrera con fecha que va a correr.

    Sirve para cualquier carrera de su calendario, no solo la que entrena. Si
    además quiere entrenar PARA ella, llama también a actualizar_perfil.
    """

    nombre: str = Field(
        max_length=80, description="Cómo la llama el corredor. Por ejemplo: Maratón CDMX"
    )
    fecha: str = Field(
        description=(
            "Fecha en formato ISO AAAA-MM-DD. Si no dijo el año, pregúntaselo "
            "antes de llamar esta herramienta."
        )
    )
    distancia: str | None = Field(
        None, max_length=20, description="Por ejemplo: 5k, 10k, 21k, maraton, 15k"
    )
    nota: str | None = Field(
        None, max_length=200, description="Lo que el corredor quiera recordar de ella."
    )


HERRAMIENTAS: dict[str, type[BaseModel]] = {
    "actualizar_perfil": ActualizarPerfil,
    "registrar_sesion": RegistrarSesion,
    "generar_plan": GenerarPlan,
    "apuntar_carrera": ApuntarCarrera,
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
