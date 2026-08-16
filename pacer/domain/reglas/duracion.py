"""Duración válida de un plan y compuerta dura. Cifras de `paramethers.md` §2 y §9.

La compuerta no negocia: si no hay semanas suficientes para el nivel, no se
produce un plan comprimido. Se devuelven alternativas — mover la fecha o bajar
la distancia — porque comprimir un plan en un dominio de salud no es un
compromiso, es un riesgo.
"""

SEMANAS = {
    "5k": {"min": 6, "def": 8, "max": 12},
    "10k": {"min": 8, "def": 10, "max": 16},
    "21k": {"min": 10, "def": 12, "max": 22},
    "maraton": {"min": 12, "def": 16, "max": 24},
}

# None significa rechazo incondicional, no "sin mínimo".
SEMANAS_MIN_POR_NIVEL: dict[str, dict[str, int | None]] = {
    "5k": {"nuevo": 10, "principiante": 8, "intermedio": 6, "avanzado": 6},
    "10k": {"nuevo": 14, "principiante": 10, "intermedio": 8, "avanzado": 8},
    "21k": {"nuevo": 20, "principiante": 14, "intermedio": 10, "avanzado": 10},
    "maraton": {"nuevo": None, "principiante": 20, "intermedio": 14, "avanzado": 12},
}

# Volumen semanal mínimo para arrancar el plan (§2.3). Por debajo se anteponen
# semanas de base.
KM_ARRANQUE_MIN = {"5k": 12, "10k": 18, "21k": 25, "maraton": 32}

# Techo duro de volumen semanal: el extremo alto del "pico típico recreativo"
# de §2.3. Al alcanzarlo la tendencia deja de crecer y se sostiene, que es lo
# que hace un entrenador: no se sube para siempre.
PICO_MAX_KM = {"5k": 40, "10k": 50, "21k": 60, "maraton": 70}

DESCARGA_CADA_N_SEMANAS = {
    "nuevo": 3,
    "principiante": 3,
    "intermedio": 4,
    "avanzado": 4,
}

# El bloque base opera como descarga implícita solo para quien ya corre con
# consistencia. Quien empieza construye dentro del base y ahí sí descansa.
DESCARGA_EN_BLOQUE_BASE = {
    "nuevo": True,
    "principiante": True,
    "intermedio": False,
    "avanzado": False,
}


class PlanImposible(Exception):
    """No existe un plan seguro para esta combinación."""

    def __init__(
        self,
        motivo: str,
        minimo: int | None = None,
        maximo: int | None = None,
        razon: str = "",
    ) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.minimo = minimo
        self.maximo = maximo
        self.razon = razon
        """El porqué en lenguaje humano, para que el coach lo explique.

        Sin esto el modelo solo sabe que una regla lo bloqueó, y termina
        diciendo "el sistema no me deja" — que no le sirve de nada a nadie.
        """


def validar_duracion(distancia: str, nivel: str, semanas: int) -> None:
    """Lanza `PlanImposible` si la combinación no admite un plan seguro."""
    if distancia not in SEMANAS:
        raise PlanImposible(f"distancia desconocida: {distancia}")
    if nivel not in DESCARGA_CADA_N_SEMANAS:
        raise PlanImposible(f"nivel desconocido: {nivel}")

    minimo = SEMANAS_MIN_POR_NIVEL[distancia][nivel]

    # Se ataja antes de comparar: `semanas < None` es TypeError, no False.
    if minimo is None:
        raise PlanImposible(
            f"{distancia} no es una meta segura para alguien de nivel {nivel}",
            razon=(
                "Correr 42 kilómetros partiendo de cero es la combinación con "
                "más riesgo de lesión que hay en este deporte. No existe un "
                "número de semanas que lo vuelva seguro sin haber corrido "
                "antes de forma constante: el problema no es el tiempo, es la "
                "base que todavía no está."
            ),
        )

    maximo = SEMANAS[distancia]["max"]

    if semanas < minimo:
        raise PlanImposible(
            f"{distancia} en nivel {nivel} necesita al menos {minimo} semanas",
            minimo=minimo,
            maximo=maximo,
            razon=(
                f"El cuerpo tarda en adaptarse: la carga sube poco a poco, "
                f"semana a semana. Para {distancia} desde un nivel {nivel} eso "
                f"toma {minimo} semanas como mínimo. Comprimirlo significa "
                f"subir más rápido de lo que el cuerpo aguanta, y así es "
                f"exactamente como aparecen las lesiones."
            ),
        )
    if semanas > maximo:
        raise PlanImposible(
            f"un plan de {distancia} no se extiende más de {maximo} semanas",
            minimo=minimo,
            maximo=maximo,
            razon=(
                f"Un bloque de entrenamiento más largo que {maximo} semanas "
                f"deja de rendir: se llega al pico demasiado pronto y se pierde "
                f"forma antes de la carrera."
            ),
        )


def descarga_cada(nivel: str) -> int:
    return DESCARGA_CADA_N_SEMANAS[nivel]


def descarga_en_base(nivel: str) -> bool:
    return DESCARGA_EN_BLOQUE_BASE[nivel]
