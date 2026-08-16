import pytest
from hypothesis import given
from hypothesis import strategies as st

from pacer.domain.servicios.categoria import (
    KM_MAXIMO,
    KM_MINIMO,
    categoria_de_km,
    como_se_entrena,
    km_oficiales,
)

# --- el mapeo ------------------------------------------------------------


@pytest.mark.parametrize(
    ("km", "esperada"),
    [
        (3.0, "5k"),
        (3.5, "5k"),      # el caso que rompió: una carrera de barrio
        (5.0, "5k"),
        (7.4, "5k"),
        (7.6, "10k"),
        (10.0, "10k"),
        (12.0, "10k"),
        (15.5, "10k"),
        (16.0, "21k"),
        (21.1, "21k"),
        (30.0, "21k"),
        (32.0, "maraton"),
        (42.2, "maraton"),
        (44.0, "maraton"),
    ],
)
def test_cada_distancia_cae_en_la_categoria_mas_parecida(
    km: float, esperada: str
) -> None:
    assert categoria_de_km(km) == esperada


def test_las_distancias_oficiales_caen_en_su_propia_categoria() -> None:
    """Si un 21.1 no cayera en "21k", el mapeo estaría mal por construcción."""
    for objetivo, km in km_oficiales().items():
        assert categoria_de_km(km) == objetivo


# --- lo que queda fuera --------------------------------------------------


def test_una_prueba_de_pista_no_es_una_carrera_de_fondo() -> None:
    """300 m no se entrena con un plan de 5k. Decir que sí sería mentir."""
    assert categoria_de_km(0.3) is None
    assert categoria_de_km(1.5) is None


def test_el_ultrafondo_no_se_entrena_como_un_maraton() -> None:
    """Un 100k tiene otra preparación. Darle el plan de maratón sería peligroso."""
    assert categoria_de_km(100.0) is None
    assert categoria_de_km(50.0) is None


def test_una_distancia_absurda_no_revienta() -> None:
    assert categoria_de_km(0) is None
    assert categoria_de_km(-5) is None


@given(km=st.floats(min_value=-1000, max_value=1000, allow_nan=False))
def test_o_devuelve_una_categoria_que_el_generador_conoce_o_no_devuelve_nada(
    km: float,
) -> None:
    """El generador solo sabe cuatro distancias. Este mapeo no puede inventarle
    una quinta: o cae en las que conoce, o dice que no cubre esa carrera."""
    categoria = categoria_de_km(km)

    assert categoria is None or categoria in km_oficiales()


@given(km=st.floats(min_value=KM_MINIMO, max_value=KM_MAXIMO))
def test_todo_lo_que_esta_dentro_del_rango_tiene_plan(km: float) -> None:
    assert categoria_de_km(km) is not None


# --- cómo se lo explicamos a la persona ----------------------------------


def test_explica_con_que_plan_se_entrena_una_distancia_rara() -> None:
    """Es la frase que evita la contradicción: el coach decía "es de 3.5 km" y
    acto seguido "no puedo hacer planes de 5 km"."""
    assert como_se_entrena(3.5) == "se entrena como un 5K"


def test_cuando_la_distancia_es_la_oficial_no_da_explicaciones_de_mas() -> None:
    assert como_se_entrena(10.0) == "es un 10K"
    assert como_se_entrena(42.2) == "es un maratón"


def test_lo_que_no_cubre_lo_dice_claro() -> None:
    assert "no" in como_se_entrena(0.4).lower()
    assert "no" in como_se_entrena(80.0).lower()
