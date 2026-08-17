"""Repositorio del corredor y de su conversación."""

from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
        """Identidad por canal: el chat de Telegram identifica a la persona."""
        return await self._obtener_o_crear(
            CorredorORM.telegram_chat_id == telegram_chat_id,
            lambda: CorredorORM(telegram_chat_id=telegram_chat_id),
        )

    async def obtener_o_crear_por_sesion(self, clave: str) -> Corredor:
        """El corredor de ESTE navegador. Lo crea la primera vez que aparece.

        Reemplaza al viejo "primer corredor de la tabla", que convertía cada
        visita en la misma persona: mandar el enlace a alguien era darle tu plan.
        """
        return await self._obtener_o_crear(
            CorredorORM.clave_sesion == clave,
            lambda: CorredorORM(clave_sesion=clave),
        )

    async def _obtener_o_crear(
        self, condicion: Any, nuevo: Callable[[], CorredorORM]
    ) -> Corredor:
        """Buscar y, si no está, crear — a prueba de carreras.

        Al abrir la app salen varias peticiones a la vez con la misma cookie:
        todas miran, ninguna encuentra y todas intentan insertar. Gana una y el
        resto choca contra el UNIQUE. Quien pierde no falla: vuelve a mirar y
        encuentra la fila que acaba de crear la otra. Mirar antes de insertar
        nunca basta; entre el SELECT y el INSERT cabe otra petición.
        """
        fila = (await self._sesion.execute(select(CorredorORM).where(condicion))
                ).scalar_one_or_none()
        if fila is not None:
            return _a_dominio(fila)

        fila = nuevo()
        self._sesion.add(fila)
        try:
            await self._sesion.commit()
        except IntegrityError:
            await self._sesion.rollback()
            fila = (await self._sesion.execute(select(CorredorORM).where(condicion))
                    ).scalar_one()
            return _a_dominio(fila)

        await self._sesion.refresh(fila)
        return _a_dominio(fila)

    async def por_email(self, email: str) -> Corredor | None:
        consulta = select(CorredorORM).where(CorredorORM.email == email.lower())
        fila = (await self._sesion.execute(consulta)).scalar_one_or_none()
        return _a_dominio(fila) if fila is not None else None

    async def guardar_credenciales(
        self, corredor_id: int, email: str, password_hash: str
    ) -> bool:
        """Le pone cuenta al corredor que ya existía. Devuelve si se pudo.

        No crea una fila nueva a propósito: registrarse ADOPTA el corredor que
        venías usando, así nadie pierde su plan por crear la cuenta.
        """
        fila = await self._sesion.get(CorredorORM, corredor_id)
        if fila is None:
            return False

        fila.email = email.lower()
        fila.password_hash = password_hash
        try:
            await self._sesion.commit()
        except IntegrityError:
            # El UNIQUE del correo es quien decide, no una consulta previa.
            await self._sesion.rollback()
            return False
        return True

    async def mudar_sesion(self, corredor_id: int, clave: str) -> None:
        """Ata este navegador al corredor indicado. Es lo que hace "entrar".

        Suelta la llave de quien la tuviera antes: `clave_sesion` es UNIQUE y
        sin eso el UPDATE choca contra el navegador anónimo que la traía.
        """
        previo = (
            await self._sesion.execute(
                select(CorredorORM).where(CorredorORM.clave_sesion == clave)
            )
        ).scalar_one_or_none()

        if previo is not None:
            if previo.id == corredor_id:
                return
            previo.clave_sesion = None
            await self._sesion.flush()

        fila = await self._sesion.get(CorredorORM, corredor_id)
        if fila is not None:
            fila.clave_sesion = clave
        await self._sesion.commit()

    async def con_telegram(self) -> list[Corredor]:
        """Los corredores que tienen un chat al que escribirles."""
        consulta = select(CorredorORM).where(CorredorORM.telegram_chat_id.isnot(None))
        return [_a_dominio(f) for f in (await self._sesion.execute(consulta)).scalars()]

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

        return _conversacion_valida(
            [
                {"role": fila.rol, "content": [{"text": fila.texto}]}
                for fila in reversed(filas)
            ]
        )


def _conversacion_valida(historial: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deja el historial como lo exige `converse`: empieza en el corredor y alterna.

    Recortar la ventana puede dejar la primera línea en el coach, y un turno
    que se cayó a medias deja dos del corredor seguidas. Cualquiera de las dos
    hace que la API rechace TODOS los turnos siguientes, y eso desde fuera se
    ve como que el coach perdió la memoria.

    Los mensajes seguidos del mismo lado se juntan en vez de descartarse:
    tirarlos sería perder de verdad lo que la persona dijo.
    """
    while historial and historial[0]["role"] != "user":
        historial.pop(0)

    juntados: list[dict[str, Any]] = []
    for mensaje in historial:
        if juntados and juntados[-1]["role"] == mensaje["role"]:
            juntados[-1]["content"][0]["text"] += "\n" + mensaje["content"][0]["text"]
        else:
            juntados.append(mensaje)
    return juntados


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
