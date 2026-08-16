"""Reparto del plan en bloques. Cifras de `paramethers.md` §3 (grado C).

El tapering se reserva primero, en semanas absolutas, porque es el único
bloque con respaldo grado A. El residuo del reparto va a base; si el plan es
corto se sacrifica pico, nunca tapering.
"""

TAPER_SEMANAS = {"5k": 1, "10k": 1, "21k": 2, "maraton": 3}
PROPORCION_CONSTRUCCION = 0.45
PROPORCION_PICO = 0.20


def repartir_bloques(distancia: str, semanas_totales: int) -> dict[str, int]:
    """Reparte las semanas del plan entre base, construcción, pico y tapering."""
    if distancia not in TAPER_SEMANAS:
        raise ValueError(f"distancia desconocida: {distancia}")

    tapering = TAPER_SEMANAS[distancia]
    restantes = semanas_totales - tapering
    if restantes < 1:
        raise ValueError(
            f"{semanas_totales} semanas no alcanzan para {distancia}: "
            f"el tapering solo ya ocupa {tapering}"
        )

    construccion = int(restantes * PROPORCION_CONSTRUCCION)
    pico = int(restantes * PROPORCION_PICO)
    base = restantes - construccion - pico

    return {
        "base": base,
        "construccion": construccion,
        "pico": pico,
        "tapering": tapering,
    }
