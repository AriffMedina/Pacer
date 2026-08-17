"""La puesta al día del esquema, contra una base de verdad.

Se prueba sobre SQLite en archivo porque lo que se está verificando es el
comportamiento del motor, no el de un doble: una tabla vieja a la que le falta
una columna del modelo.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from pacer.infrastructure.persistencia.esquema import agregar_columnas_nuevas
from pacer.infrastructure.persistencia.modelos import Base


@pytest.fixture
def motor(tmp_path: Path):  # type: ignore[no-untyped-def]
    return create_engine(f"sqlite:///{tmp_path / 'vieja.db'}")


def test_agrega_la_columna_que_le_falta_a_una_tabla_existente(motor) -> None:  # type: ignore[no-untyped-def]
    """El caso real: `nombre` se agregó al modelo con la base ya en uso."""
    with motor.begin() as conexion:
        conexion.execute(
            text("CREATE TABLE corredor (id INTEGER PRIMARY KEY, objetivo VARCHAR)")
        )

        agregadas = agregar_columnas_nuevas(conexion)

        assert "corredor.nombre" in agregadas
        columnas = {c["name"] for c in inspect(conexion).get_columns("corredor")}
        assert "nombre" in columnas


def test_no_se_pierden_los_datos_que_ya_estaban(motor) -> None:  # type: ignore[no-untyped-def]
    """Lo único inaceptable sería que poner el esquema al día borrara el plan
    de alguien. La columna nueva llega vacía y el resto queda intacto."""
    with motor.begin() as conexion:
        conexion.execute(
            text("CREATE TABLE corredor (id INTEGER PRIMARY KEY, objetivo VARCHAR)")
        )
        conexion.execute(text("INSERT INTO corredor (id, objetivo) VALUES (1, '21k')"))

        agregar_columnas_nuevas(conexion)

        fila = conexion.execute(
            text("SELECT objetivo, nombre FROM corredor WHERE id = 1")
        ).one()
        assert fila.objetivo == "21k"
        assert fila.nombre is None


def test_crea_tambien_los_indices_que_faltan(motor) -> None:  # type: ignore[no-untyped-def]
    """Una columna sin su índice único es una columna a medias.

    Pasó en producción: `clave_sesion` se agregó con ALTER pero su UNIQUE no,
    así que dos peticiones a la vez creaban DOS corredores con la misma cookie
    y la siguiente consulta reventaba por encontrar dos filas donde va una.
    """
    with motor.begin() as conexion:
        conexion.execute(
            text("CREATE TABLE corredor (id INTEGER PRIMARY KEY, objetivo VARCHAR)")
        )

        agregar_columnas_nuevas(conexion)

        indices = {i["name"] for i in inspect(conexion).get_indexes("corredor")}
        assert "ix_corredor_clave_sesion" in indices


def test_el_indice_nuevo_impide_duplicados(motor) -> None:  # type: ignore[no-untyped-def]
    with motor.begin() as conexion:
        conexion.execute(text("CREATE TABLE corredor (id INTEGER PRIMARY KEY)"))
        agregar_columnas_nuevas(conexion)

        conexion.execute(text("INSERT INTO corredor (id, clave_sesion) VALUES (1,'k')"))
        with pytest.raises(IntegrityError):
            conexion.execute(
                text("INSERT INTO corredor (id, clave_sesion) VALUES (2,'k')")
            )


def test_correrlo_dos_veces_no_falla(motor) -> None:  # type: ignore[no-untyped-def]
    """Arranca en cada despliegue y en cada reinicio del contenedor."""
    with motor.begin() as conexion:
        Base.metadata.create_all(conexion)

        assert agregar_columnas_nuevas(conexion) == []
        assert agregar_columnas_nuevas(conexion) == []


def test_una_tabla_que_no_existe_es_problema_de_create_all(motor) -> None:  # type: ignore[no-untyped-def]
    """No intenta alterar lo que todavía no está: se saltea la tabla entera."""
    with motor.begin() as conexion:
        assert agregar_columnas_nuevas(conexion) == []
