from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.carrera import Carrera
from pacer.infrastructure.persistencia.modelos import CarreraORM
from pacer.infrastructure.persistencia.repositorio_carrera import RepositorioCarrera

CORREDOR = 1
OTRO = 2


def carrera(dia: int = 6, nombre: str = "Maratón CDMX") -> Carrera:
    return Carrera(
        fecha=date(2026, 12, dia), nombre=nombre, distancia_km=42.2, nota="Meta: 4h"
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


async def test_guarda_la_distancia_como_kilometros(sesion_bd: AsyncSession) -> None:
    """Cualquier distancia, no solo las cuatro oficiales."""
    repositorio = RepositorioCarrera(sesion_bd)

    await repositorio.agregar(
        CORREDOR, Carrera(fecha=date(2026, 9, 12), nombre="Carrera azul", distancia_km=3.5)
    )

    assert (await repositorio.todas(CORREDOR))[0].distancia_km == 3.5


async def test_la_distancia_se_guarda_con_un_decimal(sesion_bd: AsyncSession) -> None:
    """Nadie corre 12.347 km, y ese ruido se cuela en la tarjeta y en la voz."""
    repositorio = RepositorioCarrera(sesion_bd)

    await repositorio.agregar(
        CORREDOR,
        Carrera(fecha=date(2027, 3, 20), nombre="Rara", distancia_km=12.347),
    )

    assert (await repositorio.todas(CORREDOR))[0].distancia_km == 12.3


async def test_rescata_la_distancia_de_las_filas_viejas(
    sesion_bd: AsyncSession,
) -> None:
    """Las carreras guardadas cuando la distancia era texto libre siguen
    sirviendo: sin esto, quien ya tenía carreras las vería sin distancia y sin
    plan asociado."""
    sesion_bd.add(
        CarreraORM(
            corredor_id=CORREDOR,
            fecha=date(2026, 10, 25),
            nombre="Medio viejo",
            distancia="21k",
            distancia_km=None,
        )
    )
    await sesion_bd.commit()

    recuperada = (await RepositorioCarrera(sesion_bd).todas(CORREDOR))[0]

    assert recuperada.distancia_km == 21.1


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
