"""Cifrado de contraseñas.

Lo único que no se improvisa en todo el proyecto. Una contraseña guardada mal
no la arregla un parche después: ya salió de aquí.
"""

import pytest

from pacer.infrastructure.seguridad import ClaveInvalida, cifrar, coincide


def test_la_contrasena_no_se_guarda_nunca_en_claro() -> None:
    guardado = cifrar("correr-es-vida")

    assert "correr-es-vida" not in guardado


def test_la_misma_contrasena_da_hashes_distintos() -> None:
    """Sal aleatoria por contraseña: sin ella, dos personas con la misma clave
    tienen el mismo hash y una tabla precalculada las abre a las dos."""
    assert cifrar("misma-clave") != cifrar("misma-clave")


def test_reconoce_la_contrasena_correcta() -> None:
    assert coincide("correr-es-vida", cifrar("correr-es-vida"))


def test_rechaza_la_equivocada() -> None:
    assert not coincide("otra-cosa", cifrar("correr-es-vida"))


def test_distingue_mayusculas() -> None:
    assert not coincide("Correr-Fuerte", cifrar("correr-fuerte"))


def test_un_hash_corrupto_no_revienta_el_login() -> None:
    """Una fila a medio migrar no puede tumbar la app: se rechaza y ya."""
    for basura in ["", "no-es-un-hash", "scrypt$solo-una-parte", "a$b$c"]:
        assert not coincide("lo que sea", basura)


def test_una_contrasena_vacia_no_se_cifra() -> None:
    """Cifrarla la haría válida para entrar, que es justo lo que no queremos."""
    with pytest.raises(ClaveInvalida):
        cifrar("")


def test_una_contrasena_demasiado_corta_se_rechaza() -> None:
    with pytest.raises(ClaveInvalida) as rechazo:
        cifrar("1234")

    assert rechazo.value.razon


def test_el_formato_dice_con_que_se_cifro() -> None:
    """El día que se cambie de algoritmo hay que poder distinguir los viejos."""
    assert cifrar("correr-es-vida").startswith("scrypt$")
