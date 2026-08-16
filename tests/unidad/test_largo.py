from pacer.domain.reglas.largo import (
    LARGO_TOPE_KM,
    largo_maximo_permitido,
    tope_por_tiempo,
)


def test_sin_historial_solo_mandan_los_topes() -> None:
    assert largo_maximo_permitido("5k", []) == LARGO_TOPE_KM["5k"]


def test_no_crece_mas_de_diez_por_ciento_sobre_el_maximo_reciente() -> None:
    assert largo_maximo_permitido("21k", [10.0, 12.0, 11.0]) == 12.0 * 1.10


def test_solo_mira_las_ultimas_cuatro_semanas() -> None:
    # El 20 quedó fuera de la ventana: ya no cuenta como referencia.
    permitido = largo_maximo_permitido("maraton", [20.0, 8.0, 9.0, 10.0, 11.0])

    assert permitido == 11.0 * 1.10


def test_el_tope_por_distancia_manda_cuando_es_el_mas_bajo() -> None:
    # 1.10 × 20 = 22, pero un 5k no pasa de 12.
    assert largo_maximo_permitido("5k", [20.0]) == LARGO_TOPE_KM["5k"]


def test_el_tope_por_tiempo_recorta_el_maraton() -> None:
    # 32 km al ritmo fácil estimado pasan de 3 horas.
    assert tope_por_tiempo() < LARGO_TOPE_KM["maraton"]
    assert largo_maximo_permitido("maraton", [100.0]) == tope_por_tiempo()
