"""El parseo de la respuesta de Bedrock se prueba sin red, con respuestas enlatadas."""

from pacer.infrastructure.llm.bedrock import interpretar_respuesta

SOLO_TEXTO = {
    "stopReason": "end_turn",
    "output": {
        "message": {
            "role": "assistant",
            "content": [{"text": "¿Para qué carrera te estás preparando?"}],
        }
    },
}

CON_HERRAMIENTA = {
    "stopReason": "tool_use",
    "output": {
        "message": {
            "role": "assistant",
            "content": [
                {"text": "Perfecto, lo anoto."},
                {
                    "toolUse": {
                        "toolUseId": "tu_123",
                        "name": "actualizar_perfil",
                        "input": {"objetivo": "21k"},
                    }
                },
            ],
        }
    },
}


def test_una_respuesta_de_texto_no_trae_llamadas() -> None:
    respuesta = interpretar_respuesta(SOLO_TEXTO)

    assert respuesta.llamadas == ()
    assert "carrera" in respuesta.texto


def test_extrae_la_llamada_a_herramienta() -> None:
    respuesta = interpretar_respuesta(CON_HERRAMIENTA)

    assert len(respuesta.llamadas) == 1
    llamada = respuesta.llamadas[0]
    assert llamada.nombre == "actualizar_perfil"
    assert llamada.entrada == {"objetivo": "21k"}
    assert llamada.id == "tu_123"


def test_conserva_el_texto_junto_a_la_llamada() -> None:
    respuesta = interpretar_respuesta(CON_HERRAMIENTA)

    assert "lo anoto" in respuesta.texto


def test_conserva_el_mensaje_crudo_para_reenviarlo() -> None:
    respuesta = interpretar_respuesta(CON_HERRAMIENTA)

    assert respuesta.mensaje["role"] == "assistant"
