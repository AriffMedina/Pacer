"""Unir el navegador con el chat de Telegram.

El problema que resuelve: cada canal creaba su propio corredor. Armabas el
plan hablando por la web, le escribías al bot y el bot no sabía quién eras.
Y como los recordatorios salen de `corredor.telegram_chat_id`, quien solo
usaba la web no recibía ninguno jamás.

La forma más simple de atar dos canales sin pedir credenciales es un código
corto que se dicta: la web lo muestra, el corredor se lo manda al bot, y el
bot une los dos. Aquí vive solo lo que es regla y no depende de nada de
fuera: cómo se ve el código y hasta cuándo sirve.
"""

import secrets
from datetime import datetime, timedelta

# Seis dígitos: se dictan de memoria y se teclean en un móvil sin cambiar de
# teclado. Solo números a propósito — una I y un 1 dictados en voz alta son
# el mismo sonido, y el corredor teclea lo que creyó oír.
LARGO = 6

# Diez minutos es tiempo de sobra para abrir Telegram y pegar el código, y
# poco para que uno olvidado siga sirviéndole a alguien más.
DURACION = timedelta(minutes=10)


def generar_codigo() -> str:
    """Un código nuevo, imposible de adivinar.

    `secrets` y no `random`: esto abre el acceso a la conversación y al plan
    de una persona. Un generador predecible convierte el código en un trámite
    para quien quiera entrar.

    El `zfill` no es cosmético: sin él, un número que empieza en cero se
    imprime con cinco dígitos y el corredor teclea lo que ve, que no entra.
    """
    return str(secrets.randbelow(10**LARGO)).zfill(LARGO)


def vence_en(ahora: datetime) -> datetime:
    return ahora + DURACION


def vigente(caduca: datetime | None, ahora: datetime) -> bool:
    """Si el código todavía sirve.

    `None` es "nunca pidió código" y se responde igual que uno expirado: no
    sirve. Distinguirlos solo daría al de fuera una forma de preguntar si
    alguien tiene un canje pendiente.

    En el borde exacto ya está muerto. Un código de un solo uso que aguanta
    "un ratito más" es un código que alguien puede canjear por ti.
    """
    return caduca is not None and ahora < caduca
