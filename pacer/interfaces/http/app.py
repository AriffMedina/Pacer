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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from pacer.application.casos_uso.atender_telegram import atender_mensaje_de_telegram
from pacer.application.casos_uso.atender_turno import atender_turno
from pacer.application.contexto.bloque_estado import construir_bloque
from pacer.application.contexto.prompt_sistema import construir_prompt
from pacer.composition_root import (
    configuracion,
    construir_llm,
    construir_observabilidad,
    construir_stt,
    construir_telegram,
    construir_tts,
)
from pacer.domain.puertos.notificacion import MensajeEntrante
from pacer.domain.puertos.voz import ErrorDeTranscripcion
from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan
from pacer.infrastructure.persistencia.repositorio_corredor import RepositorioCorredor
from pacer.interfaces.http.internas import router as router_interno
from pacer.interfaces.worker.sondeo_telegram import sondear

DIRECTORIO_WEB = Path(__file__).resolve().parents[3] / "web"

registro = logging.getLogger("pacer")


# Cuántos turnos anteriores se le recuerdan al modelo. No hace falta más: los
# hechos —perfil, plan, sesiones— viven en tablas y entran por el bloque de
# estado. Esto es continuidad de trato, no fuente de verdad.
TURNOS_RECORDADOS = 12

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
    app.state.trazas = construir_observabilidad(config)
    app.state.llm = construir_llm(config, app.state.trazas)
    app.state.stt = construir_stt(config)
    app.state.tts = construir_tts(config)

    await _calentar_voz(app, config.calentar_voz)

    app.state.telegram = construir_telegram(config)
    sondeo = _arrancar_sondeo(app)

    yield

    if sondeo is not None:
        sondeo.cancel()
    if app.state.telegram is not None:
        app.state.telegram.cerrar()
    app.state.trazas.cerrar()
    await motor.dispose()


def _arrancar_sondeo(app: FastAPI) -> asyncio.Task[None] | None:
    """Escucha Telegram en segundo plano mientras la app viva."""
    canal = app.state.telegram
    if canal is None:
        return None

    async def atender(mensaje: MensajeEntrante) -> None:
        async with app.state.fabrica() as bd:
            corredores = RepositorioCorredor(bd)
            corredor = await corredores.obtener_o_crear_piloto()
            await corredores.vincular_telegram(corredor.id, mensaje.chat_id)

            historial = await corredores.ultimos_turnos(
                corredor.id, TURNOS_RECORDADOS
            )

            resultado = await atender_mensaje_de_telegram(
                mensaje,
                llm=app.state.llm,
                stt=app.state.stt,
                canal=canal,
                repositorio=RepositorioPlan(bd),
                sistema=construir_prompt(),
                historial=historial,
                perfil=corredor.perfil,
                corredor_id=corredor.id,
                hoy=datetime.now(UTC).date(),
            )

            if resultado.atendido:
                await corredores.guardar_perfil(corredor.id, resultado.perfil)
                await corredores.recordar(
                    corredor.id,
                    "user",
                    resultado.dicho_por_el_corredor,
                    canal="telegram",
                )
                await corredores.recordar(
                    corredor.id, "assistant", resultado.respuesta, canal="telegram"
                )

    return asyncio.create_task(sondear(canal, atender))


app = FastAPI(title="Pacer", lifespan=ciclo_de_vida)
app.include_router(router_interno)


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
        # En un hilo: httpx aquí es bloqueante y colgaría el event loop, que es
        # justo lo que rompe cuando entren Telegram y la web a la vez.
        transcripcion = await asyncio.to_thread(
            app.state.stt.transcribir, datos, audio.filename or "turno.webm"
        )
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

    # La traza del turno envuelve todo: las llamadas al modelo cuelgan de ella,
    # así en Langfuse se ve una conversación y no llamadas sueltas.
    with app.state.trazas.observar(
        nombre="turno_hablado",
        entrada={"transcripcion": transcripcion.texto},
        metadatos={"ms_transcripcion": ms_stt},
    ) as traza:
        async with app.state.fabrica() as bd:
            corredores = RepositorioCorredor(bd)
            corredor = await corredores.obtener_o_crear_piloto()

            # El coach retoma donde quedó, aunque el servidor se haya reiniciado.
            historial = await corredores.ultimos_turnos(
                corredor.id, TURNOS_RECORDADOS
            )
            historial.append(
                {"role": "user", "content": [{"text": transcripcion.texto}]}
            )

            repositorio = RepositorioPlan(bd)
            plan_previo = await repositorio.version_activa(corredor.id)
            sistema = construir_prompt(
                construir_bloque(
                    plan_previo, hoy=hoy, fecha_carrera=corredor.perfil.fecha_carrera
                )
                if plan_previo and corredor.perfil.fecha_carrera
                else None
            )

            resultado = await atender_turno(
                llm=app.state.llm,
                repositorio=repositorio,
                sistema=sistema,
                mensajes=historial,
                perfil=corredor.perfil,
                corredor_id=corredor.id,
                hoy=hoy,
            )

            await corredores.guardar_perfil(corredor.id, resultado.perfil)
            await corredores.recordar(
                corredor.id, "user", transcripcion.texto, canal="web"
            )
            await corredores.recordar(
                corredor.id, "assistant", resultado.texto, canal="web"
            )

        traza.registrar_salida(
            {
                "respuesta": resultado.texto,
                "herramientas": list(resultado.herramientas_usadas),
                "plan_version": resultado.plan.version if resultado.plan else None,
                "motivo_cambio": resultado.plan.motivo_cambio if resultado.plan else None,
                "vueltas": resultado.vueltas,
            }
        )

    ms_total = int((time.perf_counter() - arranque) * 1000)

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


@app.get("/api/plan")
async def plan_actual() -> dict[str, Any]:
    """El plan vigente y el perfil, para las pantallas de plan y agenda."""
    hoy = datetime.now(UTC).date()

    async with app.state.fabrica() as bd:
        corredores = RepositorioCorredor(bd)
        corredor = await corredores.obtener_o_crear_piloto()
        plan = await RepositorioPlan(bd).version_activa(corredor.id)

    perfil = corredor.perfil
    if plan is None:
        return {"hay_plan": False, "objetivo": perfil.objetivo}

    semana_actual = next(
        (
            s.numero
            for s in plan.semanas
            if any(ses.fecha >= hoy for ses in s.sesiones)
        ),
        len(plan.semanas),
    )

    return {
        "hay_plan": True,
        "version": plan.version,
        "motivo_cambio": plan.motivo_cambio,
        "objetivo": perfil.objetivo,
        "fecha_carrera": perfil.fecha_carrera.isoformat()
        if perfil.fecha_carrera
        else None,
        "dias_para_carrera": (perfil.fecha_carrera - hoy).days
        if perfil.fecha_carrera
        else None,
        "semana_actual": semana_actual,
        "semanas_totales": len(plan.semanas),
        "hoy": hoy.isoformat(),
        "semanas": [
            {
                "numero": s.numero,
                "bloque": s.bloque,
                "es_descarga": s.es_descarga,
                "km_total": s.km_total,
                "sesiones": [
                    {
                        "fecha": ses.fecha.isoformat(),
                        "tipo": ses.tipo,
                        "km": ses.km,
                        "completada": ses.completada,
                        "sensacion": ses.sensacion,
                    }
                    for ses in s.sesiones
                ],
            }
            for s in plan.semanas
        ],
    }


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
