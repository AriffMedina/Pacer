from typing import Any

from pacer.domain.puertos.observabilidad import (
    TIPO_GENERACION,
    SinObservabilidad,
)


def test_sin_llaves_la_traza_no_hace_nada_y_no_falla() -> None:
    observabilidad = SinObservabilidad()

    with observabilidad.observar("turno", TIPO_GENERACION, entrada="hola") as obs:
        obs.registrar_salida("respuesta")

    observabilidad.cerrar()


def test_el_objeto_nulo_cumple_el_puerto() -> None:
    # Si la firma cambiara, el adaptador real y el nulo se desincronizarían y
    # la app funcionaría en desarrollo y reventaría con llaves puestas.
    observabilidad: Any = SinObservabilidad()

    with observabilidad.observar(
        nombre="llamada",
        tipo=TIPO_GENERACION,
        entrada={"mensajes": []},
        modelo="algun-modelo",
        metadatos={"vuelta": 1},
    ) as obs:
        assert obs.registrar_salida({"texto": "ok"}) is None


def test_una_excepcion_dentro_de_la_traza_se_propaga() -> None:
    # Trazar no debe tragarse errores del negocio: solo los suyos propios.
    observabilidad = SinObservabilidad()
    reventado = False

    try:
        with observabilidad.observar("turno"):
            raise ValueError("fallo real")
    except ValueError:
        reventado = True

    assert reventado
