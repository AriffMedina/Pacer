"""Fixtures de integración con base de datos intercambiable.

Por defecto corre contra SQLite en memoria. Para verificar Postgres —que es lo
que se despliega— basta apuntar la variable, sin tocar una línea de test:

    docker compose -f infra/docker-compose.yml up -d
    TEST_DATABASE_URL=postgresql+asyncpg://pacer:pacer@localhost:5432/pacer \\
        uv run pytest tests/integracion

`drop_all` antes de `create_all` no es opcional: SQLite en memoria nace limpio
en cada motor, pero Postgres conserva el estado entre tests.
"""

import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

SQLITE_EN_MEMORIA = "sqlite+aiosqlite:///:memory:"
URL_DE_PRUEBAS = os.environ.get("TEST_DATABASE_URL", SQLITE_EN_MEMORIA)


@pytest.fixture
async def sesion_bd() -> AsyncIterator[AsyncSession]:
    motor = create_async_engine(URL_DE_PRUEBAS)

    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.drop_all)
        await conexion.run_sync(Base.metadata.create_all)

    fabrica = async_sessionmaker(motor, expire_on_commit=False)
    async with fabrica() as sesion:
        yield sesion

    await motor.dispose()


@pytest.fixture
async def repositorio(sesion_bd: AsyncSession) -> RepositorioPlan:
    return RepositorioPlan(sesion_bd)
