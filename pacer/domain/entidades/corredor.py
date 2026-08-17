"""El corredor: identidad y perfil.

La identidad es por canal (el chat de Telegram) y no por credenciales. `email`
y `password_hash` existen en el modelo desde el principio pero van vacíos: el
piloto es de un corredor y la autenticación no era requisito.

Que existan desde hoy es deliberado. El aislamiento de datos —que es la parte
cara de rehacer— ya está: cada plan, semana y sesión cuelga de un `corredor_id`.
Agregar login después es llenar dos columnas y poner una dependencia delante,
no reabrir el modelo.
"""

from dataclasses import dataclass, field

from pacer.domain.entidades.perfil import Perfil


@dataclass(frozen=True)
class Corredor:
    id: int
    perfil: Perfil = field(default_factory=Perfil)
    telegram_chat_id: int | None = None
    email: str | None = None
    password_hash: str | None = None
