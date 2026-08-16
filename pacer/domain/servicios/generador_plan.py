"""Generador determinístico de planes.

Lo calcula código probado, nunca el modelo de lenguaje. El modelo traduce,
pregunta y explica; no decide la carga.

Cifras de `paramethers.md`. El 20% de calidad se reparte sobre kilómetros, no
sobre número de sesiones: es la métrica correcta (§5).
"""

from datetime import date, timedelta

from pacer.domain.entidades.plan import Plan, Semana, Sesion, TipoSesion
from pacer.domain.reglas.descarga import CADA_N_SEMANAS, FACTOR_VOLUMEN
from pacer.domain.reglas.periodizacion import repartir_bloques
from pacer.domain.reglas.progresion import PROGRESION_SEMANAL_MAX

LARGO_PCT = {"5k": 0.28, "10k": 0.30, "21k": 0.33, "maraton": 0.33}
CALIDAD_PCT = 0.20
TAPER_REDUCCION_VOLUMEN = 0.50
# Cuánto más largo es el largo que una sesión fácil cuando hay que rebalancear.
PESO_LARGO = 1.3

# Composición de la semana por bloque y días disponibles (`paramethers.md` §7).
COMPOSICION: dict[int, dict[str, tuple[int, int]]] = {
    # bloque: (sesiones fáciles, sesiones de calidad); el largo siempre es 1.
    3: {
        "base": (2, 0),
        "construccion": (1, 1),
        "pico": (1, 1),
        "tapering": (1, 1),
    },
    4: {
        "base": (3, 0),
        "construccion": (2, 1),
        "pico": (1, 2),
        "tapering": (2, 1),
    },
}

ORDEN_BLOQUES = ("base", "construccion", "pico", "tapering")


def generar_plan(
    distancia: str,
    semanas: int,
    km_semana: int,
    dias: int,
    inicio: date,
) -> Plan:
    """Construye un plan completo a partir del perfil del corredor.

    `inicio` se inyecta: el dominio no lee el reloj.
    """
    if dias not in COMPOSICION:
        raise ValueError(f"días no soportados: {dias} (se admiten 3 o 4)")

    bloques = repartir_bloques(distancia, semanas)
    primer_dia = inicio

    volumenes = _volumenes_por_semana(bloques, km_semana)
    construidas = []

    numero = 0
    for bloque in ORDEN_BLOQUES:
        for _ in range(bloques[bloque]):
            volumen, es_descarga = volumenes[numero]
            construidas.append(
                _armar_semana(
                    numero=numero + 1,
                    bloque=bloque,
                    km_total=volumen,
                    es_descarga=es_descarga,
                    dias=dias,
                    distancia=distancia,
                    inicio=primer_dia + timedelta(weeks=numero),
                )
            )
            numero += 1

    return Plan(version=1, semanas=tuple(construidas))


def _volumenes_por_semana(
    bloques: dict[str, int], km_inicial: int
) -> list[tuple[float, bool]]:
    """Calcula el volumen de cada semana y marca cuáles son de descarga."""
    volumenes: list[tuple[float, bool]] = []
    volumen = float(km_inicial)
    indice = 0

    for bloque in ("base", "construccion", "pico"):
        for _ in range(bloques[bloque]):
            indice += 1
            # El bloque base no lleva descargas (`paramethers.md` §6).
            es_descarga = bloque != "base" and indice % CADA_N_SEMANAS == 0
            if indice == 1:
                pass
            elif es_descarga:
                volumen *= FACTOR_VOLUMEN
            else:
                volumen *= PROGRESION_SEMANAL_MAX
            volumenes.append((round(volumen, 1), es_descarga))

    # El tapering baja de forma progresiva hasta el 50% del pico (§4).
    pico = volumen
    total_taper = bloques["tapering"]
    for k in range(1, total_taper + 1):
        factor = 1 - TAPER_REDUCCION_VOLUMEN * k / total_taper
        volumenes.append((round(pico * factor, 1), False))

    return volumenes


def _armar_semana(
    numero: int,
    bloque: str,
    km_total: float,
    es_descarga: bool,
    dias: int,
    distancia: str,
    inicio: date,
) -> Semana:
    """Reparte los kilómetros de la semana entre sus sesiones."""
    n_faciles, n_calidad = COMPOSICION[dias][bloque]

    km_calidad_total = round(km_total * CALIDAD_PCT, 1) if n_calidad else 0.0
    km_no_calidad = km_total - km_calidad_total

    km_largo = round(km_total * LARGO_PCT[distancia], 1)
    km_facil = (km_no_calidad - km_largo) / n_faciles

    # El largo tiene que ser la sesión más larga de la semana. En bloques con
    # pocas sesiones fáciles el reparto por porcentaje puede invertirlo, así
    # que se reparte el volumen no-calidad dando al largo una porción mayor.
    if km_facil > km_largo:
        km_facil = km_no_calidad / (n_faciles + PESO_LARGO)
        km_largo = km_no_calidad - km_facil * n_faciles

    sesiones: list[Sesion] = []
    dia = 0

    for _ in range(n_faciles):
        sesiones.append(_sesion(inicio, dia, "facil", km_facil))
        dia += 2

    for _ in range(n_calidad):
        sesiones.append(
            _sesion(inicio, dia, "calidad", km_calidad_total / n_calidad)
        )
        dia += 2

    sesiones.append(_sesion(inicio, dia, "largo", km_largo))

    return Semana(numero=numero, sesiones=tuple(sesiones), es_descarga=es_descarga)


def _sesion(inicio: date, desplazamiento: int, tipo: TipoSesion, km: float) -> Sesion:
    return Sesion(
        fecha=inicio + timedelta(days=desplazamiento),
        tipo=tipo,
        km=round(km, 1),
    )
