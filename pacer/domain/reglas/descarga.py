"""Factor de descarga. Cifra de `paramethers.md` §6 (grado C).

La cadencia y la exención del bloque base dependen del nivel y viven en
`duracion.py`. Acá queda solo el factor, que es el mismo para todos.

`FACTOR_VOLUMEN` se reutiliza en el ajustador reactivo: se recorta volumen,
nunca días ni intensidad. Es el principio del tapering aplicado en pequeño.
"""

FACTOR_VOLUMEN = 0.65
MANTENER_CALIDAD = True
