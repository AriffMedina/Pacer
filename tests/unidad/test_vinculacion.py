"""El código que une el navegador con el chat de Telegram.

Hasta ahora cada canal creaba su propio corredor: armabas el plan en la web,
le escribías al bot y el bot te atendía como a un desconocido. Peor todavía,
los recordatorios salen de `corredor.telegram_chat_id`, así que quien solo
usaba la web no recibía ninguno nunca.

Esto es la mitad de dominio de ese arreglo: generar el código y decir si
todavía sirve. Quién lo canjea y cómo es cosa de las capas de fuera.
"""

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from pacer.domain.servicios.vinculacion import (
    DURACION,
    LARGO,
    generar_codigo,
    vence_en,
    vigente,
)

# Con zona, como todo instante del proyecto: `reloj.ahora()` la trae, y
# comparar con zona contra sin zona lanza TypeError.
AHORA = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


# --- el código -----------------------------------------------------------


def test_el_codigo_tiene_el_largo_acordado() -> None:
    assert len(generar_codigo()) == LARGO


def test_el_codigo_es_solo_digitos() -> None:
    """Se dicta en voz alta y se teclea en un móvil: nada de letras que se
    confundan, ni mayúsculas que obliguen a cambiar de teclado."""
    assert generar_codigo().isdigit()


def test_conserva_los_ceros_de_la_izquierda() -> None:
    """Un `randint` formateado como número se come el cero inicial y devuelve
    cinco dígitos. El corredor teclea lo que ve y no entra."""
    assert all(len(generar_codigo()) == LARGO for _ in range(400))


def test_dos_codigos_seguidos_no_son_el_mismo() -> None:
    """No es una prueba de aleatoriedad, es una red contra el peor error
    posible: devolver una constante."""
    assert len({generar_codigo() for _ in range(50)}) > 40


# --- la vigencia ---------------------------------------------------------


def test_recien_generado_esta_vigente() -> None:
    assert vigente(vence_en(AHORA), AHORA) is True


def test_justo_antes_de_expirar_sigue_sirviendo() -> None:
    assert vigente(vence_en(AHORA), AHORA + DURACION - timedelta(seconds=1)) is True


def test_al_expirar_deja_de_servir() -> None:
    """En el borde exacto ya no vale. Un código de un solo uso que sigue vivo
    'un ratito más' es un código que alguien puede canjear por ti."""
    assert vigente(vence_en(AHORA), AHORA + DURACION) is False


def test_sin_codigo_no_hay_nada_vigente() -> None:
    """Un corredor que nunca pidió código: `None` no es un código expirado,
    es la ausencia de código, y las dos cosas se responden igual."""
    assert vigente(None, AHORA) is False


@given(st.integers(min_value=1, max_value=60 * 24 * 30))
def test_cualquier_momento_posterior_al_vencimiento_esta_muerto(minutos: int) -> None:
    caduca = vence_en(AHORA)
    assert vigente(caduca, caduca + timedelta(minutes=minutos)) is False
