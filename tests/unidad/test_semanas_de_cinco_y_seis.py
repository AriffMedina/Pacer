"""Semanas de 5 y 6 días.

El piloto solo componía 3 y 4. Lo pidió un usuario real con un argumento
bueno: al gimnasio se va cinco días y nadie se escandaliza. Correr es de más
impacto, pero eso se resuelve con la MEZCLA de sesiones —más fácil, no más
calidad— y no prohibiendo días.

Donde sí se para la cuenta es en siete: sin un día sin correr no hay
adaptación. El músculo se reconstruye descansando, así que el séptimo día es
descanso y el coach lo dice con esas palabras.
"""

from datetime import date

import pytest

from pacer.domain.servicios.generador_plan import (
    COMPOSICION,
    ORDEN_BLOQUES,
    generar_plan,
)

INICIO = date(2026, 8, 17)


# --- la tabla ------------------------------------------------------------


def test_se_admiten_de_tres_a_seis_dias() -> None:
    assert sorted(COMPOSICION) == [3, 4, 5, 6]


def test_siete_dias_nunca() -> None:
    """No es un hueco por llenar: es la decisión. Correr los siete días deja al
    cuerpo sin la ventana en la que efectivamente mejora."""
    assert 7 not in COMPOSICION


@pytest.mark.parametrize("dias", sorted(COMPOSICION))
@pytest.mark.parametrize("bloque", ORDEN_BLOQUES)
def test_la_semana_suma_exactamente_los_dias(dias: int, bloque: str) -> None:
    """El largo siempre es 1 y no aparece en la tupla. Si las cuentas no
    cuadran, el corredor entrena un día de más o de menos sin que nadie avise."""
    faciles, calidad = COMPOSICION[dias][bloque]

    assert faciles + calidad + 1 == dias


@pytest.mark.parametrize("dias", sorted(COMPOSICION))
def test_en_base_no_hay_calidad(dias: int) -> None:
    """La base construye volumen. Meter series antes de tener kilómetros es
    exactamente cómo se lesiona la gente que empieza con prisa."""
    assert COMPOSICION[dias]["base"][1] == 0


@pytest.mark.parametrize("dias", sorted(COMPOSICION))
def test_el_pico_es_donde_mas_calidad_hay(dias: int) -> None:
    calidad = {b: COMPOSICION[dias][b][1] for b in ORDEN_BLOQUES}

    assert calidad["pico"] == max(calidad.values())
    assert calidad["pico"] > calidad["base"]


@pytest.mark.parametrize("dias", sorted(COMPOSICION))
def test_el_tapering_afloja_respecto_al_pico(dias: int) -> None:
    """Llegar fresco a la carrera es el objetivo entero del tapering."""
    assert COMPOSICION[dias]["tapering"][1] <= COMPOSICION[dias]["pico"][1]


@pytest.mark.parametrize("dias", sorted(COMPOSICION))
@pytest.mark.parametrize("bloque", ORDEN_BLOQUES)
def test_nunca_mas_de_dos_sesiones_de_calidad(dias: int, bloque: str) -> None:
    """Dos por semana es el techo en cualquier composición. La tercera no
    entrena más: acumula fatiga y lesiona. Por eso sumar días no puede
    traducirse en sumar series."""
    assert COMPOSICION[dias][bloque][1] <= 2


def test_los_dias_que_se_ganan_van_a_rodaje_suave() -> None:
    """La respuesta técnica a "si al gimnasio voy cinco días, ¿por qué a correr
    no?": puedes, y lo que se añade es volumen fácil. Entre 3 y 6 días las
    sesiones fáciles crecen de forma estricta y la calidad se estanca en su
    techo."""
    for bloque in ORDEN_BLOQUES:
        faciles = [COMPOSICION[d][bloque][0] for d in sorted(COMPOSICION)]
        # Monótono, no estrictamente creciente: entre 3 y 4 días el extra va a
        # calidad en el pico, y ese reparto ya estaba decidido antes que esto.
        assert faciles == sorted(faciles), (
            f"en {bloque} sumar días quitó rodaje: {faciles}"
        )
        # A partir del cuarto, en cambio, todo lo que se suma es suave.
        assert COMPOSICION[6][bloque][0] > COMPOSICION[5][bloque][0]
        assert COMPOSICION[5][bloque][0] > COMPOSICION[4][bloque][0]


# --- el plan de verdad ---------------------------------------------------


@pytest.mark.parametrize("dias", [5, 6])
def test_genera_un_plan_completo(dias: int) -> None:
    plan = generar_plan(
        distancia="10k",
        nivel="intermedio",
        semanas=12,
        km_semana=30,
        dias=dias,
        inicio=INICIO,
    )

    assert all(len(s.sesiones) == dias for s in plan.semanas)


@pytest.mark.parametrize("dias", [5, 6])
def test_cada_semana_deja_dias_sin_correr(dias: int) -> None:
    """Con 5 días quedan 2 libres; con 6, uno. Que existan es el argumento
    entero de por qué 7 no está."""
    plan = generar_plan(
        distancia="21k",
        nivel="intermedio",
        semanas=14,
        km_semana=40,
        dias=dias,
        inicio=INICIO,
    )

    for semana in plan.semanas:
        distintos = {s.fecha for s in semana.sesiones}
        assert len(distintos) == dias
        assert 7 - len(distintos) >= 1


@pytest.mark.parametrize("dias", [5, 6])
def test_siempre_hay_exactamente_un_largo(dias: int) -> None:
    plan = generar_plan(
        distancia="maraton",
        nivel="avanzado",
        semanas=18,
        km_semana=50,
        dias=dias,
        inicio=INICIO,
    )

    for semana in plan.semanas:
        assert sum(1 for s in semana.sesiones if s.tipo == "largo") == 1
