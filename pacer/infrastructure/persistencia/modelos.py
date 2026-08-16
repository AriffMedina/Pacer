"""Modelos SQLAlchemy, separados a propósito de las entidades de dominio.

El dominio no sabe que esto existe. El repositorio traduce entre ambos mundos,
y `import-linter` es quien vigila que esa frontera no se cruce.
"""

from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


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
