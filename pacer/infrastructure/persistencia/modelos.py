"""Modelos SQLAlchemy, separados a propósito de las entidades de dominio.

El dominio no sabe que esto existe. El repositorio traduce entre ambos mundos,
y `import-linter` es quien vigila que esa frontera no se cruce.
"""

from datetime import UTC, date, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Instantes CON zona horaria. Sin esto Postgres crea `timestamp without time
# zone` y revienta al compararlo contra un datetime con `tzinfo`:
#   asyncpg.DataError: can't subtract offset-naive and offset-aware datetimes
# SQLite lo tolera, así que la suite pasaba y el contenedor fallaba. Un tipo
# explícito vale más que confiar en la inferencia del dialecto.
MOMENTO = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


class CorredorORM(Base):
    """Identidad y perfil.

    `email` y `password_hash` nacen vacíos a propósito: el piloto identifica por
    canal, no por credenciales. Existir desde hoy evita migrar el esquema el día
    que se agregue login.
    """

    __tablename__ = "corredor"

    id: Mapped[int] = mapped_column(primary_key=True)
    # BigInteger y no el INTEGER que infiere `Mapped[int]`: los chat id de
    # Telegram pasan de los 2.147.483.647 que aguanta un int32. SQLite guarda
    # enteros de cualquier tamaño y no se queja; Postgres rechaza el UPDATE.
    telegram_chat_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, index=True, default=None
    )
    email: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)
    password_hash: Mapped[str | None] = mapped_column(default=None)

    # Qué navegador es este corredor ahora mismo. Sin cuenta es la única
    # identidad que hay; con cuenta, entrar mueve esta llave a la fila de la
    # cuenta y el navegador pasa a ser esa persona.
    clave_sesion: Mapped[str | None] = mapped_column(
        unique=True, index=True, default=None
    )

    # El código de un solo uso que une este corredor con un chat de Telegram.
    # Vive en la fila y no en memoria a propósito: la app corre en más de un
    # proceso y un diccionario en RAM haría que el código funcionara o no
    # según qué worker atendiera el canje. UNIQUE porque dos corredores con el
    # mismo código serían dos personas peleándose una identidad.
    codigo_telegram: Mapped[str | None] = mapped_column(
        unique=True, index=True, default=None
    )
    # MOMENTO y no un DateTime pelado: `reloj.ahora()` devuelve fecha CON zona,
    # y comparar una con zona contra una sin zona lanza TypeError. El canje
    # habría reventado la primera vez que alguien lo usara.
    codigo_telegram_caduca: Mapped[datetime | None] = mapped_column(
        MOMENTO, default=None
    )

    # Perfil. Son hechos del corredor, no conversación, así que son columnas.
    nombre: Mapped[str | None] = mapped_column(default=None)
    objetivo: Mapped[str | None] = mapped_column(default=None)
    nivel: Mapped[str | None] = mapped_column(default=None)
    dias_disponibles: Mapped[int | None] = mapped_column(default=None)
    km_semana: Mapped[int | None] = mapped_column(default=None)
    fecha_carrera: Mapped[date | None] = mapped_column(default=None)
    dolor_actual: Mapped[bool] = mapped_column(default=False)


class CarreraORM(Base):
    """Fechas que el corredor apuntó. No son el plan: son su calendario.

    `nombre` + `fecha` es UNIQUE por corredor para que apuntar dos veces la
    misma carrera —desde la web y luego hablando— no la duplique.
    """

    __tablename__ = "carrera"
    __table_args__ = (UniqueConstraint("corredor_id", "fecha", "nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    corredor_id: Mapped[int] = mapped_column(ForeignKey("corredor.id"), index=True)
    fecha: Mapped[date] = mapped_column(index=True)
    nombre: Mapped[str]
    distancia_km: Mapped[float | None] = mapped_column(default=None)
    nota: Mapped[str] = mapped_column(default="")

    # Se guardaba la distancia como texto ("21k", "15 k", "maraton"). No se
    # podía razonar sobre eso, así que ahora son kilómetros. La columna vieja
    # se conserva solo para leer las filas escritas antes; ya nadie escribe en
    # ella y se puede tirar en cuanto haya migraciones de verdad.
    distancia: Mapped[str | None] = mapped_column(default=None)


class ConversacionORM(Base):
    """Turnos anteriores, para que el coach retome después de un reinicio.

    Los hechos viven en sus propias tablas; esto es continuidad de trato, no
    fuente de verdad. Si se perdiera, el coach seguiría sabiendo quién eres y
    en qué semana vas.
    """

    __tablename__ = "conversacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    corredor_id: Mapped[int] = mapped_column(
        ForeignKey("corredor.id"), index=True
    )
    rol: Mapped[str]
    texto: Mapped[str]
    canal: Mapped[str] = mapped_column(default="web")
    creado_en: Mapped[datetime] = mapped_column(
        MOMENTO, default=lambda: datetime.now(UTC)
    )


class RecordatorioORM(Base):
    """Lo que el coach tiene pendiente preguntarte.

    `clave` es UNIQUE: materializar dos veces no duplica, y confirmar dos veces
    no reenvía. Los reintentos de n8n son seguros por construcción de la base,
    no por el cuidado de quien llama.
    """

    __tablename__ = "recordatorio"

    id: Mapped[int] = mapped_column(primary_key=True)
    corredor_id: Mapped[int] = mapped_column(ForeignKey("corredor.id"), index=True)
    clave: Mapped[str] = mapped_column(unique=True, index=True)
    texto: Mapped[str]
    programado_para: Mapped[datetime] = mapped_column(MOMENTO, index=True)
    canal: Mapped[str] = mapped_column(default="telegram")
    enviado_en: Mapped[datetime | None] = mapped_column(MOMENTO, default=None)
    id_mensaje_proveedor: Mapped[str | None] = mapped_column(default=None)


class PlanORM(Base):
    __tablename__ = "plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    corredor_id: Mapped[int] = mapped_column(index=True)
    version: Mapped[int]
    motivo_cambio: Mapped[str | None] = mapped_column(default=None)

    semanas: Mapped[list["SemanaORM"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="SemanaORM.numero",
        lazy="selectin",
    )


class SemanaORM(Base):
    __tablename__ = "semana"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    numero: Mapped[int]
    es_descarga: Mapped[bool] = mapped_column(default=False)
    # base, construccion, pico o tapering. Es cómo el plan se describe a sí
    # mismo, y sin esta columna el viaje a la base lo borraba.
    bloque: Mapped[str | None] = mapped_column(default=None)
    recortada: Mapped[bool | None] = mapped_column(default=False)

    plan: Mapped[PlanORM] = relationship(back_populates="semanas")
    sesiones: Mapped[list["SesionORM"]] = relationship(
        back_populates="semana",
        cascade="all, delete-orphan",
        order_by="SesionORM.id",
        lazy="selectin",
    )


class SesionORM(Base):
    __tablename__ = "sesion"

    id: Mapped[int] = mapped_column(primary_key=True)
    semana_id: Mapped[int] = mapped_column(ForeignKey("semana.id"))
    fecha: Mapped[date]
    tipo: Mapped[str]
    km: Mapped[float]
    completada: Mapped[bool] = mapped_column(default=False)
    sensacion: Mapped[str | None] = mapped_column(default=None)

    semana: Mapped[SemanaORM] = relationship(back_populates="sesiones")
