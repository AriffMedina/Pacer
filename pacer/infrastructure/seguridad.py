"""Cifrado de contraseñas y llaves de sesión.

`hashlib.scrypt` y no una librería: scrypt es un KDF de verdad —lento y caro en
memoria a propósito, que es lo que frena a quien roba la tabla— y viene en la
librería estándar. Una dependencia menos que auditar en un proyecto de fin de
semana, sin bajar el listón.

Lo que NO se hace aquí, y está fuera de alcance a sabiendas: recuperación de
contraseña, segundo factor y bloqueo por intentos. Eso es producto, no cifrado.
"""

import hashlib
import secrets

ALGORITMO = "scrypt"

# Coste de scrypt. n=2^14 con r=8 pide ~16 MB por intento: imperceptible al
# entrar, caro de multiplicar por millones si se filtra la base.
N = 2**14
R = 8
P = 1
LARGO = 32
BYTES_DE_SAL = 16

# No es política de seguridad seria, es el mínimo para que no se cuele una
# contraseña de un carácter. Lo serio sería medir entropía; esto es un piloto.
MINIMO = 8


class ClaveInvalida(Exception):
    """La contraseña no se puede aceptar tal cual viene."""

    def __init__(self, razon: str) -> None:
        super().__init__(razon)
        self.razon = razon


def cifrar(clave: str) -> str:
    """Devuelve `scrypt$sal$hash`. La contraseña en claro no sale de aquí."""
    if len(clave) < MINIMO:
        raise ClaveInvalida(
            f"La contraseña necesita al menos {MINIMO} caracteres."
        )

    sal = secrets.token_bytes(BYTES_DE_SAL)
    return f"{ALGORITMO}${sal.hex()}${_derivar(clave, sal).hex()}"


def coincide(clave: str, guardado: str | None) -> bool:
    """¿Es esta la contraseña? Nunca lanza: un hash roto es un `no`.

    Una fila a medio migrar o un valor corrupto no pueden tumbar el login de
    todo el mundo; se rechaza ese intento y se sigue.
    """
    if not guardado:
        return False

    try:
        algoritmo, sal, esperado = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        calculado = _derivar(clave, bytes.fromhex(sal))
    except (ValueError, TypeError):
        return False

    # compare_digest y no `==`: comparar byte a byte filtra por tiempo cuántos
    # coinciden, y con eso se reconstruye un hash a ciegas.
    return secrets.compare_digest(calculado.hex(), esperado)


def _derivar(clave: str, sal: bytes) -> bytes:
    return hashlib.scrypt(
        clave.encode("utf-8"), salt=sal, n=N, r=R, p=P, dklen=LARGO
    )


def llave_de_sesion() -> str:
    """Identificador de navegador. Aleatorio de verdad, no un contador."""
    return secrets.token_urlsafe(24)
