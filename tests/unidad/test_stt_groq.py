"""El parseo de la respuesta de Groq se prueba sin red, con respuestas enlatadas."""

from typing import Any

import httpx
import pytest

from pacer.domain.puertos.voz import ErrorDeTranscripcion
from pacer.infrastructure.stt.groq_whisper import (
    AdaptadorGroqWhisper,
    describir_fallo,
    interpretar_transcripcion,
)


class RespuestaFalsa:
    def __init__(self, codigo: int, cuerpo: dict[str, Any] | None = None) -> None:
        self.status_code = codigo
        self.text = ""
        self._cuerpo = cuerpo or {}

    def json(self) -> dict[str, Any]:
        return self._cuerpo


def simular(monkeypatch: pytest.MonkeyPatch, *codigos: int) -> list[int]:
    """Devuelve una respuesta por llamada y registra cuántas hubo."""
    llamadas: list[int] = []
    secuencia = list(codigos)

    def post_falso(*args: Any, **kwargs: Any) -> RespuestaFalsa:
        codigo = secuencia[len(llamadas)]
        llamadas.append(codigo)
        if codigo == 200:
            return RespuestaFalsa(200, {"text": "hola", "duration": 1.0})
        return RespuestaFalsa(codigo)

    monkeypatch.setattr(httpx, "post", post_falso)
    return llamadas

VERBOSE = {
    "text": " Ayer corrí doce kilómetros y acabé muerto.",
    "duration": 4.0,
    "segments": [{"id": 0, "start": 0.0, "end": 4.0, "text": "Ayer corrí..."}],
}

SIN_SEGMENTOS = {"text": "Hola"}


def test_extrae_el_texto_y_lo_limpia() -> None:
    resultado = interpretar_transcripcion(VERBOSE)

    assert resultado.texto == "Ayer corrí doce kilómetros y acabé muerto."


def test_calcula_palabras_por_segundo() -> None:
    resultado = interpretar_transcripcion(VERBOSE)

    # 7 palabras en 4 segundos.
    assert resultado.duracion_s == 4.0
    assert round(resultado.palabras_por_s, 2) == 1.75


def test_una_respuesta_sin_duracion_no_revienta() -> None:
    resultado = interpretar_transcripcion(SIN_SEGMENTOS)

    assert resultado.texto == "Hola"
    assert resultado.palabras_por_s == 0.0


def test_una_duracion_cero_no_divide_entre_cero() -> None:
    resultado = interpretar_transcripcion({"text": "algo", "duration": 0})

    assert resultado.palabras_por_s == 0.0


def test_un_401_se_considera_transitorio_y_se_reintenta() -> None:
    # Medido: Groq devuelve 401 intermitente con llaves válidas. Rendirse al
    # primer intento le rompe el turno al usuario por un fallo pasajero.
    mensaje, recuperable = describir_fallo(401, '{"error":{"message":"Invalid API Key"}}')

    assert recuperable
    assert "intermitente" in mensaje


def test_un_429_es_recuperable_y_habla_de_cuota() -> None:
    mensaje, recuperable = describir_fallo(429, "")

    assert recuperable
    assert "cuota" in mensaje


def test_un_error_del_servidor_es_recuperable() -> None:
    _, recuperable = describir_fallo(503, "")

    assert recuperable


def test_un_401_pasajero_se_supera_reintentando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas = simular(monkeypatch, 401, 200)

    resultado = AdaptadorGroqWhisper(api_key="x").transcribir(b"audio", "t.webm")

    assert resultado.texto == "hola"
    assert len(llamadas) == 2


def test_si_falla_siempre_se_rinde_con_el_error_real(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas = simular(monkeypatch, 401, 401, 401)

    with pytest.raises(ErrorDeTranscripcion):
        AdaptadorGroqWhisper(api_key="x").transcribir(b"audio", "t.webm")

    assert len(llamadas) == 3


def test_un_error_definitivo_no_gasta_reintentos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    llamadas = simular(monkeypatch, 400)

    with pytest.raises(ErrorDeTranscripcion):
        AdaptadorGroqWhisper(api_key="x").transcribir(b"audio", "t.webm")

    assert len(llamadas) == 1


def test_un_400_no_se_reintenta() -> None:
    # Un audio malformado no mejora reintentando: solo gasta tiempo del usuario.
    mensaje, recuperable = describir_fallo(400, "archivo corrupto")

    assert not recuperable
    assert "archivo corrupto" in mensaje
