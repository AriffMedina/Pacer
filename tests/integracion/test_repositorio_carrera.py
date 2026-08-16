from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.carrera import Carrera
from pacer.infrastructure.persistencia.repositorio_carrera import RepositorioCarrera

CORREDOR = 1
OTRO = 2


def carrera(dia: int = 6, nombre: str = "Maratón CDMX") -> Carrera:
    return Carrera(
        fecha=date(2026, 12, dia), nombre=nombre, distancia="maraton", nota="Meta: 4h"
    )


async def test_apunta_y_recupera_una_carrera(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCarrera(sesion_bd)

    guardada = await repositorio.agregar(CORREDOR, carrera())

    assert guardada.id is not None
    todas = await repositorio.todas(CORREDOR)
    assert [c.nombre for c in todas] == ["Maratón CDMX"]
    assert todas[0].nota == "Meta: 4h"


async def test_apuntar_la_misma_dos_veces_no_la_duplica(
    sesion_bd: AsyncSession,
) -> None:
    """Se puede apuntar desde la web y volver a mencionarla hablando.

    Lo garantiza el UNIQUE de la base, no una consulta previa: entre mirar y
    escribir cabe otro turno por Telegram.
    """
    repositorio = RepositorioCarrera(sesion_bd)

    primera = await repositorio.agregar(CORREDOR, carrera())
    segunda = await repositorio.agregar(CORREDOR, carrera())

    assert primera.id == segunda.id
    assert len(await repositorio.todas(CORREDOR)) == 1


async def test_las_devuelve_ordenadas_por_fecha(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCarrera(sesion_bd)
    await repositorio.agregar(CORREDOR, carrera(20, "Diciembre"))
    await repositorio.agregar(CORREDOR, carrera(6, "Primera"))

    assert [c.nombre for c in await repositorio.todas(CORREDOR)] == [
        "Primera",
        "Diciembre",
    ]


async def test_quitar_una_carrera(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCarrera(sesion_bd)
    guardada = await repositorio.agregar(CORREDOR, carrera())

    assert await repositorio.quitar(CORREDOR, guardada.id or 0) is True
    assert await repositorio.todas(CORREDOR) == ()


async def test_quitar_algo_que_no_existe_no_revienta(sesion_bd: AsyncSession) -> None:
    assert await RepositorioCarrera(sesion_bd).quitar(CORREDOR, 999) is False


async def test_no_se_puede_borrar_la_carrera_de_otro(sesion_bd: AsyncSession) -> None:
    """Hoy hay un solo corredor, pero el aislamiento se prueba desde hoy: es
    lo que hace que agregar login después sea llenar columnas y no reabrir esto."""
    repositorio = RepositorioCarrera(sesion_bd)
    ajena = await repositorio.agregar(OTRO, carrera())

    assert await repositorio.quitar(CORREDOR, ajena.id or 0) is False
    assert len(await repositorio.todas(OTRO)) == 1


async def test_cada_corredor_ve_solo_las_suyas(sesion_bd: AsyncSession) -> None:
    repositorio = RepositorioCarrera(sesion_bd)
    await repositorio.agregar(CORREDOR, carrera(6, "Mía"))
    await repositorio.agregar(OTRO, carrera(6, "Ajena"))

    assert [c.nombre for c in await repositorio.todas(CORREDOR)] == ["Mía"]
