"""Dos personas en la misma URL.

Esta es la garantía que sostiene poder compartir el enlace: antes toda visita
resolvía al primer corredor de la tabla, así que mandarle la dirección a alguien
era darle tu plan, tu nombre y tu conversación. Se prueba contra la API de
verdad, no contra el repositorio: la cookie es parte del contrato.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    carpeta = tmp_path_factory.mktemp("bd-sesiones")
    previo = dict(os.environ)
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{carpeta}/sesiones.db"
    os.environ["CALENTAR_VOZ"] = "false"
    os.environ["LANGFUSE_PUBLIC_KEY"] = ""
    os.environ["LANGFUSE_SECRET_KEY"] = ""
    os.environ["TELEGRAM_BOT_TOKEN"] = ""

    from pacer.interfaces.http import app as modulo

    yield modulo.app

    os.environ.clear()
    os.environ.update(previo)


def navegador(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    """Un TestClient nuevo = un frasco de cookies nuevo = otra persona."""
    return TestClient(app)


def test_la_primera_visita_recibe_su_cookie(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        respuesta = cliente.get("/api/plan")

        assert respuesta.status_code == 200
        assert cliente.cookies.get("pacer_sesion")


def test_dos_navegadores_no_comparten_carreras(app) -> None:  # type: ignore[no-untyped-def]
    """El fallo original, dicho en una línea: tu enlace era tu cuenta."""
    with navegador(app) as ana, navegador(app) as beto:
        ana.post("/api/carreras", json={
            "nombre": "La de Ana", "fecha": "2027-03-20", "distancia_km": 10,
        })

        assert [c["nombre"] for c in ana.get("/api/carreras").json()["carreras"]] == ["La de Ana"]
        assert beto.get("/api/carreras").json()["carreras"] == []


def test_el_mismo_navegador_conserva_lo_suyo(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        cliente.post("/api/carreras", json={
            "nombre": "Mi carrera", "fecha": "2027-05-02", "distancia_km": 21.1,
        })
        cliente.get("/api/plan")

        assert len(cliente.get("/api/carreras").json()["carreras"]) == 1


def test_borrar_el_plan_de_uno_no_toca_al_otro(app) -> None:  # type: ignore[no-untyped-def]
    """Lo que más miedo daba de compartir el enlace: que alguien borre tu plan."""
    with navegador(app) as ana, navegador(app) as beto:
        beto.post("/api/carreras", json={
            "nombre": "De Beto", "fecha": "2027-04-11", "distancia_km": 5,
        })

        ana.delete("/api/plan")

        assert len(beto.get("/api/carreras").json()["carreras"]) == 1


# --- cuenta --------------------------------------------------------------


def test_registrarse_conserva_lo_que_ya_habias_hecho(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        cliente.post("/api/carreras", json={
            "nombre": "Antes de la cuenta", "fecha": "2027-06-06", "distancia_km": 10,
        })

        alta = cliente.post("/api/cuenta/registro", json={
            "email": "ana@ejemplo.mx", "password": "correr-es-vida",
        })

        assert alta.status_code == 200
        assert cliente.get("/api/cuenta").json()["email"] == "ana@ejemplo.mx"
        assert len(cliente.get("/api/carreras").json()["carreras"]) == 1


def test_entrar_desde_otro_navegador_trae_tu_plan(app) -> None:  # type: ignore[no-untyped-def]
    """Para eso existe la cuenta: cambiar de teléfono sin perder nada."""
    with navegador(app) as casa, navegador(app) as movil:
        casa.post("/api/carreras", json={
            "nombre": "Maratón de Ari", "fecha": "2027-09-19", "distancia_km": 42.2,
        })
        casa.post("/api/cuenta/registro", json={
            "email": "ari@ejemplo.mx", "password": "clave-bien-larga",
        })

        assert movil.get("/api/carreras").json()["carreras"] == []

        entrada = movil.post("/api/cuenta/entrar", json={
            "email": "ari@ejemplo.mx", "password": "clave-bien-larga",
        })

        assert entrada.status_code == 200
        assert [c["nombre"] for c in movil.get("/api/carreras").json()["carreras"]] == [
            "Maratón de Ari"
        ]


def test_la_contrasena_equivocada_no_entra(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        cliente.post("/api/cuenta/registro", json={
            "email": "beto@ejemplo.mx", "password": "clave-bien-larga",
        })

    with navegador(app) as intruso:
        respuesta = intruso.post("/api/cuenta/entrar", json={
            "email": "beto@ejemplo.mx", "password": "la-que-sea",
        })

        assert respuesta.status_code == 401
        assert intruso.get("/api/cuenta").json()["email"] is None


def test_un_correo_inexistente_falla_igual_que_una_clave_mala(app) -> None:  # type: ignore[no-untyped-def]
    """Distinguirlos convertiría el login en un buscador de correos registrados."""
    with navegador(app) as cliente:
        cliente.post("/api/cuenta/registro", json={
            "email": "existe@ejemplo.mx", "password": "clave-bien-larga",
        })

    with navegador(app) as otro:
        mala_clave = otro.post("/api/cuenta/entrar", json={
            "email": "existe@ejemplo.mx", "password": "incorrecta-pero-larga",
        })
        sin_cuenta = otro.post("/api/cuenta/entrar", json={
            "email": "no-existe@ejemplo.mx", "password": "incorrecta-pero-larga",
        })

        assert mala_clave.status_code == sin_cuenta.status_code == 401
        assert mala_clave.json() == sin_cuenta.json()


def test_el_correo_ya_registrado_se_rechaza(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as uno:
        uno.post("/api/cuenta/registro", json={
            "email": "repetido@ejemplo.mx", "password": "clave-bien-larga",
        })

    with navegador(app) as otro:
        respuesta = otro.post("/api/cuenta/registro", json={
            "email": "repetido@ejemplo.mx", "password": "otra-clave-larga",
        })

        assert respuesta.status_code == 409


def test_una_contrasena_corta_se_rechaza_con_motivo(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        respuesta = cliente.post("/api/cuenta/registro", json={
            "email": "corta@ejemplo.mx", "password": "1234",
        })

        assert respuesta.status_code == 400
        assert respuesta.json()["explicacion"]


def test_salir_deja_el_navegador_en_blanco(app) -> None:  # type: ignore[no-untyped-def]
    with navegador(app) as cliente:
        cliente.post("/api/carreras", json={
            "nombre": "Con cuenta", "fecha": "2027-07-07", "distancia_km": 10,
        })
        cliente.post("/api/cuenta/registro", json={
            "email": "salgo@ejemplo.mx", "password": "clave-bien-larga",
        })

        cliente.post("/api/cuenta/salir")
        cliente.cookies.clear()

        assert cliente.get("/api/cuenta").json()["email"] is None
        assert cliente.get("/api/carreras").json()["carreras"] == []
