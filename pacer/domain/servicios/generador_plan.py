"""Generador determinístico de planes.

Lo calcula código probado, nunca el modelo de lenguaje. El modelo traduce,
pregunta y explica; no decide la carga.

Cifras de `paramethers.md`. El 20% de calidad se reparte sobre kilómetros, no
sobre número de sesiones: es la métrica correcta (§5).
"""

from dataclasses import replace
from datetime import date, timedelta

from pacer.domain.entidades.plan import Plan, Semana, Sesion, TipoSesion
from pacer.domain.reglas.descarga import FACTOR_VOLUMEN
from pacer.domain.reglas.duracion import (
    PICO_MAX_KM,
    descarga_cada,
    descarga_en_base,
    validar_duracion,
)
from pacer.domain.reglas.largo import LARGO_PCT, largo_maximo_permitido
from pacer.domain.reglas.periodizacion import repartir_bloques
from pacer.domain.reglas.progresion import PROGRESION_SEMANAL_MAX

CALIDAD_PCT = 0.20
MARGEN_DE_REDONDEO = 1.01
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
    nivel: str,
    semanas: int,
    km_semana: int,
    dias: int,
    inicio: date,
) -> Plan:
    """Construye un plan completo a partir del perfil del corredor.

    `inicio` se inyecta: el dominio no lee el reloj.
    Lanza `PlanImposible` si la combinación no admite un plan seguro.
    """
    if dias not in COMPOSICION:
        raise ValueError(f"días no soportados: {dias} (se admiten 3 o 4)")

    validar_duracion(distancia, nivel, semanas)

    bloques = repartir_bloques(distancia, semanas)
    primer_dia = inicio

    volumenes = _volumenes_por_semana(bloques, km_semana, nivel, distancia)
    construidas = []

    numero = 0
    largos_recientes: list[float] = []

    for bloque in ORDEN_BLOQUES:
        for _ in range(bloques[bloque]):
            volumen, es_descarga = volumenes[numero]
            semana = _armar_semana(
                numero=numero + 1,
                bloque=bloque,
                km_total=volumen,
                es_descarga=es_descarga,
                dias=dias,
                distancia=distancia,
                inicio=primer_dia + timedelta(weeks=numero),
            )
            semana = _frenar_por_el_largo(semana, distancia, largos_recientes)

            largo = semana.largo
            largos_recientes.append(largo.km if largo else 0.0)
            construidas.append(semana)
            numero += 1

    return Plan(version=1, semanas=tuple(_bajar_desde_la_carga_real(construidas)))


def _bajar_desde_la_carga_real(semanas: list[Semana]) -> list[Semana]:
    """El tapering baja desde donde el corredor está, no desde la tendencia.

    Si la restricción del largo recortó la semana pico, el taper calculado
    sobre la tendencia teórica puede quedar POR ENCIMA de la última semana de
    carga. Un taper que sube no es un taper.
    """
    de_carga = [s for s in semanas if s.bloque != "tapering"]
    taper = [s for s in semanas if s.bloque == "tapering"]
    if not de_carga or not taper:
        return semanas

    techo = de_carga[-1].km_total
    # La primera semana de taper debe quedar en su fracción del pico REAL. Se
    # deduce el factor de ahí y se aplica a todas por igual, para que la curva
    # descendente del taper se conserve.
    objetivo = techo * (1 - TAPER_REDUCCION_VOLUMEN / len(taper))
    if taper[0].km_total <= objetivo:
        return semanas

    factor = objetivo / taper[0].km_total

    return [
        replace(
            semana,
            sesiones=tuple(
                replace(s, km=round(s.km * factor, 1)) for s in semana.sesiones
            ),
        )
        if semana.bloque == "tapering"
        else semana
        for semana in semanas
    ]


def _volumenes_por_semana(
    bloques: dict[str, int], km_inicial: int, nivel: str, distancia: str
) -> list[tuple[float, bool]]:
    """Calcula el volumen de cada semana y marca cuáles son de descarga."""
    volumenes: list[tuple[float, bool]] = []
    # La tendencia es la línea de progresión. Una descarga es un bajón puntual
    # POR DEBAJO de la tendencia, no un retroceso de la tendencia misma: si la
    # progresión continuara desde el valor reducido, cada ciclo cerraría en
    # 1.10 × 1.10 × 0.65 = 0.79 y el plan iría hacia abajo.
    tendencia = float(km_inicial)
    # Techo duro: la carga deja de crecer al llegar al pico de la distancia y
    # se sostiene. Un entrenador no sube el volumen indefinidamente.
    #
    # Si el corredor YA entrena por encima de ese pico, el techo es su volumen
    # actual: el generador está para no empujarlo más allá de lo típico, no
    # para bajarle la carga a quien ya la sostiene.
    techo = max(float(PICO_MAX_KM[distancia]), tendencia)
    cada = descarga_cada(nivel)
    en_base = descarga_en_base(nivel)
    indice = 0

    for bloque in ("base", "construccion", "pico"):
        for _ in range(bloques[bloque]):
            indice += 1
            # La exención del bloque base depende del nivel (§6 v1.1): quien ya
            # corre con consistencia usa el base como descarga implícita.
            permitida = en_base or bloque != "base"
            es_descarga = permitida and indice % cada == 0

            if es_descarga:
                volumen = tendencia * FACTOR_VOLUMEN
            else:
                if indice > 1:
                    tendencia = min(tendencia * PROGRESION_SEMANAL_MAX, techo)
                volumen = tendencia
            volumenes.append((round(volumen, 1), es_descarga))

    # El tapering baja de forma progresiva hasta el 50% del pico (§4).
    pico = tendencia
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

    return Semana(
        numero=numero,
        sesiones=tuple(sesiones),
        es_descarga=es_descarga,
        bloque=bloque,
    )


def _frenar_por_el_largo(
    semana: Semana, distancia: str, largos_recientes: list[float]
) -> Semana:
    """Recorta la semana entera si su long run se pasa del techo permitido.

    Se escala TODA la semana en la misma proporción, no solo el largo. Si la
    salida larga no puede crecer, el volumen semanal tampoco debería: recortar
    únicamente el largo dejaría una semana con la carga alta repartida en
    sesiones fáciles, que es la misma carga por otro camino.

    Escalar preserva el resto de invariantes: el reparto fácil/calidad es una
    proporción, y el largo sigue siendo la sesión más larga.
    """
    largo = semana.largo
    if largo is None or largo.km <= 0:
        return semana

    permitido = largo_maximo_permitido(distancia, largos_recientes)

    # El margen del 1% distingue un recorte real de un desborde por redondeo:
    # el largo crece justo al 10% y se pasa por centésimas casi cada semana.
    # Sin esto, todas las semanas quedarían marcadas y la bandera no diría nada.
    if largo.km <= permitido * MARGEN_DE_REDONDEO:
        return semana

    factor = permitido / largo.km
    return replace(
        semana,
        recortada=True,
        sesiones=tuple(
            replace(sesion, km=round(sesion.km * factor, 1))
            for sesion in semana.sesiones
        ),
    )


def _sesion(inicio: date, desplazamiento: int, tipo: TipoSesion, km: float) -> Sesion:
    return Sesion(
        fecha=inicio + timedelta(days=desplazamiento),
        tipo=tipo,
        km=round(km, 1),
    )
