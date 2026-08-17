"""Puesta al día del esquema para columnas nuevas.

`Base.metadata.create_all` crea tablas que faltan, pero NO altera las que ya
existen. Agregar una columna al modelo y desplegar contra una base viva deja
todas las consultas de esa tabla fallando con UndefinedColumn.

Esto es el mínimo que evita ese fallo sin borrar los datos de nadie: solo
agrega columnas nuevas y anulables. No renombra, no borra, no cambia tipos, no
mueve datos. Para eso hace falta Alembic, y Alembic es la respuesta correcta en
cuanto el proyecto tenga más de un entorno con datos que importen.
"""

import logging
from typing import Any

from sqlalchemy import Connection, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateIndex

from pacer.infrastructure.persistencia.modelos import Base

registro = logging.getLogger("pacer")


def agregar_columnas_nuevas(conexion: Connection) -> list[str]:
    """Agrega las columnas anulables que el modelo tiene y la base todavía no.

    Devuelve lo que agregó, para que quede en el log del arranque: una
    migración silenciosa es una migración que nadie puede auditar.
    """
    inspector = inspect(conexion)
    existentes = set(inspector.get_table_names())
    agregadas: list[str] = []

    for tabla in Base.metadata.sorted_tables:
        if tabla.name not in existentes:
            continue  # create_all ya la creó completa

        en_la_base = {c["name"] for c in inspector.get_columns(tabla.name)}

        for columna in tabla.columns:
            if columna.name in en_la_base or not columna.nullable:
                continue

            tipo = columna.type.compile(conexion.dialect)
            conexion.execute(
                text(f'ALTER TABLE "{tabla.name}" ADD COLUMN "{columna.name}" {tipo}')
            )
            agregadas.append(f"{tabla.name}.{columna.name}")

        agregadas += _indices_que_faltan(conexion, inspector, tabla)

    if agregadas:
        registro.info("esquema al día: %s", ", ".join(agregadas))

    return agregadas


def _indices_que_faltan(conexion: Connection, inspector: Any, tabla: Any) -> list[str]:
    """Crea los índices declarados en el modelo que la tabla no tenga.

    `ALTER TABLE ADD COLUMN` agrega la columna y NADA más: el UNIQUE que la
    declaración pedía se queda sin crear. Pasó con `clave_sesion` — sin su
    índice, dos peticiones simultáneas creaban dos corredores con la misma
    cookie y la consulta siguiente encontraba dos filas donde va una.

    Un índice que no se puede crear (datos duplicados de antes) se registra
    fuerte y no detiene el arranque: la app sirve, pero queda constancia.
    """
    existentes = {indice["name"] for indice in inspector.get_indexes(tabla.name)}
    creados = []

    for indice in tabla.indexes:
        if indice.name in existentes:
            continue
        try:
            conexion.execute(CreateIndex(indice))
            creados.append(f"índice {indice.name}")
        except SQLAlchemyError as fallo:
            registro.error(
                "NO se pudo crear el índice %s; puede haber duplicados: %s",
                indice.name,
                fallo,
            )

    return creados
