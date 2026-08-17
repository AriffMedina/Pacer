"""El reloj del corredor, no el del servidor.

`datetime.now(UTC).date()` no es "hoy" para quien corre. En México son seis
horas menos: a las 18:00 del domingo el servidor ya cree que es lunes, y con él
la sesión de hoy, la racha y la hora de los recordatorios. Un producto que se
usa al salir a correr —de tarde y de noche— se rompe justo a esa hora.

La zona es configurable y por defecto es la de México. Es la decisión honesta
para un piloto de un corredor: guardar la zona en el perfil solo tiene sentido
el día que haya varios, y ese día esto es el único sitio que cambia.
"""

from datetime import UTC, date, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ZONA_POR_DEFECTO = "America/Mexico_City"


def zona(nombre: str = ZONA_POR_DEFECTO) -> tzinfo:
    """La zona pedida, o UTC si el sistema no la conoce.

    El respaldo es `datetime.UTC` y no `ZoneInfo("UTC")`: Windows no trae base
    de zonas horarias, así que el propio respaldo fallaría —y con él el
    arranque— justo en la máquina donde se desarrolla. La dependencia `tzdata`
    la provee; esto es el cinturón por si algún día no está.
    """
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return UTC


def ahora(nombre: str = ZONA_POR_DEFECTO) -> datetime:
    """El instante actual, con zona. Siempre consciente, nunca ingenuo."""
    return datetime.now(UTC).astimezone(zona(nombre))


def hoy(nombre: str = ZONA_POR_DEFECTO) -> date:
    """El día que es para el corredor."""
    return ahora(nombre).date()
