"""Repositorio del corredor y de su conversación."""

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pacer.domain.entidades.corredor import Corredor
from pacer.domain.entidades.perfil import Nivel, Objetivo, Perfil
from pacer.infrastructure.persistencia.modelos import ConversacionORM, CorredorORM

CAMPOS_DE_PERFIL = (
    "nombre",
    "objetivo",
    "nivel",
    "dias_disponibles",
    "km_semana",
    "fecha_carrera",
    "dolor_actual",
)


class RepositorioCorredor:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_o_crear(self, telegram_chat_id: int) -> Corredor:
        """Identidad por canal: el chat de Telegram basta para el piloto."""
        consulta = select(CorredorORM).where(
            CorredorORM.telegram_chat_id == telegram_chat_id
        )
        fila = (await self._sesion.execute(consulta)).scalar_one_or_none()

        if fila is None:
            fila = CorredorORM(telegram_chat_id=telegram_chat_id)
            self._sesion.add(fila)
            await self._sesion.commit()
            await self._sesion.refresh(fila)

        return _a_dominio(fila)

    async def obtener_o_crear_piloto(self) -> Corredor:
        """El corredor del piloto: el primero que exista, o uno nuevo.

        Atajo deliberado y acotado. `vision.md` declara el multiusuario fuera de
        alcance, así que la web y Telegram atienden a la misma persona. El día
        que haya autenticación, esto se reemplaza por resolver el corredor desde
        el token — y como todo lo demás ya recibe `corredor_id` por parámetro,
        es el único lugar que cambia.
        """
        consulta = select(CorredorORM).order_by(CorredorORM.id).limit(1)
        fila = (await self._sesion.execute(consulta)).scalar_one_or_none()

        if fila is None:
            fila = CorredorORM()
            self._sesion.add(fila)
            await self._sesion.commit()
            await self._sesion.refresh(fila)

        return _a_dominio(fila)

    async def vincular_telegram(self, corredor_id: int, chat_id: int) -> None:
        """Ata un chat al corredor la primera vez que escribe."""
        fila = await self._sesion.get(CorredorORM, corredor_id)
        if fila is not None and fila.telegram_chat_id is None:
            fila.telegram_chat_id = chat_id
            await self._sesion.commit()

    async def por_id(self, corredor_id: int) -> Corredor | None:
        fila = await self._sesion.get(CorredorORM, corredor_id)
        return _a_dominio(fila) if fila is not None else None

    async def guardar_perfil(self, corredor_id: int, perfil: Perfil) -> None:
        """Persiste los hechos del corredor. Nunca crea una fila nueva."""
        fila = await self._sesion.get(CorredorORM, corredor_id)
        if fila is None:
            raise ValueError(f"no existe el corredor {corredor_id}")

        for campo in CAMPOS_DE_PERFIL:
            setattr(fila, campo, getattr(perfil, campo))

        await self._sesion.commit()

    async def recordar(
        self, corredor_id: int, rol: str, texto: str, canal: str = "web"
    ) -> None:
        self._sesion.add(
            ConversacionORM(
                corredor_id=corredor_id, rol=rol, texto=texto, canal=canal
            )
        )
        await self._sesion.commit()

    async def ultimos_turnos(
        self, corredor_id: int, cuantos: int
    ) -> list[dict[str, Any]]:
        """Los últimos turnos, en orden cronológico, listos para el modelo."""
        consulta = (
            select(ConversacionORM)
            .where(ConversacionORM.corredor_id == corredor_id)
            .order_by(ConversacionORM.id.desc())
            .limit(cuantos)
        )
        filas = list((await self._sesion.execute(consulta)).scalars())

        return [
            {"role": fila.rol, "content": [{"text": fila.texto}]}
            for fila in reversed(filas)
        ]


def _a_dominio(fila: CorredorORM) -> Corredor:
    return Corredor(
        id=fila.id,
        telegram_chat_id=fila.telegram_chat_id,
        email=fila.email,
        password_hash=fila.password_hash,
        perfil=Perfil(
            nombre=fila.nombre,
            objetivo=cast(Objetivo | None, fila.objetivo),
            nivel=cast(Nivel | None, fila.nivel),
            dias_disponibles=fila.dias_disponibles,
            km_semana=fila.km_semana,
            fecha_carrera=fila.fecha_carrera,
            dolor_actual=fila.dolor_actual,
        ),
    )
