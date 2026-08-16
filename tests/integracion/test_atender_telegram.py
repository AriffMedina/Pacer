"""Telegram contra una base real, con canal y modelo falsos."""

from datetime import date
from typing import Any

from pacer.application.casos_uso.atender_telegram import (
    SIN_VOZ,
    atender_mensaje_de_telegram,
)
from pacer.application.casos_uso.crear_plan import crear_plan
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import LlamadaHerramienta, RespuestaLLM
from pacer.domain.puertos.notificacion import MensajeEntrante
from pacer.domain.puertos.voz import ErrorDeTranscripcion, Transcripcion
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

CORREDOR = 1
HOY = date(2026, 8, 16)

PERFIL = Perfil(
    objetivo="21k",
    nivel="intermedio",
    dias_disponibles=4,
    km_semana=25,
    fecha_carrera=date(2026, 11, 1),
)


class CanalFalso:
    def __init__(self, audio: bytes = b"ogg") -> None:
        self.enviados: list[tuple[int, str]] = []
        self._audio = audio

    def enviar(self, chat_id: int, texto: str) -> None:
        self.enviados.append((chat_id, texto))

    def recibir(self, desde: int) -> list[MensajeEntrante]:
        return []

    def descargar_voz(self, voz_id: str) -> bytes:
        return self._audio


class STTFalso:
    def __init__(self, texto: str = "hoy corrí y acabé muerto") -> None:
        self.texto = texto

    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion:
        return Transcripcion(texto=self.texto)


class STTQueFalla:
    def transcribir(self, audio: bytes, nombre_archivo: str) -> Transcripcion:
        raise ErrorDeTranscripcion("proveedor caído")


class LLMFalso:
    def __init__(self, *respuestas: RespuestaLLM) -> None:
        self._respuestas = list(respuestas)

    def conversar(
        self, sistema: str, mensajes: list[dict[str, Any]], herramientas: dict[str, Any]
    ) -> RespuestaLLM:
        return self._respuestas.pop(0)


def solo_texto(texto: str) -> RespuestaLLM:
    return RespuestaLLM(texto=texto, llamadas=(), mensaje={"role": "assistant"})


def con_llamada(nombre: str, entrada: dict[str, Any]) -> RespuestaLLM:
    return RespuestaLLM(
        texto="",
        llamadas=(LlamadaHerramienta(id="tu_1", nombre=nombre, entrada=entrada),),
        mensaje={"role": "assistant"},
    )


async def correr(
    mensaje: MensajeEntrante,
    llm: Any,
    canal: CanalFalso,
    repositorio: RepositorioPlan,
    stt: Any = None,
    perfil: Perfil = PERFIL,
) -> Any:
    return await atender_mensaje_de_telegram(
        mensaje,
        llm=llm,
        stt=stt,
        canal=canal,
        repositorio=repositorio,
        sistema="sistema",
        historial=[],
        perfil=perfil,
        corredor_id=CORREDOR,
        hoy=HOY,
    )


async def test_un_mensaje_de_texto_recibe_respuesta(
    repositorio: RepositorioPlan,
) -> None:
    canal = CanalFalso()
    mensaje = MensajeEntrante(id_actualizacion=1, chat_id=55, texto="hola")

    resultado = await correr(canal=canal, llm=LLMFalso(solo_texto("¡Qué onda!")),
                             mensaje=mensaje, repositorio=repositorio)

    assert resultado.atendido
    assert canal.enviados == [(55, "¡Qué onda!")]


async def test_una_nota_de_voz_se_transcribe_y_se_atiende(
    repositorio: RepositorioPlan,
) -> None:
    canal = CanalFalso()
    mensaje = MensajeEntrante(id_actualizacion=2, chat_id=55, voz_id="AwACAgQ")

    resultado = await correr(
        mensaje, LLMFalso(solo_texto("Anotado.")), canal, repositorio, STTFalso()
    )

    assert resultado.dicho_por_el_corredor == "hoy corrí y acabé muerto"
    assert canal.enviados[0][1] == "Anotado."


async def test_el_plan_cambia_desde_telegram(repositorio: RepositorioPlan) -> None:
    """Criterio #3: contesta por Telegram y el plan se ajusta sin abrir la app."""
    await repositorio.guardar(crear_plan(PERFIL, hoy=HOY), corredor_id=CORREDOR)

    canal = CanalFalso()
    llm = LLMFalso(
        con_llamada(
            "registrar_sesion",
            {"pista_temporal": "hoy", "km": 5.0, "sensacion": "muy_dura"},
        ),
        solo_texto("Te bajé la carga de esta semana."),
    )
    mensaje = MensajeEntrante(id_actualizacion=3, chat_id=55, voz_id="AwACAgQ")

    await correr(mensaje, llm, canal, repositorio, STTFalso())

    versiones = await repositorio.versiones(CORREDOR)
    assert [p.version for p in versiones] == [1, 2]
    assert "muy_dura" in str(versiones[1].motivo_cambio)
    assert canal.enviados[0][1] == "Te bajé la carga de esta semana."


async def test_una_voz_que_no_se_transcribe_avisa(
    repositorio: RepositorioPlan,
) -> None:
    canal = CanalFalso()
    mensaje = MensajeEntrante(id_actualizacion=4, chat_id=55, voz_id="AwACAgQ")

    resultado = await correr(
        mensaje, LLMFalso(), canal, repositorio, STTQueFalla()
    )

    assert not resultado.atendido
    assert canal.enviados == [(55, SIN_VOZ)]


async def test_un_sticker_no_llega_al_coach(repositorio: RepositorioPlan) -> None:
    canal = CanalFalso()
    mensaje = MensajeEntrante(id_actualizacion=5, chat_id=55)

    resultado = await correr(mensaje, LLMFalso(), canal, repositorio)

    assert not resultado.atendido
    assert canal.enviados == []
