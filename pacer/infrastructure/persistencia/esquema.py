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

from sqlalchemy import Connection, inspect, text

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

    if agregadas:
        registro.info("esquema al día, columnas agregadas: %s", ", ".join(agregadas))

    return agregadas
