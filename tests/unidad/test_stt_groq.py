"""El parseo de la respuesta de Groq se prueba sin red, con respuestas enlatadas."""

from pacer.infrastructure.stt.groq_whisper import (
    describir_fallo,
    interpretar_transcripcion,
)

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


def test_un_401_manda_a_revisar_la_cuenta_no_la_llave() -> None:
    # Groq responde "Invalid API Key" en audio incluso con llaves que /models
    # acepta. Repetir ese mensaje hace perder el tiempo en el lugar equivocado.
    mensaje = describir_fallo(401, '{"error":{"message":"Invalid API Key"}}')

    assert "límites y facturación" in mensaje
    assert "no la llave" in mensaje


def test_un_429_habla_de_cuota() -> None:
    assert "cuota" in describir_fallo(429, "")


def test_un_error_desconocido_incluye_el_cuerpo() -> None:
    mensaje = describir_fallo(503, "servicio caído")

    assert "503" in mensaje
    assert "servicio caído" in mensaje
