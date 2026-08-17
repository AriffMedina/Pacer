"""Un recordatorio: el coach buscándote.

`vision.md`: "El canal proactivo no es un extra: es el mecanismo por el que el
ciclo se cierra. Es la única forma de que el cuarto paso ocurra sin depender de
que el usuario recuerde abrir una app."

La `clave` es estable y se deriva del hecho que lo origina —el corredor y la
fecha de la sesión— para que materializar dos veces no duplique nada. La
unicidad la garantiza la base, no el cuidado de quien llama.
"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Recordatorio:
    corredor_id: int
    texto: str
    programado_para: datetime
    clave: str
    canal: str = "telegram"
    id: int = 0
    enviado_en: datetime | None = None

    @property
    def enviado(self) -> bool:
        return self.enviado_en is not None


def clave_de_sesion(corredor_id: int, fecha: date) -> str:
    """Identidad estable del recordatorio de una sesión."""
    return f"sesion:{corredor_id}:{fecha.isoformat()}"
