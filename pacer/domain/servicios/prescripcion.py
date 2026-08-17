"""Qué hacer exactamente en una sesión, y por qué.

El plan dice "calidad, 8.8 km". A un corredor eso no le dice nada: no sabe si
son series, a qué ritmo, ni cuánto descansar entre ellas. Sin esto, la mitad
del plan es un número que cada quien interpreta como puede —y casi siempre lo
interpreta corriendo todo demasiado rápido.

Esto es CÓDIGO, no prompt, por la misma razón que el generador: es carga de
entrenamiento. El modelo lee esta prescripción y la explica; no la inventa. Un
LLM improvisando series para alguien con una rodilla lastimada es exactamente
el fallo que este proyecto no se puede permitir.

Función pura sobre la sesión, el nivel y el bloque. Nada de reloj ni de base.
"""

from dataclasses import dataclass

from pacer.domain.entidades.perfil import Nivel
from pacer.domain.entidades.plan import Sesion

# Reparto de una sesión de calidad. El trabajo fuerte es la mitad; el resto es
# lo que hace que se pueda repetir la semana que viene sin romperse.
PARTE_CALENTAMIENTO = 0.25
PARTE_VUELTA = 0.25

# Por debajo de esto no hay sesión que partir en tres: se corre y ya.
KM_MINIMOS_PARA_PARTIR = 3.0

# En pico el fondo termina a ritmo de carrera. Un tercio es suficiente para el
# estímulo específico sin convertir el fondo en una competencia.
PARTE_FINAL_EN_PICO = 0.33

QUE_EMPIEZAN = ("nuevo", "principiante")


@dataclass(frozen=True)
class Tramo:
    titulo: str
    detalle: str
    km: float


@dataclass(frozen=True)
class Prescripcion:
    resumen: str
    tramos: tuple[Tramo, ...]
    esfuerzo: str
    porque: str


SUAVE = "Suave: tienes que poder hablar en frases completas (3-4 de 10)."
FIRME = "Firme pero sostenible: frases cortas, no palabras sueltas (7-8 de 10)."
CONSTANTE = "Suave y constante de principio a fin (4-5 de 10)."

PORQUE = {
    "facil": (
        "El kilometraje suave es el que construye la base aeróbica. Correrlo "
        "rápido no lo mejora: solo te deja cansado para la sesión que sí importa."
    ),
    "largo": (
        "El fondo enseña a tu cuerpo a usar grasa como combustible y prepara "
        "las piernas para el tiempo que vas a estar de pie el día de la carrera."
    ),
    "calidad_base": (
        "Todavía no hay fondo para series. Estos progresivos despiertan la "
        "zancada y te preparan para el trabajo fuerte que viene después."
    ),
    "calidad_construccion": (
        "Las series suben tu techo: es el bloque donde de verdad te haces más "
        "rápido. Por eso van con calentamiento y vuelta a la calma completos."
    ),
    "calidad_pico": (
        "Ya no se busca subir el techo, se ensaya la carrera. Correr a ritmo "
        "objetivo enseña al cuerpo y a la cabeza cómo se va a sentir ese día."
    ),
    "calidad_tapering": (
        "Poco volumen y algo de ritmo: mantiene la sensación de velocidad "
        "mientras descansas. En esta semana ya no se gana forma, se conserva."
    ),
}


def prescribir(
    sesion: Sesion, nivel: Nivel | None, bloque: str
) -> Prescripcion:
    """Traduce una sesión del plan a instrucciones que se pueden seguir."""
    km = round(sesion.km, 1)

    if sesion.tipo == "facil":
        return _facil(km)
    if sesion.tipo == "largo":
        return _largo(km, bloque)
    return _calidad(km, nivel, bloque)


def _facil(km: float) -> Prescripcion:
    return Prescripcion(
        resumen=f"Rodaje suave de {km} km",
        tramos=(
            Tramo(
                titulo="Rodaje continuo",
                detalle=(
                    "Corre los "
                    f"{km} km a ritmo cómodo, sin cambios. Si no puedes hablar "
                    "mientras corres, vas demasiado rápido: bájale."
                ),
                km=km,
            ),
        ),
        esfuerzo=SUAVE,
        porque=PORQUE["facil"],
    )


def _largo(km: float, bloque: str) -> Prescripcion:
    # En tapering el fondo se acorta y NO se acelera. Meterle ritmo en esa
    # semana es el error clásico que llega cansado al día de la carrera.
    if bloque == "pico" and km >= KM_MINIMOS_PARA_PARTIR:
        final = round(km * PARTE_FINAL_EN_PICO, 1)
        inicio = round(km - final, 1)
        return Prescripcion(
            resumen=f"Fondo de {km} km terminando fuerte",
            tramos=(
                Tramo(
                    titulo="Primera parte",
                    detalle=f"{inicio} km suaves, sin mirar el reloj.",
                    km=inicio,
                ),
                Tramo(
                    titulo="Final progresivo",
                    detalle=(
                        f"Últimos {final} km a ritmo de carrera. Vas a llegar "
                        "cansado: de eso se trata."
                    ),
                    km=final,
                ),
            ),
            esfuerzo="Suave y al final firme. Termina con la sensación de que podías más.",
            porque=PORQUE["largo"],
        )

    return Prescripcion(
        resumen=f"Fondo de {km} km",
        tramos=(
            Tramo(
                titulo="Continuo suave",
                detalle=(
                    f"{km} km a ritmo cómodo y constante. La distancia es el "
                    "objetivo; el ritmo, no."
                ),
                km=km,
            ),
        ),
        esfuerzo=CONSTANTE,
        porque=PORQUE["largo"],
    )


def _calidad(km: float, nivel: Nivel | None, bloque: str) -> Prescripcion:
    if km < KM_MINIMOS_PARA_PARTIR:
        # Partir 2 km en tres tramos da tramos de 500 m. No es una sesión.
        return Prescripcion(
            resumen=f"Soltura de {km} km",
            tramos=(
                Tramo(
                    titulo="Continuo con progresivos",
                    detalle=(
                        f"{km} km suaves y, al terminar, 4 progresivos de 20 "
                        "segundos acelerando poco a poco."
                    ),
                    km=km,
                ),
            ),
            esfuerzo=SUAVE,
            porque=PORQUE["calidad_base"],
        )

    calentamiento = round(km * PARTE_CALENTAMIENTO, 1)
    vuelta = round(km * PARTE_VUELTA, 1)
    # El principal absorbe el redondeo para que los tramos sumen la sesión.
    principal = round(km - calentamiento - vuelta, 1)

    titulo, detalle, resumen, esfuerzo = _trabajo_principal(principal, nivel, bloque)

    return Prescripcion(
        resumen=resumen,
        tramos=(
            Tramo(
                titulo="Calentamiento",
                detalle=(
                    f"{calentamiento} km trotando muy suave. Entrar en frío al "
                    "trabajo fuerte es como se lesiona la gente."
                ),
                km=calentamiento,
            ),
            Tramo(titulo=titulo, detalle=detalle, km=principal),
            Tramo(
                titulo="Vuelta a la calma",
                detalle=f"{vuelta} km trotando suave hasta que la respiración vuelva a la normalidad.",
                km=vuelta,
            ),
        ),
        esfuerzo=esfuerzo,
        porque=PORQUE.get(f"calidad_{bloque}", PORQUE["calidad_base"]),
    )


def _trabajo_principal(
    km: float, nivel: Nivel | None, bloque: str
) -> tuple[str, str, str, str]:
    """El corazón de la sesión: qué se hace, cómo se descansa y a qué ritmo."""
    if bloque == "pico":
        return (
            "Ritmo de carrera",
            f"{km} km seguidos a ritmo de carrera, sin pausas.",
            f"{km} km a ritmo de carrera",
            "Firme y sostenido: el ritmo que quieres el día de la carrera.",
        )

    if bloque == "tapering":
        bloques = max(2, min(4, round(km / 0.8)))
        return (
            "Recordatorio de ritmo",
            f"{bloques} × 3 minutos a ritmo de carrera con 2 minutos de trote suave entre cada uno.",
            f"{bloques} bloques cortos a ritmo de carrera",
            "Firme, pero sin vaciarte. Esta semana ya no se gana forma.",
        )

    if bloque == "construccion":
        return _series(km, nivel)

    # base, o un plan viejo sin bloque: soltura antes que intensidad.
    return (
        "Progresivos",
        (
            f"{km} km suaves y dentro de ellos 6 progresivos de 20 segundos: "
            "acelera poco a poco hasta ir rápido y suelta. Recupera caminando."
        ),
        f"{km} km con 6 progresivos",
        SUAVE,
    )


def _series(km: float, nivel: Nivel | None) -> tuple[str, str, str, str]:
    """Series. La forma cambia con el nivel, no solo el número de repeticiones.

    A quien empieza se le dan cortas y con pausa CAMINANDO: trotar la
    recuperación supone una base aeróbica que todavía no tiene, y termina
    haciendo la serie siguiente peor que la anterior.
    """
    if nivel in QUE_EMPIEZAN:
        repeticiones = max(2, round(km / 0.4))
        return (
            "Series cortas",
            (
                f"{repeticiones} × 400 metros fuertes, caminando 90 segundos "
                "entre cada una hasta recuperar el aire."
            ),
            f"{repeticiones} × 400 m",
            FIRME,
        )

    repeticiones = max(2, round(km))
    return (
        "Series",
        (
            f"{repeticiones} × 1 km fuerte, trotando 2 minutos suaves entre "
            "cada uno. Todos al mismo ritmo: si el último es el más lento, "
            "empezaste demasiado rápido."
        ),
        f"{repeticiones} × 1 km",
        FIRME,
    )
