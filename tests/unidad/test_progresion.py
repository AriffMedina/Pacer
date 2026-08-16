import pytest

from pacer.domain.reglas.periodizacion import repartir_bloques
from pacer.domain.reglas.progresion import siguiente_volumen


def test_no_sube_mas_de_diez_por_ciento() -> None:
    assert siguiente_volumen(30, es_descarga=False) == 33


def test_descarga_baja_el_volumen() -> None:
    assert siguiente_volumen(40, es_descarga=True) == 26


def test_el_tapering_se_reserva_primero() -> None:
    bloques = repartir_bloques("maraton", 16)

    assert bloques["tapering"] == 3


def test_los_bloques_suman_el_total() -> None:
    for distancia, semanas in (("5k", 8), ("10k", 10), ("21k", 12), ("maraton", 16)):
        bloques = repartir_bloques(distancia, semanas)

        assert sum(bloques.values()) == semanas


def test_el_residuo_va_a_base() -> None:
    bloques = repartir_bloques("maraton", 16)

    assert bloques == {"base": 6, "construccion": 5, "pico": 2, "tapering": 3}


def test_un_plan_sin_espacio_para_tapering_se_rechaza() -> None:
    with pytest.raises(ValueError):
        repartir_bloques("maraton", 3)
