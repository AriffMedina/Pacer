"""Configuración leída de `.env` o del entorno.

La base de datos es una URL, no una decisión de código: SQLite para desarrollar
sin Docker, Postgres cuando el compose está arriba. Los modelos de SQLAlchemy
son los mismos en ambos casos.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict

SQLITE_LOCAL = "sqlite+aiosqlite:///./pacer.db"


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = SQLITE_LOCAL

    # us-east-1 y no us-east-2: allá Polly no tiene voces neural para es-MX.
    aws_region: str = "us-east-1"

    groq_api_key: str = ""
    telegram_bot_token: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

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
