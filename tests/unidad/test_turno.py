from fastapi.testclient import TestClient

from pacer.interfaces.http.app import app

cliente = TestClient(app)


def test_turno_acepta_audio_y_devuelve_audio() -> None:
    respuesta = cliente.post(
        "/api/turno",
        files={"audio": ("turno.webm", b"bytes-de-prueba", "audio/webm")},
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("audio/")
    assert len(respuesta.content) > 0


def test_turno_acepta_el_formato_de_safari() -> None:
    respuesta = cliente.post(
        "/api/turno",
        files={"audio": ("turno.mp4", b"bytes-de-prueba", "audio/mp4")},
    )

    assert respuesta.status_code == 200
