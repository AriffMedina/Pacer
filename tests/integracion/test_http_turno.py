"""El endpoint completo, con adaptadores falsos.

Ni Groq ni Polly ni Bedrock se tocan aquí, y la base es un archivo temporal:
un test que le escribe a la base real o gasta llamadas de API no es un test.
"""

import base64
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


def test_un_turno_devuelve_transcripcion_respuesta_y_voz(cliente: TestClient) -> None:
    respuesta = cliente.post("/api/turno", files=audio_de_prueba())

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["transcripcion"] == "quiero correr un medio maratón"
    assert "carrera" in cuerpo["respuesta"]
    assert base64.b64decode(cuerpo["audio_base64"]) == b"mp3-de-mentira"


def test_reporta_la_latencia_por_etapa(cliente: TestClient) -> None:
    cuerpo = cliente.post("/api/turno", files=audio_de_prueba()).json()

    for etapa in ("transcripcion", "coach", "voz", "total"):
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
