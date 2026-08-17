"""Configuración leída de `.env` o del entorno.

La base de datos es una URL, no una decisión de código: SQLite para desarrollar
sin Docker, Postgres cuando el compose está arriba. Los modelos de SQLAlchemy
son los mismos en ambos casos.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SQLITE_LOCAL = "sqlite+aiosqlite:///./pacer.db"

# Anclado a la raíz del proyecto, NO al directorio de trabajo: un `env_file`
# relativo se pierde en silencio al lanzar el proceso desde otra carpeta o con
# otro WORKDIR en el contenedor, y la app arranca con la configuración vacía
# sin dar un solo error.
RAIZ_DEL_PROYECTO = Path(__file__).resolve().parents[2]


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_DEL_PROYECTO / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = SQLITE_LOCAL

    # us-east-1 y no us-east-2: allá Polly no tiene voces neural para es-MX.
    aws_region: str = "us-east-1"

    # `generative` suena mejor; `neural` sintetiza más rápido. Configurable para
    # poder medir el intercambio sin tocar código.
    motor_tts: str = "generative"

    # Una síntesis de cortesía al arrancar, para que el primer turno real no
    # pague el arranque en frío. Se apaga en tests: no deben tocar la red.
    calentar_voz: bool = True

    # Token de la API interna que consume n8n. Vacío = API interna cerrada.
    # El default inseguro es el que se olvida en producción.
    pacer_token: str = ""

    groq_api_key: str = ""
    telegram_bot_token: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    # Langfuse Cloud entrega LANGFUSE_BASE_URL; el SDK histórico usa
    # LANGFUSE_HOST. Se aceptan las dos para que copiar y pegar desde la
    # consola de Langfuse no falle en silencio.
    langfuse_host: str = "http://localhost:3000"
    langfuse_base_url: str = ""

    @property
    def es_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def stt_disponible(self) -> bool:
        """Sin llave de Groq no hay transcripción, pero el resto sigue vivo."""
        return bool(self.groq_api_key)

    @property
    def telegram_disponible(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def langfuse_url(self) -> str:
        """La URL efectiva: gana `LANGFUSE_BASE_URL` si está puesta."""
        return self.langfuse_base_url or self.langfuse_host

    @property
    def observabilidad_disponible(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)
