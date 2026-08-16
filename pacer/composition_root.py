"""Único lugar donde se elige qué implementación entra por cada puerto.

Cambiar de familia de modelos es cambiar `MODEL_ID` y nada más: ese es el
argumento entero del ADR-003.
"""

from pacer.infrastructure.llm.bedrock import AdaptadorBedrock

REGION = "us-east-1"

# Amazon acepta el id directo.
MODEL_ID_NOVA = "amazon.nova-lite-v1:0"
# Anthropic en Bedrock exige inference profile: el prefijo `us.` no es opcional.
MODEL_ID_CLAUDE = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

MODEL_ID = MODEL_ID_NOVA

# Polly: en us-east-1 hay voces neural y generative para es-MX.
# En us-east-2 solo existe Mia standard, por eso el proyecto vive en us-east-1.
VOZ_TTS = "Mia"
MOTOR_TTS = "generative"


def construir_llm() -> AdaptadorBedrock:
    return AdaptadorBedrock(model_id=MODEL_ID, region=REGION)
