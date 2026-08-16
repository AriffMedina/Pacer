"""El cable: audio del navegador → transcripción → coach → voz de vuelta.

Devuelve JSON en vez de audio crudo para que la interfaz pueda mostrar la
transcripción y la latencia. El cajón de diagnóstico no es adorno: sin él, un
turno lento y un turno roto se ven igual desde el teléfono.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from pacer.application.casos_uso.atender_turno import atender_turno
from pacer.application.contexto.bloque_estado import construir_bloque
from pacer.application.contexto.prompt_sistema import construir_prompt
from pacer.composition_root import (
    CORREDOR_PILOTO,
    configuracion,
    construir_llm,
    construir_stt,
    construir_tts,
)
from pacer.domain.entidades.perfil import Perfil
from pacer.domain.puertos.voz import ErrorDeTranscripcion
from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan

DIRECTORIO_WEB = Path(__file__).resolve().parents[3] / "web"

registro = logging.getLogger("pacer")


@dataclass
class SesionEnMemoria:
    """Perfil e historial del piloto.

    Limitación conocida: se pierde al reiniciar. El plan sí está en la base;
    persistir el perfil es lo que falta para que Telegram funcione con la app
    cerrada durante días.
    """

    perfil: Perfil = field(default_factory=Perfil)
    mensajes: list[dict[str, Any]] = field(default_factory=list)


sesion = SesionEnMemoria()

# Respuestas esperando ser sintetizadas. Se guardan pocas y se descartan las
# viejas: nadie pide la voz de un turno de hace veinte turnos.
_PENDIENTES: OrderedDict[str, str] = OrderedDict()
_YA_SINTETIZADO: OrderedDict[str, bytes] = OrderedDict()
MAX_PENDIENTES = 20


def _guardar_para_voz(texto: str) -> str:
    turno_id = uuid4().hex[:12]
    _PENDIENTES[turno_id] = texto
    while len(_PENDIENTES) > MAX_PENDIENTES:
        _PENDIENTES.popitem(last=False)
    return turno_id


async def _adelantar_sintesis(turno_id: str, texto: str) -> None:
    """Sintetiza sin que nadie lo haya pedido todavía.

    Corre después de responder, así los ~200 ms de Polly se solapan con el
    viaje de red y el render del cliente en vez de sumarse. Si falla, no pasa
    nada: el endpoint de voz vuelve a intentarlo bajo demanda.
    """
    try:
        audio = await asyncio.to_thread(app.state.tts.sintetizar, texto)
    except Exception as fallo:  # noqa: BLE001 — un fallo de voz jamás rompe un turno
        registro.warning("no se pudo adelantar la voz del turno %s: %s", turno_id, fallo)
        return

    _YA_SINTETIZADO[turno_id] = audio
    while len(_YA_SINTETIZADO) > MAX_PENDIENTES:
        _YA_SINTETIZADO.popitem(last=False)


async def _calentar_voz(app: FastAPI, activo: bool) -> None:
    """Primera llamada a Polly al arrancar, no en el primer turno del usuario.

    Medido: la primera síntesis tarda ~850 ms y las siguientes ~200. Ese costo
    lo paga el servidor al levantar, no la persona que abre la app —que es
    justo el turno donde se forma la primera impresión.
    """
    if not activo:
        return
    try:
        await asyncio.to_thread(app.state.tts.sintetizar, "listo")
    except Exception as fallo:  # noqa: BLE001 — arrancar sin voz es mejor que no arrancar
        registro.warning("no se pudo calentar la voz: %s", fallo)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI) -> AsyncIterator[None]:
    config = configuracion()
    motor = create_async_engine(config.database_url)

    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)

    app.state.fabrica = async_sessionmaker(motor, expire_on_commit=False)
    app.state.llm = construir_llm(config)
    app.state.stt = construir_stt(config)
    app.state.tts = construir_tts(config)

    await _calentar_voz(app, config.calentar_voz)

    yield

    await motor.dispose()


app = FastAPI(title="Pacer", lifespan=ciclo_de_vida)


@app.post("/api/turno")
async def turno(audio: UploadFile, tareas: BackgroundTasks) -> JSONResponse:
    """Un turno hablado completo."""
    arranque = time.perf_counter()

    if app.state.stt is None:
        return JSONResponse(
            {"error": "sin_stt", "detalle": "falta GROQ_API_KEY en el .env"},
            status_code=503,
        )

    datos = await audio.read()
    if not datos:
        return JSONResponse({"error": "audio_vacio"}, status_code=400)

    try:
        transcripcion = app.state.stt.transcribir(datos, audio.filename or "turno.webm")
    except ErrorDeTranscripcion as fallo:
        return JSONResponse(
            {
                "error": "fallo_transcripcion",
                "detalle": fallo.motivo,
                "recuperable": fallo.recuperable,
            },
            status_code=502,
        )

    if not transcripcion.texto:
        return JSONResponse({"error": "no_se_entendio"}, status_code=422)

    ms_stt = int((time.perf_counter() - arranque) * 1000)
    hoy = datetime.now(UTC).date()

    sesion.mensajes.append(
        {"role": "user", "content": [{"text": transcripcion.texto}]}
    )

    async with app.state.fabrica() as bd:
        repositorio = RepositorioPlan(bd)
        plan_previo = await repositorio.version_activa(CORREDOR_PILOTO)
        sistema = construir_prompt(
            construir_bloque(plan_previo, hoy=hoy, fecha_carrera=sesion.perfil.fecha_carrera)
            if plan_previo and sesion.perfil.fecha_carrera
            else None
        )

        resultado = await atender_turno(
            llm=app.state.llm,
            repositorio=repositorio,
            sistema=sistema,
            mensajes=sesion.mensajes,
            perfil=sesion.perfil,
            corredor_id=CORREDOR_PILOTO,
            hoy=hoy,
        )

    ms_total = int((time.perf_counter() - arranque) * 1000)

    sesion.perfil = resultado.perfil
    sesion.mensajes = resultado.mensajes
    sesion.mensajes.append(
        {"role": "assistant", "content": [{"text": resultado.texto or "..."}]}
    )

    # La voz NO se sintetiza aquí. El texto se devuelve en cuanto está y el
    # audio se pide aparte: así el usuario lee la respuesta segundos antes de
    # oírla, y un turno en modo texto no gasta una llamada a Polly.
    turno_id = _guardar_para_voz(resultado.texto)
    if resultado.texto:
        tareas.add_task(_adelantar_sintesis, turno_id, resultado.texto)

    return JSONResponse(
        {
            "transcripcion": transcripcion.texto,
            "respuesta": resultado.texto,
            "turno_id": turno_id,
            "herramientas": list(resultado.herramientas_usadas),
            "plan_version": resultado.plan.version if resultado.plan else None,
            "motivo_cambio": resultado.plan.motivo_cambio if resultado.plan else None,
            "latencia_ms": {
                "transcripcion": ms_stt,
                "coach": ms_total - ms_stt,
                "total": ms_total,
            },
        }
    )


@app.get("/api/voz/{turno_id}")
async def voz(turno_id: str) -> Response:
    """Devuelve la voz del turno. Suele estar lista antes de que la pidan."""
    adelantada = _YA_SINTETIZADO.get(turno_id)
    if adelantada is not None:
        return Response(adelantada, media_type="audio/mpeg")

    texto = _PENDIENTES.get(turno_id)
    if not texto:
        return Response(status_code=404)

    audio = await asyncio.to_thread(app.state.tts.sintetizar, texto)
    return Response(audio, media_type="audio/mpeg")


@app.get("/api/salud")
async def salud() -> dict[str, Any]:
    """Qué capacidades están vivas. Útil cuando algo falla desde el teléfono."""
    config = configuracion()
    return {
        "stt": config.stt_disponible,
        "base": "postgres" if config.es_postgres else "sqlite",
        "region": config.aws_region,
        "observabilidad": config.observabilidad_disponible,
    }


# Se monta al final para que las rutas /api tengan precedencia sobre la raíz.
app.mount("/", StaticFiles(directory=DIRECTORIO_WEB, html=True), name="web")
