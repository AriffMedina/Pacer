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
from dataclasses import replace
from datetime import UTC, date, datetime
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
from pacer.application.contexto.fechas import interpretar_fecha
from pacer.application.contexto.prompt_sistema import construir_prompt
from pacer.composition_root import (
    configuracion,
    construir_llm,
    construir_observabilidad,
    construir_stt,
    construir_telegram,
    construir_tts,
)
from pacer.domain.entidades.carrera import Carrera
from pacer.domain.puertos.notificacion import MensajeEntrante
from pacer.domain.puertos.voz import ErrorDeTranscripcion
from pacer.domain.servicios.categoria import categoria_de_km, como_se_entrena
from pacer.domain.servicios.prescripcion import prescribir
from pacer.domain.servicios.tablero import Tablero, resumir
from pacer.infrastructure.persistencia.esquema import agregar_columnas_nuevas
from pacer.infrastructure.persistencia.modelos import Base
from pacer.infrastructure.persistencia.repositorio import RepositorioPlan
from pacer.infrastructure.persistencia.repositorio_carrera import RepositorioCarrera
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


async def _atender(dicho: str, canal: str) -> tuple[Any, str]:
    """Un turno completo, venga de voz o de texto.

    La traza envuelve todo: las llamadas al modelo cuelgan de ella, así en
    Langfuse se ve una conversación y no llamadas sueltas.
    """
    hoy = datetime.now(UTC).date()

    with app.state.trazas.observar(
        nombre="turno", entrada={"dicho": dicho}, metadatos={"canal": canal}
    ) as traza:
        async with app.state.fabrica() as bd:
            corredores = RepositorioCorredor(bd)
            corredor = await corredores.obtener_o_crear_piloto()
            agenda = RepositorioCarrera(bd)

            # El coach retoma donde quedó, aunque el servidor se haya reiniciado.
            historial = await corredores.ultimos_turnos(corredor.id, TURNOS_RECORDADOS)
            historial.append({"role": "user", "content": [{"text": dicho}]})

            repositorio = RepositorioPlan(bd)
            plan_previo = await repositorio.version_activa(corredor.id)
            # El bloque se arma SIEMPRE: aunque no haya plan, el corredor puede
            # tener carreras apuntadas y el coach tiene que verlas.
            sistema = construir_prompt(
                construir_bloque(
                    plan_previo,
                    hoy=hoy,
                    fecha_carrera=corredor.perfil.fecha_carrera,
                    carreras=await agenda.todas(corredor.id),
                )
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

            for nueva in resultado.carreras_nuevas:
                await agenda.agregar(corredor.id, nueva)

            await corredores.guardar_perfil(corredor.id, resultado.perfil)
            await corredores.recordar(corredor.id, "user", dicho, canal=canal)
            await corredores.recordar(
                corredor.id, "assistant", resultado.texto, canal=canal
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

    return resultado, _guardar_para_voz(resultado.texto)


def _respuesta(
    dicho: str, resultado: Any, turno_id: str, ms_stt: int, ms_total: int
) -> JSONResponse:
    return JSONResponse(
        {
            "transcripcion": dicho,
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
        # create_all no toca las tablas que ya existen. Sin esto, una columna
        # nueva rompe todas las consultas contra una base que ya tenía datos.
        await conexion.run_sync(agregar_columnas_nuevas)

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

    resultado, turno_id = await _atender(transcripcion.texto, canal="web")
    ms_total = int((time.perf_counter() - arranque) * 1000)

    # La voz NO se sintetiza aquí: el texto se devuelve en cuanto está y el
    # audio se pide aparte, así se lee la respuesta antes de oírla.
    if resultado.texto:
        tareas.add_task(_adelantar_sintesis, turno_id, resultado.texto)

    return _respuesta(transcripcion.texto, resultado, turno_id, ms_stt, ms_total)


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


@app.post("/api/mensaje")
async def mensaje(cuerpo: dict[str, Any], tareas: BackgroundTasks) -> JSONResponse:
    """Un turno escrito. Mismo coach, mismo pipeline, sin transcripción.

    Existe para los chips de sugerencia y para el modo texto: en un producto de
    voz, escribir tiene que ser una alternativa, no una vía muerta.
    """
    texto = str(cuerpo.get("texto", "")).strip()
    if not texto:
        return JSONResponse({"error": "mensaje_vacio"}, status_code=400)

    arranque = time.perf_counter()
    resultado, turno_id = await _atender(texto, canal="web")
    ms_total = int((time.perf_counter() - arranque) * 1000)

    if resultado.texto:
        tareas.add_task(_adelantar_sintesis, turno_id, resultado.texto)

    return _respuesta(texto, resultado, turno_id, ms_stt=0, ms_total=ms_total)


@app.get("/api/plan")
async def plan_actual() -> dict[str, Any]:
    """El plan vigente y el perfil, para las pantallas de plan y agenda."""
    hoy = datetime.now(UTC).date()

    async with app.state.fabrica() as bd:
        corredores = RepositorioCorredor(bd)
        corredor = await corredores.obtener_o_crear_piloto()
        plan = await RepositorioPlan(bd).version_activa(corredor.id)

    perfil = corredor.perfil
    tablero = _tablero_json(resumir(plan, hoy=hoy))

    if plan is None:
        # El tablero viaja igual: la vista se dibuja desde el primer día, con
        # las tarjetas vacías, y no con media pantalla en blanco.
        return {
            "hay_plan": False,
            "nombre": perfil.nombre,
            "objetivo": perfil.objetivo,
            "nivel": perfil.nivel,
            # `hoy` y la fecha objetivo viajan también sin plan: el calendario
            # de la agenda se dibuja desde el primer día, con o sin entrenamiento.
            "hoy": hoy.isoformat(),
            "fecha_carrera": perfil.fecha_carrera.isoformat()
            if perfil.fecha_carrera
            else None,
            "dias_para_carrera": (perfil.fecha_carrera - hoy).days
            if perfil.fecha_carrera
            else None,
            "tablero": tablero,
        }

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
        "tablero": tablero,
        "nombre": perfil.nombre,
        "nivel": perfil.nivel,
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
                        # Qué hacer exactamente. Lo calcula el dominio: "calidad
                        # 8.8 km" no le dice nada a nadie.
                        "receta": _receta_json(
                            prescribir(ses, nivel=perfil.nivel, bloque=s.bloque)
                        ),
                    }
                    for ses in s.sesiones
                ],
            }
            for s in plan.semanas
        ],
    }


@app.delete("/api/plan")
async def borrar_plan() -> dict[str, Any]:
    """Descarta el plan entero, con todas sus versiones.

    Es distinto de ajustar: ajustar produce una v2 y archiva la anterior. Esto
    es "ya no voy a esa carrera", y dejar el plan viejo colgando haría que el
    coach siga recordando sesiones de algo que ya no existe.
    """
    async with app.state.fabrica() as bd:
        corredor = await RepositorioCorredor(bd).obtener_o_crear_piloto()
        borradas = await RepositorioPlan(bd).borrar_todo(corredor.id)

    return {"borradas": borradas}


@app.get("/api/carreras")
async def carreras() -> dict[str, Any]:
    async with app.state.fabrica() as bd:
        corredor = await RepositorioCorredor(bd).obtener_o_crear_piloto()
        apuntadas = await RepositorioCarrera(bd).todas(corredor.id)

    objetivo = corredor.perfil.fecha_carrera
    return {"carreras": [_carrera_json(c, objetivo) for c in apuntadas]}


@app.post("/api/carreras")
async def agregar_carrera(cuerpo: dict[str, Any]) -> JSONResponse:
    """Apunta una carrera desde el calendario.

    El coach la ve en el turno siguiente porque el bloque de estado se arma
    leyendo esta misma tabla: agregar aquí y hablar allá no son dos mundos.
    """
    nombre = str(cuerpo.get("nombre", "")).strip()
    fecha = interpretar_fecha(str(cuerpo.get("fecha", "")))

    if not nombre:
        return JSONResponse({"error": "falta_el_nombre"}, status_code=400)
    if fecha is None:
        return JSONResponse({"error": "fecha_no_entendida"}, status_code=400)

    try:
        km = float(cuerpo["distancia_km"]) if cuerpo.get("distancia_km") else None
    except (TypeError, ValueError):
        return JSONResponse({"error": "distancia_no_entendida"}, status_code=400)

    if km is not None and not 0 < km <= 200:
        return JSONResponse({"error": "distancia_fuera_de_rango"}, status_code=400)

    async with app.state.fabrica() as bd:
        corredor = await RepositorioCorredor(bd).obtener_o_crear_piloto()
        guardada = await RepositorioCarrera(bd).agregar(
            corredor.id,
            Carrera(
                fecha=fecha,
                nombre=nombre[:80],
                distancia_km=km,
                nota=str(cuerpo.get("nota") or "")[:200],
            ),
        )

    return JSONResponse(_carrera_json(guardada, corredor.perfil.fecha_carrera))


@app.post("/api/carreras/{carrera_id}/objetivo")
async def elegir_objetivo(carrera_id: int) -> JSONResponse:
    """Marca una carrera como la que se está entrenando.

    Es lo que faltaba: con varias carreras apuntadas, nada decía cuál era la
    objetivo, y el coach lo preguntaba una y otra vez. Elegirla aquí escribe el
    objetivo y la fecha en el perfil, que es de donde sale el plan.
    """
    async with app.state.fabrica() as bd:
        corredores = RepositorioCorredor(bd)
        corredor = await corredores.obtener_o_crear_piloto()
        elegida = next(
            (
                c
                for c in await RepositorioCarrera(bd).todas(corredor.id)
                if c.id == carrera_id
            ),
            None,
        )

        if elegida is None:
            return JSONResponse({"error": "no_existe"}, status_code=404)
        if elegida.distancia_km is None:
            return JSONResponse({"error": "sin_distancia"}, status_code=400)

        categoria = categoria_de_km(elegida.distancia_km)
        if categoria is None:
            return JSONResponse(
                {
                    "error": "distancia_no_cubierta",
                    "explicacion": como_se_entrena(elegida.distancia_km),
                },
                status_code=400,
            )

        await corredores.guardar_perfil(
            corredor.id,
            replace(corredor.perfil, objetivo=categoria, fecha_carrera=elegida.fecha),
        )

    return JSONResponse(
        {
            "objetivo": categoria,
            "fecha_carrera": elegida.fecha.isoformat(),
            "como_se_entrena": como_se_entrena(elegida.distancia_km),
        }
    )


@app.delete("/api/carreras/{carrera_id}")
async def quitar_carrera(carrera_id: int) -> JSONResponse:
    async with app.state.fabrica() as bd:
        corredor = await RepositorioCorredor(bd).obtener_o_crear_piloto()
        existia = await RepositorioCarrera(bd).quitar(corredor.id, carrera_id)

    if not existia:
        return JSONResponse({"error": "no_existe"}, status_code=404)
    return JSONResponse({"borrada": True})


def _carrera_json(carrera: Carrera, fecha_objetivo: date | None) -> dict[str, Any]:
    return {
        "id": carrera.id,
        "fecha": carrera.fecha.isoformat(),
        "nombre": carrera.nombre,
        "distancia_km": carrera.distancia_km,
        # Con qué plan se entrena, resuelto acá: la interfaz no repite la regla.
        "como_se_entrena": como_se_entrena(carrera.distancia_km)
        if carrera.distancia_km is not None
        else None,
        "categoria": categoria_de_km(carrera.distancia_km)
        if carrera.distancia_km is not None
        else None,
        "es_objetivo": fecha_objetivo is not None and carrera.fecha == fecha_objetivo,
        "nota": carrera.nota,
    }


def _receta_json(receta: Any) -> dict[str, Any]:
    return {
        "resumen": receta.resumen,
        "esfuerzo": receta.esfuerzo,
        "porque": receta.porque,
        "tramos": [
            {"titulo": t.titulo, "detalle": t.detalle, "km": t.km}
            for t in receta.tramos
        ],
    }


def _tablero_json(tablero: Tablero) -> dict[str, Any]:
    """Serializa el resumen. Traduce, no calcula: los números ya venían hechos."""
    return {
        "racha": tablero.racha,
        "semana": [
            {"inicial": d.inicial, "fecha": d.fecha.isoformat(), "estado": d.estado}
            for d in tablero.semana
        ],
        "proxima": {
            "fecha": tablero.proxima.fecha.isoformat(),
            "tipo": tablero.proxima.tipo,
            "km": tablero.proxima.km,
            "cuando": tablero.proxima.cuando,
        }
        if tablero.proxima
        else None,
        "km_hechos": tablero.km_hechos,
        "km_planeados": tablero.km_planeados,
        "porcentaje": tablero.porcentaje,
        "actividad": [
            {
                "fecha": h.fecha.isoformat(),
                "tipo": h.tipo,
                "km": h.km,
                "sensacion": h.sensacion,
                "cuando": h.cuando,
            }
            for h in tablero.actividad
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
