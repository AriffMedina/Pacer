"""El reloj del corredor.

El bug: a las 18:00 del domingo en México el servidor en UTC ya cree que es
lunes. La sesión de hoy, la racha y la hora del recordatorio se corren seis
horas antes justo cuando la gente sale a correr.
"""

from datetime import UTC, datetime
from unittest.mock import patch

from pacer.infrastructure.reloj import ahora, hoy, zona


def congelar(iso_utc: str):  # type: ignore[no-untyped-def]
    """Fija el instante en UTC, que es lo que devuelve el reloj del servidor."""
    momento = datetime.fromisoformat(iso_utc).replace(tzinfo=UTC)

    class RelojFijo(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def, override]
            return momento.astimezone(tz) if tz else momento

    return patch("pacer.infrastructure.reloj.datetime", RelojFijo)


def test_de_noche_en_mexico_todavia_es_el_mismo_dia() -> None:
    """21:00 del domingo en México son las 03:00 del lunes en UTC."""
    with congelar("2026-08-17T03:00:00"):
        assert hoy().isoformat() == "2026-08-16"


def test_de_madrugada_ya_cambio_el_dia() -> None:
    with congelar("2026-08-17T07:00:00"):  # 01:00 en México
        assert hoy().isoformat() == "2026-08-17"


def test_el_instante_siempre_lleva_zona() -> None:
    """Un datetime ingenuo contra Postgres revienta al restarlo."""
    assert ahora().tzinfo is not None


def test_una_zona_mal_escrita_no_tumba_la_app() -> None:
    """Degradarse a UTC es lo que había antes. No levantar, no."""
    assert str(zona("Marte/Olympus")) == "UTC"
