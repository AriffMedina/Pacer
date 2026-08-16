"""El endpoint completo, con adaptadores falsos.

Ni Groq ni Polly ni Bedrock se tocan aquí, y la base es un archivo temporal:
un test que le escribe a la base real o gasta llamadas de API no es un test.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pacer.domain.puertos.llm import RespuestaLLM
from pacer.domain.puertos.voz import Transcripcion


class STTFalso:
    def __init__(self, texto: str = "quiero correr un medio maratón") -> None:
        self.texto = texto

    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion:
        return Transcripcion(texto=self.texto, duracion_s=2.0, palabras_por_s=2.5)


class TTSFalso:
    def sintetizar(self, texto: str) -> bytes:
        return b"mp3-de-mentira"


class LLMFalso:
    def conversar(
        self, sistema: str, mensajes: list[dict[str, Any]], herramientas: dict[str, Any]
    ) -> RespuestaLLM:
        return RespuestaLLM(
            texto="¿Para cuándo es tu carrera?",
            llamadas=(),
            mensaje={"role": "assistant"},
        )


@pytest.fixture
def cliente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Gana sobre el .env: pydantic-settings prioriza el entorno.
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/prueba.db")

    from pacer.interfaces.http import app as modulo

    modulo.sesion.perfil = type(modulo.sesion.perfil)()
    modulo.sesion.mensajes = []

    with TestClient(modulo.app) as cliente:
        cliente.app.state.stt = STTFalso()
        cliente.app.state.tts = TTSFalso()
        cliente.app.state.llm = LLMFalso()
        yield cliente


def audio_de_prueba() -> dict[str, Any]:
    return {"audio": ("turno.webm", b"bytes-de-audio", "audio/webm")}


def test_un_turno_devuelve_transcripcion_y_texto(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/turno", files=audio_de_prueba())

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["transcripcion"] == "quiero correr un medio maratón"
    assert "carrera" in cuerpo["respuesta"]
    assert cuerpo["turno_id"]


def test_la_sintesis_no_esta_en_el_camino_critico(cliente: TestClient) -> None:
    # Si el turno devolviera audio, este TTS explotaría y el turno fallaría.
    class TTSQueExplota:
        def sintetizar(self, texto: str) -> bytes:
            raise AssertionError("no debe sintetizarse durante el turno")

    cliente.app.state.tts = TTSQueExplota()

    assert cliente.post("/api/turno", files=audio_de_prueba()).status_code == 200


def test_la_voz_se_pide_aparte_con_el_id_del_turno(cliente: TestClient) -> None:
    turno_id = cliente.post("/api/turno", files=audio_de_prueba()).json()["turno_id"]

    voz = cliente.get(f"/api/voz/{turno_id}")

    assert voz.status_code == 200
    assert voz.headers["content-type"] == "audio/mpeg"
    assert voz.content == b"mp3-de-mentira"


def test_la_voz_se_adelanta_y_no_se_sintetiza_dos_veces(cliente: TestClient) -> None:
    class TTSContador:
        def __init__(self) -> None:
            self.veces = 0

        def sintetizar(self, texto: str) -> bytes:
            self.veces += 1
            return b"mp3"

    contador = TTSContador()
    cliente.app.state.tts = contador

    turno_id = cliente.post("/api/turno", files=audio_de_prueba()).json()["turno_id"]
    cliente.get(f"/api/voz/{turno_id}")

    # Una sola vez: la del adelanto. Si el endpoint volviera a sintetizar,
    # el usuario pagaría la latencia dos veces.
    assert contador.veces == 1


def test_un_fallo_de_voz_no_rompe_el_turno(cliente: TestClient) -> None:
    class TTSQueExplota:
        def sintetizar(self, texto: str) -> bytes:
            raise RuntimeError("Polly caído")

    cliente.app.state.tts = TTSQueExplota()

    assert cliente.post("/api/turno", files=audio_de_prueba()).status_code == 200


def test_un_turno_inexistente_no_devuelve_audio(cliente: TestClient) -> None:
    assert cliente.get("/api/voz/noexiste").status_code == 404


def test_reporta_la_latencia_por_etapa(cliente: TestClient) -> None:
    cuerpo = cliente.post("/api/turno", files=audio_de_prueba()).json()

    for etapa in ("transcripcion", "coach", "total"):
        assert etapa in cuerpo["latencia_ms"]


def test_un_audio_vacio_se_rechaza(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/api/turno", files={"audio": ("turno.webm", b"", "audio/webm")}
    )

    assert respuesta.status_code == 400
    assert respuesta.json()["error"] == "audio_vacio"


def test_si_no_se_entendio_nada_lo_dice(cliente: TestClient) -> None:
    cliente.app.state.stt = STTFalso(texto="")

    respuesta = cliente.post("/api/turno", files=audio_de_prueba())

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "no_se_entendio"


def test_sin_stt_configurado_lo_dice_en_vez_de_reventar(cliente: TestClient) -> None:
    cliente.app.state.stt = None

    respuesta = cliente.post("/api/turno", files=audio_de_prueba())

    assert respuesta.status_code == 503
    assert respuesta.json()["error"] == "sin_stt"


def test_el_endpoint_de_salud_reporta_capacidades(cliente: TestClient) -> None:
    cuerpo = cliente.get("/api/salud").json()

    assert "stt" in cuerpo
    assert cuerpo["base"] in ("sqlite", "postgres")
