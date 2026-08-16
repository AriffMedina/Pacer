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
        self, motivo: str, minimo: int | None = None, maximo: int | None = None
    ) -> None:
        super().__init__(motivo)
        self.motivo = motivo
        self.minimo = minimo
        self.maximo = maximo


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
            f"{distancia} no es una meta segura para alguien de nivel {nivel}"
        )

    maximo = SEMANAS[distancia]["max"]

    if semanas < minimo:
        raise PlanImposible(
            f"{distancia} en nivel {nivel} necesita al menos {minimo} semanas",
            minimo=minimo,
            maximo=maximo,
        )
    if semanas > maximo:
        raise PlanImposible(
            f"un plan de {distancia} no se extiende más de {maximo} semanas",
            minimo=minimo,
            maximo=maximo,
        )


def descarga_cada(nivel: str) -> int:
    return DESCARGA_CADA_N_SEMANAS[nivel]


def descarga_en_base(nivel: str) -> bool:
    return DESCARGA_EN_BLOQUE_BASE[nivel]
