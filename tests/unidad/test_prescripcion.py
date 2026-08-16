from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pacer.domain.entidades.plan import Sesion
from pacer.domain.servicios.prescripcion import prescribir

BLOQUES = ("base", "construccion", "pico", "tapering")
NIVELES = ("nuevo", "principiante", "intermedio", "avanzado")


def sesion(tipo: str = "calidad", km: float = 8.0) -> Sesion:
    return Sesion(fecha=date(2026, 8, 20), tipo=tipo, km=km)  # type: ignore[arg-type]


# --- el invariante que no se puede romper --------------------------------


@given(
    tipo=st.sampled_from(["facil", "calidad", "largo"]),
    km=st.floats(min_value=1.0, max_value=42.0),
    nivel=st.sampled_from(NIVELES),
    bloque=st.sampled_from(BLOQUES),
)
def test_los_tramos_suman_los_kilometros_de_la_sesion(
    tipo: str, km: float, nivel: str, bloque: str
) -> None:
    """Si el desglose no suma lo planeado, el plan y la instrucción se
    contradicen, y quien corre le hace caso a la instrucción."""
    receta = prescribir(sesion(tipo, km), nivel=nivel, bloque=bloque)  # type: ignore[arg-type]

    assert sum(t.km for t in receta.tramos) == pytest.approx(round(km, 1), abs=0.05)


@given(
    tipo=st.sampled_from(["facil", "calidad", "largo"]),
    km=st.floats(min_value=1.0, max_value=42.0),
    nivel=st.sampled_from([*NIVELES, None]),
    bloque=st.sampled_from([*BLOQUES, ""]),
)
def test_siempre_devuelve_algo_que_se_puede_leer(
    tipo: str, km: float, nivel: str | None, bloque: str
) -> None:
    """Un plan viejo puede venir sin bloque y un perfil sin nivel. Ni uno ni
    otro pueden dejar la tarjeta en blanco."""
    receta = prescribir(sesion(tipo, km), nivel=nivel, bloque=bloque)  # type: ignore[arg-type]

    assert receta.resumen and receta.esfuerzo and receta.porque
    assert receta.tramos
    assert all(t.titulo and t.detalle for t in receta.tramos)
    assert all(t.km > 0 for t in receta.tramos)


# --- sesión fácil --------------------------------------------------------


def test_la_facil_es_un_solo_tramo_continuo() -> None:
    """Partir un rodaje suave en calentamiento y vuelta a la calma es ruido:
    la sesión entera YA es el calentamiento."""
    receta = prescribir(sesion("facil", 6.0), nivel="intermedio", bloque="base")

    assert len(receta.tramos) == 1
    assert receta.tramos[0].km == 6.0


def test_la_facil_avisa_de_no_correrla_rapido() -> None:
    """Es el error más común y el que arruina la sesión de calidad siguiente."""
    receta = prescribir(sesion("facil", 6.0), nivel="nuevo", bloque="base")

    assert "hablar" in (receta.tramos[0].detalle + receta.esfuerzo).lower()


# --- sesión de calidad ---------------------------------------------------


def test_la_calidad_lleva_calentamiento_y_vuelta_a_la_calma() -> None:
    """Entrar en frío a una sesión fuerte es como se lesiona la gente."""
    receta = prescribir(sesion("calidad", 10.0), nivel="intermedio", bloque="construccion")

    titulos = [t.titulo for t in receta.tramos]
    assert titulos[0] == "Calentamiento"
    assert titulos[-1] == "Vuelta a la calma"
    assert len(receta.tramos) == 3


def test_en_construccion_la_calidad_son_series() -> None:
    receta = prescribir(sesion("calidad", 10.0), nivel="intermedio", bloque="construccion")

    assert "×" in receta.tramos[1].detalle


def test_en_pico_la_calidad_es_ritmo_de_carrera_continuo() -> None:
    """En pico se ensaya la carrera, no se buscan más adaptaciones."""
    receta = prescribir(sesion("calidad", 10.0), nivel="intermedio", bloque="pico")

    assert "seguido" in receta.tramos[1].detalle.lower()
    assert "ritmo de carrera" in receta.tramos[1].detalle.lower()


def test_en_base_la_calidad_son_progresivos_no_series() -> None:
    """En base todavía no hay fondo para series: se busca soltura."""
    receta = prescribir(sesion("calidad", 8.0), nivel="intermedio", bloque="base")

    assert "progresiv" in receta.tramos[1].detalle.lower()
    assert "×" not in receta.tramos[1].detalle


def test_a_quien_empieza_las_series_se_le_dan_con_pausa_caminando() -> None:
    """Trotar la recuperación supone una base que quien empieza no tiene."""
    receta = prescribir(sesion("calidad", 6.0), nivel="nuevo", bloque="construccion")

    assert "camin" in receta.tramos[1].detalle.lower()


def test_a_quien_ya_corre_se_le_dan_trotando() -> None:
    receta = prescribir(sesion("calidad", 12.0), nivel="avanzado", bloque="construccion")

    assert "trot" in receta.tramos[1].detalle.lower()
    assert "camin" not in receta.tramos[1].detalle.lower()


def test_nunca_manda_menos_de_dos_series() -> None:
    """Una serie sola no es una sesión de series."""
    receta = prescribir(sesion("calidad", 3.0), nivel="avanzado", bloque="construccion")

    assert "×" in receta.tramos[1].detalle
    repeticiones = int(receta.tramos[1].detalle.split("×")[0].strip())
    assert repeticiones >= 2


# --- fondo largo ---------------------------------------------------------


def test_el_largo_es_continuo_y_suave() -> None:
    receta = prescribir(sesion("largo", 18.0), nivel="intermedio", bloque="construccion")

    assert len(receta.tramos) == 1
    assert "suave" in receta.esfuerzo.lower()


def test_en_pico_el_largo_termina_a_ritmo_de_carrera() -> None:
    """Es el ensayo específico: llegar cansado y aun así sostener el ritmo."""
    receta = prescribir(sesion("largo", 20.0), nivel="intermedio", bloque="pico")

    assert len(receta.tramos) == 2
    assert "ritmo de carrera" in receta.tramos[1].detalle.lower()
    assert receta.tramos[1].km < receta.tramos[0].km


def test_en_tapering_el_largo_no_se_acelera() -> None:
    """En tapering se descansa. Meterle ritmo es el error clásico de esa semana."""
    receta = prescribir(sesion("largo", 12.0), nivel="avanzado", bloque="tapering")

    assert len(receta.tramos) == 1


# --- el porqué -----------------------------------------------------------


def test_cada_sesion_explica_para_que_sirve() -> None:
    """Un corredor que entiende por qué, cumple. Uno que obedece, abandona."""
    porques = {
        prescribir(sesion(t, 10.0), nivel="intermedio", bloque=b).porque
        for t in ("facil", "calidad", "largo")
        for b in BLOQUES
    }

    assert len(porques) > 1
    assert all(len(p) > 30 for p in porques)
