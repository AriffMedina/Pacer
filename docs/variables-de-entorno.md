# Variables de entorno

Crea un `.env` en la raíz con esto. Ninguna es obligatoria para que el proceso
arranque: sin llave de Groq no hay voz pero se puede escribir, sin token de
Telegram ese canal no despierta, y sin Langfuse las trazas se descartan. La app
degrada, no revienta.

**Las credenciales de AWS no van aquí.** Se resuelven por la cadena estándar: en
desarrollo, `~/.aws` montado de solo lectura; en EC2, el rol de instancia. Es el
[ADR-008](adr/008-sin-llaves-en-disco.md) y es deliberado — un `.env` filtrado no
debe dar acceso a AWS.

```bash
# --- Base de datos -----------------------------------------------------
# Sin esto arranca en SQLite, que sirve para desarrollar sin Docker.
# El compose la sobrescribe apuntando al servicio de Postgres.
DATABASE_URL=postgresql+asyncpg://pacer:pacer@postgres:5432/pacer

# Solo en producción: la contraseña de ejemplo no sale de la máquina de nadie.
# POSTGRES_PASSWORD=

# --- AWS ---------------------------------------------------------------
# us-east-1 y no us-east-2: allá Polly no tiene voces neural ni generative
# para es-MX, y el coach sonaría a robot.
AWS_REGION=us-east-1

# `generative` suena mejor; `neural` sintetiza más rápido.
MOTOR_TTS=generative

# --- Transcripción -----------------------------------------------------
# https://console.groq.com/keys
GROQ_API_KEY=

# --- Telegram ----------------------------------------------------------
# El token que da @BotFather. Vacío = el canal de Telegram no arranca.
TELEGRAM_BOT_TOKEN=

# Telegram entrega cada actualización a UN solo `getUpdates`. Dos procesos con
# el mismo token se pelean los mensajes y el bot parece responder dos veces.
# Ponlo en `false` en tu máquina mientras haya un despliegue vivo.
TELEGRAM_SONDEO=true

# --- API interna -------------------------------------------------------
# Token que n8n manda en la cabecera `X-Pacer-Token`. Vacío = la API interna
# queda CERRADA, no abierta: el default inseguro es el que se olvida.
#   python -c "import secrets; print(secrets.token_urlsafe(32))"
PACER_TOKEN=

# --- Despliegue --------------------------------------------------------
# El dominio para el que Caddy pide el certificado. Solo en producción.
# PACER_DOMINIO=pacer.mi-dominio.com

# --- Observabilidad (opcional) -----------------------------------------
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

## Una nota sobre el formato

El archivo debe **terminar en salto de línea**. Sin él, cualquier `echo ... >>
.env` se pega al final de la última clave en vez de crear una nueva, y el valor
resultante es un engendro que nadie ve hasta que algo devuelve 401. Pasó.
