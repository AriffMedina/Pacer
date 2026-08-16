"""Un mensaje de Telegram atendido por el mismo coach que atiende la web.

El canal cambia; el turno no. Texto y nota de voz convergen en la misma
cadena: transcribir si hace falta, procesar el turno, responder.
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pacer.application.casos_uso.atender_turno import atender_turno
from pacer.application.casos_uso.conversar import AccionAgenda
from pacer.domain.entidades.carrera import Carrera
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.llm import PuertoLLM
from pacer.domain.puertos.notificacion import MensajeEntrante, PuertoNotificacion
from pacer.domain.puertos.repositorio import PuertoRepositorioPlan
from pacer.domain.puertos.voz import ErrorDeTranscripcion, PuertoSTT

registro = logging.getLogger("pacer")

SIN_VOZ = "Escuché tu nota pero no pude entenderla. ¿Me la escribes?"
SIN_CONTENIDO = "Solo entiendo texto y notas de voz por ahora."

# Telegram entrega las notas de voz como `.oga` (OPUS en contenedor OGG), pero
# Groq valida POR EXTENSIÓN antes de mirar los bytes y `.oga` no está en su
# lista: [flac mp3 mp4 mpeg mpga m4a ogg opus wav webm]. El contenido es el
# mismo; solo hay que nombrarlo como lo espera. Costó un 400 averiguarlo.
NOMBRE_DE_NOTA_DE_VOZ = "nota.ogg"


@dataclass(frozen=True)
class ResultadoTelegram:
    atendido: bool
    dicho_por_el_corredor: str = ""
    respuesta: str = ""
    perfil: Perfil = field(default_factory=Perfil)
    carreras_nuevas: tuple[Carrera, ...] = ()
    acciones_agenda: tuple[AccionAgenda, ...] = ()


async def atender_mensaje_de_telegram(
    mensaje: MensajeEntrante,
    *,
    llm: PuertoLLM,
    stt: PuertoSTT | None,
    canal: PuertoNotificacion,
    repositorio: PuertoRepositorioPlan,
    sistema: str,
    historial: list[dict[str, Any]],
    perfil: Perfil,
    corredor_id: int,
    hoy: date,
    carreras: tuple[Carrera, ...] = (),
) -> ResultadoTelegram:
    """Atiende un mensaje entrante y contesta por el mismo chat."""
    if not mensaje.tiene_contenido:
        return ResultadoTelegram(atendido=False, perfil=perfil)

    dicho = mensaje.texto or ""

    if mensaje.es_voz:
        if stt is None:
            canal.enviar(mensaje.chat_id, SIN_VOZ)
            return ResultadoTelegram(atendido=False, perfil=perfil)
        try:
            audio = canal.descargar_voz(str(mensaje.voz_id))
            dicho = stt.transcribir(audio, NOMBRE_DE_NOTA_DE_VOZ).texto
        except (ErrorDeTranscripcion, OSError) as fallo:
            registro.warning("nota de voz no transcrita: %s", fallo)
            canal.enviar(mensaje.chat_id, SIN_VOZ)
            return ResultadoTelegram(atendido=False, perfil=perfil)

    if not dicho.strip():
        canal.enviar(mensaje.chat_id, SIN_VOZ)
        return ResultadoTelegram(atendido=False, perfil=perfil)

    historial.append({"role": "user", "content": [{"text": dicho}]})

    resultado = await atender_turno(
        llm=llm,
        repositorio=repositorio,
        sistema=sistema,
        mensajes=historial,
        perfil=perfil,
        corredor_id=corredor_id,
        hoy=hoy,
        carreras=carreras,
    )

    historial[:] = resultado.mensajes
    historial.append(
        {"role": "assistant", "content": [{"text": resultado.texto or "..."}]}
    )

    canal.enviar(mensaje.chat_id, resultado.texto)

    return ResultadoTelegram(
        atendido=True,
        dicho_por_el_corredor=dicho,
        respuesta=resultado.texto,
        perfil=resultado.perfil,
        carreras_nuevas=resultado.carreras_nuevas,
        acciones_agenda=resultado.acciones_agenda,
    )
