"""La compuerta dura de §2.2: nunca se produce un plan comprimido."""

import pytest

from pacer.domain.reglas.duracion import (
    PlanImposible,
    descarga_cada,
    descarga_en_base,
    validar_duracion,
)


def test_una_combinacion_valida_pasa() -> None:
    validar_duracion("21k", "intermedio", 12)


def test_menos_semanas_que_el_minimo_del_nivel_se_rechaza() -> None:
    # 21k + nuevo exige 20 semanas.
    with pytest.raises(PlanImposible) as error:
        validar_duracion("21k", "nuevo", 16)

    assert error.value.minimo == 20


def test_mas_semanas_que_el_maximo_se_rechaza() -> None:
    with pytest.raises(PlanImposible):
        validar_duracion("5k", "intermedio", 20)


def test_maraton_para_nuevo_se_rechaza_siempre() -> None:
    for semanas in (12, 20, 24, 52):
        with pytest.raises(PlanImposible):
            validar_duracion("maraton", "nuevo", semanas)


def test_el_rechazo_no_revienta_comparando_contra_none() -> None:
    # `SEMANAS_MIN_POR_NIVEL["maraton"]["nuevo"]` es None: la compuerta tiene
    # que atajarlo antes de cualquier comparación numérica.
    with pytest.raises(PlanImposible):
        validar_duracion("maraton", "nuevo", 24)


def test_21k_para_nuevo_ahora_tiene_solucion() -> None:
    # Era el rango vacío de la v1.0: mínimo 20 contra máximo 18.
    validar_duracion("21k", "nuevo", 20)
    validar_duracion("21k", "nuevo", 22)


def test_los_principiantes_descargan_cada_tres_semanas() -> None:
    assert descarga_cada("nuevo") == 3
    assert descarga_cada("principiante") == 3
    assert descarga_cada("intermedio") == 4
    assert descarga_cada("avanzado") == 4


def test_solo_los_principiantes_descargan_dentro_del_bloque_base() -> None:
    assert descarga_en_base("nuevo")
    assert descarga_en_base("principiante")
    assert not descarga_en_base("intermedio")
    assert not descarga_en_base("avanzado")
