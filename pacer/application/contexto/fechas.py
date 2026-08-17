"""Interpretación de fechas dichas en español.

El modelo transcribe lo que la persona dijo, y la gente no habla en ISO. Ser
estricto acá provoca un bucle: el campo no se guarda, el guardarrail sigue
pidiéndolo, y el coach vuelve a preguntar con otro formato. Se declara ISO en
el esquema y se acepta lo que llega.
"""

import re
from datetime import date

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_CON_BARRAS = re.compile(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$")
_HABLADA = re.compile(r"^(\d{1,2})\s*(?:de\s+)?([a-záéíóúñ]+)\s*(?:de\s+)?(\d{4})$")


DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
NOMBRES_DE_MES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def en_palabras(fecha: date) -> str:
    """Una fecha dicha entera: día de la semana, día, mes y año.

    Todo lo que le llegue al modelo pasa por aquí. Darle un ISO pelado es
    pedirle que calcule qué día de la semana cae, y calculando se equivoca:
    llegó a ofrecer "el martes 19" siendo miércoles.
    """
    return (
        f"{DIAS[fecha.weekday()]} {fecha.day} de "
        f"{NOMBRES_DE_MES[fecha.month - 1]} de {fecha.year}"
    )


def interpretar_fecha(texto: str) -> date | None:
    """Traduce una fecha escrita de varias formas. `None` si no se entiende."""
    limpio = (texto or "").strip().lower()
    if not limpio:
        return None

    for patron, orden in (
        (_ISO, ("anio", "mes", "dia")),
        (_CON_BARRAS, ("dia", "mes", "anio")),
    ):
        coincide = patron.match(limpio)
        if coincide:
            partes = dict(zip(orden, (int(g) for g in coincide.groups())))
            return _armar(partes["anio"], partes["mes"], partes["dia"])

    hablada = _HABLADA.match(limpio)
    if hablada:
        dia, nombre_mes, anio = hablada.groups()
        mes = MESES.get(_sin_acentos(nombre_mes))
        if mes is not None:
            return _armar(int(anio), mes, int(dia))

    return None


def _armar(anio: int, mes: int, dia: int) -> date | None:
    """Una fecha imposible es un dato que no entendimos, no una excepción."""
    try:
        return date(anio, mes, dia)
    except ValueError:
        return None


def _sin_acentos(palabra: str) -> str:
    for con, sin in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        palabra = palabra.replace(con, sin)
    return palabra
