"""Único lugar donde se elige qué implementación entra por cada puerto.

Cambiar de familia de modelos es cambiar `MODEL_ID` y nada más: ese es el
argumento entero del ADR-003.
"""

from pacer.infrastructure.configuracion import Configuracion
from pacer.infrastructure.llm.bedrock import AdaptadorBedrock
from pacer.infrastructure.stt.groq_whisper import AdaptadorGroqWhisper
from pacer.infrastructure.tts.polly import AdaptadorPolly

# Amazon acepta el id directo.
MODEL_ID_NOVA = "amazon.nova-lite-v1:0"
# Anthropic en Bedrock exige inference profile: el prefijo `us.` no es opcional.
MODEL_ID_CLAUDE = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Medido el 2026-08-15 con el mismo prompt y el mismo catálogo de herramientas:
# Nova Lite no llamó actualizar_perfil y filtró un bloque <thinking> en el texto,
# que el TTS habría leído en voz alta. Claude Haiku llamó la herramienta y parseó
# "1 de noviembre de 2026" a fecha ISO sin ayuda. Se eligió por comportamiento
# observado, no por preferencia.
MODEL_ID = MODEL_ID_CLAUDE

# Polly: en us-east-1 hay voces neural y generative para es-MX.
# En us-east-2 solo existe Mia standard, por eso el proyecto vive en us-east-1.
VOZ_TTS = "Mia"
MOTOR_TTS = "generative"

# El piloto es de un solo corredor (`vision.md`: multiusuario fuera de alcance).
CORREDOR_PILOTO = 1


def configuracion() -> Configuracion:
    return Configuracion()


def construir_llm(config: Configuracion | None = None) -> AdaptadorBedrock:
    conf = config or configuracion()
    return AdaptadorBedrock(model_id=MODEL_ID, region=conf.aws_region)


def construir_stt(config: Configuracion | None = None) -> AdaptadorGroqWhisper | None:
    """Sin llave de Groq no hay transcripción, pero el resto del sistema vive."""
    conf = config or configuracion()
    if not conf.stt_disponible:
        return None
    return AdaptadorGroqWhisper(api_key=conf.groq_api_key)


def construir_tts(config: Configuracion | None = None) -> AdaptadorPolly:
    conf = config or configuracion()
    return AdaptadorPolly(region=conf.aws_region, voz=VOZ_TTS, motor=MOTOR_TTS)
