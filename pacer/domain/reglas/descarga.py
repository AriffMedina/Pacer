"""Parámetros de descarga. Cifras tomadas de `paramethers.md` §6 (grado C).

`FACTOR_VOLUMEN` se reutiliza para el ajuste reactivo del ajustador: se recorta
volumen, nunca días ni intensidad. Es el mismo principio del tapering aplicado
en pequeño.
"""

FACTOR_VOLUMEN = 0.65
CADA_N_SEMANAS = 4
CADA_N_SEMANAS_PRINCIPIANTE = 3
